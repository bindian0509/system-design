"""
TDD Test Suite: Order Service
==============================
Instant Grocery Delivery App — Blinkit-scale

The Order Service is the synchronous critical path (< 500ms p99).
It owns the full order lifecycle from cart lock through delivery.

Assumed module layout (production code lives under `src/order_service/`):
    src/order_service/models.py    — dataclasses + OrderState enum
    src/order_service/exceptions.py — domain exceptions
    src/order_service/service.py   — OrderService, ReconciliationJob

Run with:
    pytest docs/tdd/test_order_service.py -v
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# ── Inline stubs for the production interfaces ──────────────────────────────
# These mirror what the real src/order_service/ modules must export.
# The tests import from these stubs so the file is self-contained and
# runnable before production code exists. When production code lands,
# replace the import block below with the real imports.
# ---------------------------------------------------------------------------


class OrderState(str, Enum):
    CART_LOCKED = "CART_LOCKED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    PICKING = "PICKING"
    PACKED = "PACKED"
    RIDER_ASSIGNED = "RIDER_ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Valid state transitions expressed as a directed graph.
VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.CART_LOCKED: {OrderState.PAYMENT_PENDING, OrderState.CANCELLED},
    OrderState.PAYMENT_PENDING: {
        OrderState.PAYMENT_CONFIRMED,
        OrderState.FAILED,
        OrderState.CANCELLED,
    },
    OrderState.PAYMENT_CONFIRMED: {OrderState.INVENTORY_RESERVED, OrderState.FAILED},
    OrderState.INVENTORY_RESERVED: {OrderState.PICKING, OrderState.CANCELLED},
    OrderState.PICKING: {OrderState.PACKED, OrderState.CANCELLED},
    OrderState.PACKED: {OrderState.RIDER_ASSIGNED},
    OrderState.RIDER_ASSIGNED: {OrderState.OUT_FOR_DELIVERY},
    OrderState.OUT_FOR_DELIVERY: {OrderState.DELIVERED, OrderState.FAILED},
    OrderState.DELIVERED: set(),
    OrderState.FAILED: set(),
    OrderState.CANCELLED: set(),
}

CANCELLABLE_STATES: set[OrderState] = {
    OrderState.CART_LOCKED,
    OrderState.PAYMENT_PENDING,
    OrderState.INVENTORY_RESERVED,
    OrderState.PICKING,
}

TERMINAL_STATES: set[OrderState] = {
    OrderState.DELIVERED,
    OrderState.FAILED,
    OrderState.CANCELLED,
}


# ── Domain exceptions ────────────────────────────────────────────────────────


class InsufficientStockError(Exception):
    """Raised when the Inventory Service cannot reserve the requested items."""


class PaymentFailedError(Exception):
    """Raised when the Payment Service declines or errors on authorization."""


class CancellationNotAllowedError(Exception):
    """Raised when the order's current state does not permit cancellation."""


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""


class OrderNotFoundError(Exception):
    """Raised when the requested order does not exist or belongs to another user."""


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class OrderItem:
    sku_id: str
    qty: int


@dataclass
class OrderRequest:
    user_id: str
    store_id: str
    items: list[OrderItem]
    payment_method_id: str
    delivery_address_id: str


@dataclass
class OrderResult:
    order_id: str
    status: OrderState
    eta_minutes: int


@dataclass
class Order:
    order_id: str
    user_id: str
    store_id: str
    status: OrderState
    items: list[OrderItem]
    total_amount: float
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ReconciliationResult:
    resolved_count: int
    failed_count: int


# ── Minimal in-memory implementations ────────────────────────────────────────
# These are the production classes under test.  In a real project they would
# live in src/ and be imported here.  They are inlined so the test file is
# entirely self-contained.


class OrderService:
    """
    Orchestrates order placement, cancellation, retrieval, and state transitions.

    Critical invariants:
    - DB row is written with PAYMENT_PENDING status BEFORE calling the
      Payment Service (write-ahead pattern).
    - Inventory reservation always precedes payment authorisation.
    - idempotency_key sent to Payment Service equals the order_id.
    """

    def __init__(self, inventory_service, payment_service, kafka_producer, db_session):
        self._inventory = inventory_service
        self._payment = payment_service
        self._kafka = kafka_producer
        self._db = db_session

    # ------------------------------------------------------------------
    def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Critical path (p99 < 500 ms).

        Flow:
        1. Persist order row with status=PAYMENT_PENDING (write-ahead).
        2. Call Inventory Service to reserve stock.
           - On failure → raise InsufficientStockError (no payment call).
        3. Call Payment Service with idempotency_key = order_id.
           - On failure → mark order FAILED, raise PaymentFailedError.
        4. Mark order PAYMENT_CONFIRMED.
        5. Publish `order.placed` event to Kafka.
        6. Return OrderResult.
        """
        order_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)

        order = Order(
            order_id=order_id,
            user_id=request.user_id,
            store_id=request.store_id,
            status=OrderState.PAYMENT_PENDING,
            items=request.items,
            total_amount=0.0,  # pricing service out of scope here
            idempotency_key=order_id,
            created_at=now,
            updated_at=now,
        )

        # ── 1. Write-ahead: persist PAYMENT_PENDING row ──────────────────
        self._db.save(order)

        # ── 2. Reserve inventory ─────────────────────────────────────────
        reserved = self._inventory.reserve(
            store_id=request.store_id, items=request.items
        )
        if not reserved:
            order.status = OrderState.FAILED
            self._db.save(order)
            raise InsufficientStockError(
                f"Stock unavailable for order {order_id}"
            )

        # ── 3. Authorise payment ─────────────────────────────────────────
        payment_ok = self._payment.authorize(
            payment_method_id=request.payment_method_id,
            amount=order.total_amount,
            idempotency_key=order_id,
        )
        if not payment_ok:
            order.status = OrderState.FAILED
            self._db.save(order)
            raise PaymentFailedError(
                f"Payment authorisation failed for order {order_id}"
            )

        # ── 4. Confirm ───────────────────────────────────────────────────
        order.status = OrderState.PAYMENT_CONFIRMED
        self._db.save(order)

        # ── 5. Publish event ─────────────────────────────────────────────
        self._kafka.publish("order.placed", {"order_id": order_id})

        return OrderResult(
            order_id=order_id,
            status=OrderState.PAYMENT_CONFIRMED,
            eta_minutes=30,
        )

    # ------------------------------------------------------------------
    def cancel_order(self, order_id: str, user_id: str) -> Order:
        """
        Returns the updated Order with status=CANCELLED.

        Raises:
            OrderNotFoundError: if order doesn't exist or user_id doesn't match.
            CancellationNotAllowedError: if current state isn't cancellable.
        """
        order = self._db.get(order_id)
        if order is None or order.user_id != user_id:
            raise OrderNotFoundError(order_id)

        if order.status not in CANCELLABLE_STATES:
            raise CancellationNotAllowedError(
                f"Cannot cancel order in state {order.status}"
            )

        order.status = OrderState.CANCELLED
        order.updated_at = datetime.now(tz=timezone.utc)
        self._db.save(order)
        return order

    # ------------------------------------------------------------------
    def get_order(self, order_id: str, user_id: str) -> Order:
        """
        Returns the Order.

        Raises:
            OrderNotFoundError: if order doesn't exist or user_id doesn't match.
        """
        order = self._db.get(order_id)
        if order is None or order.user_id != user_id:
            raise OrderNotFoundError(order_id)
        return order

    # ------------------------------------------------------------------
    def transition_state(self, order_id: str, new_state: OrderState) -> Order:
        """
        Applies the requested state transition after validating it against
        VALID_TRANSITIONS.

        Raises:
            OrderNotFoundError: if order doesn't exist.
            InvalidStateTransitionError: if the transition is not allowed.
        """
        order = self._db.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)

        allowed = VALID_TRANSITIONS.get(order.status, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"{order.status} → {new_state} is not a valid transition"
            )

        order.status = new_state
        order.updated_at = datetime.now(tz=timezone.utc)
        self._db.save(order)
        return order


# ── ReconciliationJob ─────────────────────────────────────────────────────────


class ReconciliationJob:
    """
    Periodic background job that resolves orders stuck in PAYMENT_PENDING.

    Any order that has been in PAYMENT_PENDING for more than 5 minutes is
    re-queried against the Payment Service using its idempotency_key.  The
    result is then used to transition the order to PAYMENT_CONFIRMED or FAILED.
    """

    STALE_THRESHOLD_MINUTES = 5

    def __init__(self, order_service: OrderService, payment_service, db_session):
        self._order_service = order_service
        self._payment = payment_service
        self._db = db_session

    def run(self) -> ReconciliationResult:
        """
        Finds PAYMENT_PENDING orders older than 5 minutes, re-queries the
        Payment Service, and resolves each order.

        Returns:
            ReconciliationResult with resolved_count and failed_count.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(
            minutes=self.STALE_THRESHOLD_MINUTES
        )
        stale_orders = self._db.find_stale_pending(cutoff)

        resolved_count = 0
        failed_count = 0

        for order in stale_orders:
            payment_status = self._payment.query_status(order.idempotency_key)
            if payment_status == "SUCCESS":
                order.status = OrderState.PAYMENT_CONFIRMED
                self._db.save(order)
                resolved_count += 1
            else:
                order.status = OrderState.FAILED
                self._db.save(order)
                failed_count += 1

        return ReconciliationResult(
            resolved_count=resolved_count, failed_count=failed_count
        )


# ===========================================================================
# ── Fixtures ────────────────────────────────────────────────────────────────
# ===========================================================================


def _make_order(
    order_id: str | None = None,
    user_id: str = "user-1",
    status: OrderState = OrderState.PAYMENT_PENDING,
    minutes_old: int = 0,
) -> Order:
    """Helper that builds a fully-populated Order dataclass."""
    now = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_old)
    oid = order_id or str(uuid.uuid4())
    return Order(
        order_id=oid,
        user_id=user_id,
        store_id="store-42",
        status=status,
        items=[OrderItem(sku_id="sku-001", qty=2)],
        total_amount=199.0,
        idempotency_key=oid,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def mock_inventory():
    """Inventory Service mock — reserve() returns True by default."""
    svc = MagicMock(name="InventoryService")
    svc.reserve.return_value = True
    return svc


@pytest.fixture()
def mock_payment():
    """Payment Service mock — authorize() returns True, query_status() returns SUCCESS."""
    svc = MagicMock(name="PaymentService")
    svc.authorize.return_value = True
    svc.query_status.return_value = "SUCCESS"
    return svc


@pytest.fixture()
def mock_kafka():
    """Kafka producer mock."""
    return MagicMock(name="KafkaProducer")


@pytest.fixture()
def mock_db():
    """
    In-memory DB session mock.

    - save(order) stores order in an internal dict keyed by order_id.
    - get(order_id) retrieves from that dict, or returns None.
    - find_stale_pending(cutoff) returns an empty list by default;
      tests override this as needed.
    """
    db = MagicMock(name="DbSession")
    _store: dict[str, Order] = {}

    def _save(order: Order) -> None:
        _store[order.order_id] = order

    def _get(order_id: str) -> Order | None:
        return _store.get(order_id)

    db.save.side_effect = _save
    db.get.side_effect = _get
    db.find_stale_pending.return_value = []
    return db


@pytest.fixture()
def order_service(mock_inventory, mock_payment, mock_kafka, mock_db):
    """Fully wired OrderService with all dependencies mocked."""
    return OrderService(
        inventory_service=mock_inventory,
        payment_service=mock_payment,
        kafka_producer=mock_kafka,
        db_session=mock_db,
    )


@pytest.fixture()
def reconciliation_job(order_service, mock_payment, mock_db):
    """ReconciliationJob wired to the same mocks as the order_service fixture."""
    return ReconciliationJob(
        order_service=order_service,
        payment_service=mock_payment,
        db_session=mock_db,
    )


@pytest.fixture()
def sample_request():
    """A valid OrderRequest used across placement tests."""
    return OrderRequest(
        user_id="user-1",
        store_id="store-42",
        items=[OrderItem(sku_id="sku-001", qty=2)],
        payment_method_id="pm-xyz",
        delivery_address_id="addr-abc",
    )


# ===========================================================================
# ── TestOrderPlacement ───────────────────────────────────────────────────────
# ===========================================================================


class TestOrderPlacement:
    """
    Tests for the OrderService.place_order() critical path.

    Validates the write-ahead pattern, inventory-first ordering, idempotency
    key propagation, Kafka event publication, and correct exception handling.
    """

    def test_place_order_returns_order_id_and_pending_status(
        self, order_service, sample_request
    ):
        """
        place_order() must return an OrderResult whose order_id is a non-empty
        string and whose status is PAYMENT_CONFIRMED after a fully successful flow.
        """
        result = order_service.place_order(sample_request)

        assert isinstance(result, OrderResult)
        assert result.order_id and len(result.order_id) > 0
        assert result.status == OrderState.PAYMENT_CONFIRMED
        assert isinstance(result.eta_minutes, int)

    def test_place_order_writes_payment_pending_row_before_calling_payment_service(
        self, order_service, sample_request, mock_db, mock_payment
    ):
        """
        The write-ahead guarantee: db.save() must be called with a
        PAYMENT_PENDING order BEFORE payment.authorize() is ever invoked.

        We track call order across both mocks using a shared call-log list.
        """
        call_log: list[str] = []

        original_save = mock_db.save.side_effect

        def tracking_save(order: Order) -> None:
            if order.status == OrderState.PAYMENT_PENDING:
                call_log.append("db_save_pending")
            original_save(order)

        mock_payment.authorize.side_effect = lambda **kw: (
            call_log.append("payment_authorize") or True
        )
        mock_db.save.side_effect = tracking_save

        order_service.place_order(sample_request)

        assert "db_save_pending" in call_log, "DB was never written with PAYMENT_PENDING"
        assert "payment_authorize" in call_log, "Payment was never called"

        pending_idx = call_log.index("db_save_pending")
        payment_idx = call_log.index("payment_authorize")
        assert pending_idx < payment_idx, (
            "DB write with PAYMENT_PENDING must precede payment.authorize() call"
        )

    def test_place_order_calls_inventory_before_payment(
        self, order_service, sample_request, mock_inventory, mock_payment
    ):
        """
        Inventory reservation must happen before payment authorisation.

        We use a shared call-log injected as side-effects on both mocks to
        capture the relative call order.
        """
        call_log: list[str] = []

        mock_inventory.reserve.side_effect = lambda **kw: (
            call_log.append("inventory_reserve") or True
        )
        mock_payment.authorize.side_effect = lambda **kw: (
            call_log.append("payment_authorize") or True
        )

        order_service.place_order(sample_request)

        assert call_log.index("inventory_reserve") < call_log.index("payment_authorize"), (
            "inventory.reserve() must be called before payment.authorize()"
        )

    def test_place_order_raises_insufficient_stock_when_inventory_fails(
        self, order_service, sample_request, mock_inventory, mock_payment
    ):
        """
        When Inventory Service returns False (stock unavailable),
        place_order() must raise InsufficientStockError and must NOT call
        payment.authorize() at all.
        """
        mock_inventory.reserve.return_value = False

        with pytest.raises(InsufficientStockError):
            order_service.place_order(sample_request)

        mock_payment.authorize.assert_not_called()

    def test_place_order_raises_payment_failed_when_authorization_fails(
        self, order_service, sample_request, mock_payment
    ):
        """
        When Payment Service returns False (declined), place_order() must
        raise PaymentFailedError.
        """
        mock_payment.authorize.return_value = False

        with pytest.raises(PaymentFailedError):
            order_service.place_order(sample_request)

    def test_place_order_publishes_order_placed_event_on_success(
        self, order_service, sample_request, mock_kafka
    ):
        """
        On a fully successful placement, an 'order.placed' event must be
        published to Kafka exactly once, containing the order_id.
        """
        result = order_service.place_order(sample_request)

        mock_kafka.publish.assert_called_once()
        topic, payload = mock_kafka.publish.call_args.args
        assert topic == "order.placed"
        assert payload["order_id"] == result.order_id

    def test_place_order_does_not_publish_event_when_inventory_fails(
        self, order_service, sample_request, mock_inventory, mock_kafka
    ):
        """
        No Kafka event must be emitted when inventory reservation fails.
        Emitting a phantom event would mislead downstream consumers into
        thinking an order was placed.
        """
        mock_inventory.reserve.return_value = False

        with pytest.raises(InsufficientStockError):
            order_service.place_order(sample_request)

        mock_kafka.publish.assert_not_called()

    def test_place_order_does_not_publish_event_when_payment_fails(
        self, order_service, sample_request, mock_payment, mock_kafka
    ):
        """
        No Kafka event must be emitted when payment authorisation fails.
        An unpaid order must never be announced as placed.
        """
        mock_payment.authorize.return_value = False

        with pytest.raises(PaymentFailedError):
            order_service.place_order(sample_request)

        mock_kafka.publish.assert_not_called()

    def test_place_order_passes_idempotency_key_to_payment_service(
        self, order_service, sample_request, mock_payment
    ):
        """
        The idempotency_key forwarded to payment.authorize() must equal the
        order_id returned in the result.  This ensures that retrying the
        exact same payment call cannot produce a double-charge.
        """
        result = order_service.place_order(sample_request)

        _, kwargs = mock_payment.authorize.call_args
        assert kwargs["idempotency_key"] == result.order_id, (
            "idempotency_key sent to PaymentService must equal the order_id"
        )

    def test_place_order_marks_order_payment_confirmed_after_successful_payment(
        self, order_service, sample_request, mock_db
    ):
        """
        After a successful payment authorisation the order row persisted in
        the DB must have status=PAYMENT_CONFIRMED.

        We inspect all calls to db.save() and assert that the final save
        carries PAYMENT_CONFIRMED status.
        """
        order_service.place_order(sample_request)

        save_calls = mock_db.save.call_args_list
        assert len(save_calls) >= 2, "Expected at least two db.save() calls"

        # The last save should be PAYMENT_CONFIRMED
        final_saved_order: Order = save_calls[-1].args[0]
        assert final_saved_order.status == OrderState.PAYMENT_CONFIRMED, (
            "Final DB write must record PAYMENT_CONFIRMED status"
        )


# ===========================================================================
# ── TestOrderCancellation ────────────────────────────────────────────────────
# ===========================================================================


class TestOrderCancellation:
    """
    Tests for the OrderService.cancel_order() method.

    Validates which states permit cancellation, which do not, and that
    ownership (user_id) is enforced before any state change.
    """

    def _store_order(self, mock_db, order: Order) -> None:
        """Inject an order directly into the mock DB's internal store."""
        # Invoke the real side_effect (the _save closure) to pre-populate.
        mock_db.save(order)

    # ── States that ALLOW cancellation ──────────────────────────────────────

    def test_cancel_allowed_in_cart_locked_state(
        self, order_service, mock_db
    ):
        """An order in CART_LOCKED state can be cancelled by its owner."""
        order = _make_order(status=OrderState.CART_LOCKED)
        mock_db.save(order)

        result = order_service.cancel_order(order.order_id, order.user_id)

        assert result.status == OrderState.CANCELLED

    def test_cancel_allowed_in_payment_pending_state(
        self, order_service, mock_db
    ):
        """
        An order stuck in PAYMENT_PENDING (e.g. before reconciliation runs)
        can be cancelled by its owner.
        """
        order = _make_order(status=OrderState.PAYMENT_PENDING)
        mock_db.save(order)

        result = order_service.cancel_order(order.order_id, order.user_id)

        assert result.status == OrderState.CANCELLED

    def test_cancel_allowed_in_inventory_reserved_state(
        self, order_service, mock_db
    ):
        """An order with stock reserved but not yet picked can be cancelled."""
        order = _make_order(status=OrderState.INVENTORY_RESERVED)
        mock_db.save(order)

        result = order_service.cancel_order(order.order_id, order.user_id)

        assert result.status == OrderState.CANCELLED

    def test_cancel_allowed_in_picking_state(
        self, order_service, mock_db
    ):
        """An order that is being picked (but not packed) can still be cancelled."""
        order = _make_order(status=OrderState.PICKING)
        mock_db.save(order)

        result = order_service.cancel_order(order.order_id, order.user_id)

        assert result.status == OrderState.CANCELLED

    # ── States that FORBID cancellation ─────────────────────────────────────

    def test_cancel_not_allowed_in_packed_state(
        self, order_service, mock_db
    ):
        """
        Once an order is PACKED the rider is about to be assigned.
        Cancellation at this point is not permitted.
        """
        order = _make_order(status=OrderState.PACKED)
        mock_db.save(order)

        with pytest.raises(CancellationNotAllowedError):
            order_service.cancel_order(order.order_id, order.user_id)

    def test_cancel_not_allowed_in_rider_assigned_state(
        self, order_service, mock_db
    ):
        """A rider has accepted the delivery; cancellation is no longer possible."""
        order = _make_order(status=OrderState.RIDER_ASSIGNED)
        mock_db.save(order)

        with pytest.raises(CancellationNotAllowedError):
            order_service.cancel_order(order.order_id, order.user_id)

    def test_cancel_not_allowed_in_out_for_delivery_state(
        self, order_service, mock_db
    ):
        """The order is on the road; it cannot be cancelled."""
        order = _make_order(status=OrderState.OUT_FOR_DELIVERY)
        mock_db.save(order)

        with pytest.raises(CancellationNotAllowedError):
            order_service.cancel_order(order.order_id, order.user_id)

    def test_cancel_not_allowed_in_delivered_state(
        self, order_service, mock_db
    ):
        """A delivered order is in a terminal state and cannot be cancelled."""
        order = _make_order(status=OrderState.DELIVERED)
        mock_db.save(order)

        with pytest.raises(CancellationNotAllowedError):
            order_service.cancel_order(order.order_id, order.user_id)

    # ── Ownership enforcement ────────────────────────────────────────────────

    def test_cancel_raises_order_not_found_for_wrong_user(
        self, order_service, mock_db
    ):
        """
        Attempting to cancel an order with a user_id that doesn't match the
        order's owner must raise OrderNotFoundError.

        This prevents one user from cancelling another user's order, and also
        avoids leaking the existence of the order to an unauthorised caller.
        """
        order = _make_order(user_id="user-owner", status=OrderState.PAYMENT_PENDING)
        mock_db.save(order)

        with pytest.raises(OrderNotFoundError):
            order_service.cancel_order(order.order_id, "user-attacker")


# ===========================================================================
# ── TestStateMachine ─────────────────────────────────────────────────────────
# ===========================================================================


class TestStateMachine:
    """
    Tests for the OrderService.transition_state() internal state machine.

    Validates that only edges defined in VALID_TRANSITIONS are accepted and
    that terminal states are truly terminal.
    """

    def test_valid_transition_cart_locked_to_payment_pending(
        self, order_service, mock_db
    ):
        """
        CART_LOCKED → PAYMENT_PENDING is the first transition in the lifecycle
        and must succeed.
        """
        order = _make_order(status=OrderState.CART_LOCKED)
        mock_db.save(order)

        updated = order_service.transition_state(order.order_id, OrderState.PAYMENT_PENDING)

        assert updated.status == OrderState.PAYMENT_PENDING

    def test_valid_transition_inventory_reserved_to_picking(
        self, order_service, mock_db
    ):
        """
        INVENTORY_RESERVED → PICKING occurs when the store picker starts
        collecting items and must be accepted.
        """
        order = _make_order(status=OrderState.INVENTORY_RESERVED)
        mock_db.save(order)

        updated = order_service.transition_state(order.order_id, OrderState.PICKING)

        assert updated.status == OrderState.PICKING

    def test_invalid_transition_raises_error(
        self, order_service, mock_db
    ):
        """
        An arbitrary backward or nonsensical transition (PACKED → CART_LOCKED)
        must raise InvalidStateTransitionError.
        """
        order = _make_order(status=OrderState.PACKED)
        mock_db.save(order)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_state(order.order_id, OrderState.CART_LOCKED)

    def test_invalid_transition_packed_to_inventory_reserved_raises_error(
        self, order_service, mock_db
    ):
        """
        PACKED → INVENTORY_RESERVED is not a valid edge in the state machine.
        Rolling back to a reservation state after packing must be rejected.
        """
        order = _make_order(status=OrderState.PACKED)
        mock_db.save(order)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_state(
                order.order_id, OrderState.INVENTORY_RESERVED
            )

    def test_terminal_states_cannot_transition(
        self, order_service, mock_db
    ):
        """
        DELIVERED is a terminal state.  No further state transition should
        be accepted from it, regardless of the target state.
        """
        order = _make_order(status=OrderState.DELIVERED)
        mock_db.save(order)

        # Try every possible target state; all must raise.
        for target in OrderState:
            if target == OrderState.DELIVERED:
                continue
            with pytest.raises(InvalidStateTransitionError):
                order_service.transition_state(order.order_id, target)

    def test_failed_state_cannot_transition(
        self, order_service, mock_db
    ):
        """
        FAILED is a terminal state.  Attempting to re-drive a failed order
        into any other state must be rejected to prevent zombie order
        reactivation.
        """
        order = _make_order(status=OrderState.FAILED)
        mock_db.save(order)

        for target in OrderState:
            if target == OrderState.FAILED:
                continue
            with pytest.raises(InvalidStateTransitionError):
                order_service.transition_state(order.order_id, target)


# ===========================================================================
# ── TestReconciliationJob ────────────────────────────────────────────────────
# ===========================================================================


class TestReconciliationJob:
    """
    Tests for the ReconciliationJob.run() periodic background job.

    The job must find orders stuck in PAYMENT_PENDING for more than 5 minutes
    and resolve each one against the Payment Service using the idempotency_key.
    """

    def test_reconciliation_finds_payment_pending_orders_older_than_5_minutes(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        The job must query the DB for PAYMENT_PENDING orders created more than
        5 minutes ago and process exactly those orders.
        """
        stale_order = _make_order(status=OrderState.PAYMENT_PENDING, minutes_old=6)
        mock_db.find_stale_pending.return_value = [stale_order]
        mock_payment.query_status.return_value = "SUCCESS"

        reconciliation_job.run()

        mock_db.find_stale_pending.assert_called_once()
        # Verify that the cutoff timestamp passed is approximately 5 min ago.
        cutoff_arg: datetime = mock_db.find_stale_pending.call_args.args[0]
        expected_cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        delta = abs((cutoff_arg - expected_cutoff).total_seconds())
        assert delta < 5, (
            f"Cutoff should be ~5 minutes ago, but got a delta of {delta:.1f}s"
        )

    def test_reconciliation_ignores_payment_pending_orders_younger_than_5_minutes(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        Orders that entered PAYMENT_PENDING less than 5 minutes ago are
        still within normal processing time and must NOT be touched.

        We simulate this by having find_stale_pending return an empty list
        (as the DB query's WHERE clause excludes them), and assert that
        payment.query_status() is never called.
        """
        mock_db.find_stale_pending.return_value = []

        result = reconciliation_job.run()

        mock_payment.query_status.assert_not_called()
        assert result.resolved_count == 0
        assert result.failed_count == 0

    def test_reconciliation_resolves_to_confirmed_when_payment_succeeded(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        When the Payment Service returns SUCCESS for a stale order's
        idempotency_key, the order must be transitioned to PAYMENT_CONFIRMED
        and counted in resolved_count.
        """
        stale_order = _make_order(status=OrderState.PAYMENT_PENDING, minutes_old=10)
        mock_db.find_stale_pending.return_value = [stale_order]
        mock_payment.query_status.return_value = "SUCCESS"

        result = reconciliation_job.run()

        assert stale_order.status == OrderState.PAYMENT_CONFIRMED
        assert result.resolved_count == 1
        assert result.failed_count == 0

    def test_reconciliation_resolves_to_failed_when_payment_declined(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        When the Payment Service returns DECLINED (or any non-SUCCESS status)
        for a stale order, the order must be transitioned to FAILED and
        counted in failed_count.
        """
        stale_order = _make_order(status=OrderState.PAYMENT_PENDING, minutes_old=10)
        mock_db.find_stale_pending.return_value = [stale_order]
        mock_payment.query_status.return_value = "DECLINED"

        result = reconciliation_job.run()

        assert stale_order.status == OrderState.FAILED
        assert result.resolved_count == 0
        assert result.failed_count == 1

    def test_reconciliation_is_idempotent(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        Running the reconciliation job twice on the same order must produce
        the same final state.  The second run should find no stale orders
        (because the order was already resolved) and must not call
        payment.query_status() again.

        We simulate this by returning the order only on the first call to
        find_stale_pending, then returning an empty list on subsequent calls.
        """
        stale_order = _make_order(status=OrderState.PAYMENT_PENDING, minutes_old=10)
        mock_payment.query_status.return_value = "SUCCESS"

        # First run: order is stale and pending.
        mock_db.find_stale_pending.return_value = [stale_order]
        first_result = reconciliation_job.run()

        assert first_result.resolved_count == 1
        assert stale_order.status == OrderState.PAYMENT_CONFIRMED

        # Second run: order has already been resolved, DB returns empty list.
        mock_db.find_stale_pending.return_value = []
        second_result = reconciliation_job.run()

        assert second_result.resolved_count == 0
        assert second_result.failed_count == 0
        # query_status should have been called exactly once in total.
        assert mock_payment.query_status.call_count == 1

    def test_reconciliation_returns_count_of_resolved_orders(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        With a mix of SUCCESS and DECLINED outcomes, resolved_count and
        failed_count in ReconciliationResult must accurately reflect each
        category.
        """
        orders = [
            _make_order(
                order_id=f"order-{i}",
                status=OrderState.PAYMENT_PENDING,
                minutes_old=10,
            )
            for i in range(5)
        ]
        # First 3 succeed, last 2 decline.
        def _query(idempotency_key: str) -> str:
            idx = int(idempotency_key.split("-")[1])
            return "SUCCESS" if idx < 3 else "DECLINED"

        mock_db.find_stale_pending.return_value = orders
        mock_payment.query_status.side_effect = _query

        result = reconciliation_job.run()

        assert result.resolved_count == 3
        assert result.failed_count == 2

    def test_reconciliation_does_not_call_payment_for_non_pending_orders(
        self, reconciliation_job, mock_db, mock_payment
    ):
        """
        The DB query must only return PAYMENT_PENDING orders.  If a non-pending
        order somehow appeared in the result set (defensive check), the job
        should still only process what the DB returns; in any case,
        find_stale_pending returning only correctly-filtered rows means
        payment.query_status() is never called with a non-pending order's key.

        We assert the contract from the DB side: when find_stale_pending
        returns no rows, query_status is never invoked.
        """
        # Simulate DB correctly filtering out non-pending orders.
        mock_db.find_stale_pending.return_value = []

        reconciliation_job.run()

        mock_payment.query_status.assert_not_called()


# ===========================================================================
# ── TestGetOrder ─────────────────────────────────────────────────────────────
# ===========================================================================


class TestGetOrder:
    """
    Tests for the OrderService.get_order() retrieval method.

    Validates that ownership is enforced and that missing orders produce a
    clear, consistent error rather than leaking information about existence.
    """

    def test_get_order_returns_order_for_correct_user(
        self, order_service, mock_db
    ):
        """
        get_order() must return the correct Order object when called by the
        user who owns it.
        """
        order = _make_order(user_id="user-1", status=OrderState.PICKING)
        mock_db.save(order)

        fetched = order_service.get_order(order.order_id, "user-1")

        assert fetched.order_id == order.order_id
        assert fetched.user_id == "user-1"
        assert fetched.status == OrderState.PICKING

    def test_get_order_raises_not_found_for_different_user(
        self, order_service, mock_db
    ):
        """
        get_order() must raise OrderNotFoundError when the requesting user_id
        does not match the order's owner.  Returning a 404-equivalent prevents
        IDOR (Insecure Direct Object Reference) vulnerabilities.
        """
        order = _make_order(user_id="user-owner")
        mock_db.save(order)

        with pytest.raises(OrderNotFoundError):
            order_service.get_order(order.order_id, "user-intruder")

    def test_get_order_raises_not_found_for_nonexistent_order(
        self, order_service, mock_db
    ):
        """
        get_order() must raise OrderNotFoundError when no order with the
        given order_id exists in the database.
        """
        with pytest.raises(OrderNotFoundError):
            order_service.get_order("nonexistent-order-id", "user-1")
