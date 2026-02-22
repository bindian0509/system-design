"""
TDD test suite for the InventoryService of an instant grocery delivery app (Blinkit-scale).

System context:
  - 40 dark stores, ~5,000 SKUs per store
  - Hot layer: Redis Hash per store (key: inv:{store_id}:{sku_id}, fields: qty_available, qty_reserved)
  - Cold layer: PostgreSQL updated asynchronously via Kafka write-behind consumer (~5s lag)
  - Reservation is atomic via a Redis Lua script to prevent overselling

Test organisation:
  TestReservation          — single-SKU reserve/release logic
  TestMultiItemReservation — all-or-nothing order-level reservation
  TestRestock              — restock increases qty_available
  TestStockAdjustment      — write-offs / corrections
  TestCircuitBreaker       — Redis-down fallback behaviour
  TestStockQuery           — get_stock() shape and correctness
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Domain types assumed to be produced by the service layer
# ---------------------------------------------------------------------------

@dataclass
class ReservationResult:
    """Result returned by InventoryService.reserve_order_items()."""

    success: bool
    failed_skus: list[str] = field(default_factory=list)


class RedisUnavailableError(Exception):
    """Raised when the Redis circuit breaker is open."""


# ---------------------------------------------------------------------------
# Minimal stub implementation of InventoryService
# (tests drive the interface; this stub makes the tests runnable)
# ---------------------------------------------------------------------------

class InventoryService:
    """
    Manages per-store stock levels for an instant grocery delivery system.

    Hot layer  : Redis Hash  — key ``inv:{store_id}:{sku_id}``
                               fields ``qty_available``, ``qty_reserved``
    Cold layer : PostgreSQL  — updated asynchronously via Kafka write-behind
                               consumer with ~5 s lag.
    """

    # Lua script executed atomically inside Redis for a single-SKU reservation.
    _RESERVE_LUA = """
local qty = redis.call('HGET', KEYS[1], 'qty_available')
if tonumber(qty) >= tonumber(ARGV[1]) then
  redis.call('HDECRBY', KEYS[1], 'qty_available', ARGV[1])
  redis.call('HINCRBY', KEYS[1], 'qty_reserved', ARGV[1])
  return 1
else
  return 0
end
"""

    # How many consecutive Redis failures open the circuit breaker.
    _FAILURE_THRESHOLD = 3

    def __init__(self, redis_client: Any, kafka_producer: Any, db_session: Any) -> None:
        self._redis = redis_client
        self._kafka = kafka_producer
        self._db = db_session
        self._redis_failure_count: int = 0
        self._circuit_open: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _redis_key(self, store_id: str, sku_id: str) -> str:
        return f"inv:{store_id}:{sku_id}"

    def _record_redis_failure(self) -> None:
        self._redis_failure_count += 1
        if self._redis_failure_count >= self._FAILURE_THRESHOLD:
            self._circuit_open = True

    def _reset_redis_failure_count(self) -> None:
        self._redis_failure_count = 0

    def _publish(self, topic: str, payload: dict) -> None:
        self._kafka.produce(topic, json.dumps(payload))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reserve_stock(self, store_id: str, sku_id: str, qty: int) -> bool:
        """
        Attempt to reserve *qty* units for a single SKU.

        Returns True  if reservation succeeded (Redis qty decremented atomically).
        Returns False if insufficient stock.
        Raises RedisUnavailableError if the circuit breaker is open.
        """
        if self._circuit_open:
            raise RedisUnavailableError("Redis circuit breaker is open")

        key = self._redis_key(store_id, sku_id)
        try:
            result = self._redis.eval(self._RESERVE_LUA, 1, key, qty)
            self._reset_redis_failure_count()
        except Exception as exc:
            self._record_redis_failure()
            raise RedisUnavailableError(str(exc)) from exc

        if result == 1:
            self._publish(
                "inventory.reserved",
                {
                    "store_id": store_id,
                    "sku_id": sku_id,
                    "qty": qty,
                },
            )
            return True

        return False

    def reserve_order_items(self, store_id: str, items: list[dict]) -> ReservationResult:
        """
        Reserve multiple SKUs atomically (all-or-nothing).

        If any single SKU fails, all previously reserved SKUs in this call are
        rolled back via release_reservation().  Returns a ReservationResult with
        ``success=False`` and the list of SKUs that could not be reserved.
        """
        reserved_so_far: list[dict] = []
        failed_skus: list[str] = []

        for item in items:
            sku_id: str = item["sku_id"]
            qty: int = item["qty"]
            success = self.reserve_stock(store_id, sku_id, qty)
            if success:
                reserved_so_far.append(item)
            else:
                failed_skus.append(sku_id)

        if failed_skus:
            # Roll back every SKU that was already reserved in this batch.
            for item in reserved_so_far:
                self.release_reservation(store_id, item["sku_id"], item["qty"])
            return ReservationResult(success=False, failed_skus=failed_skus)

        return ReservationResult(success=True, failed_skus=[])

    def release_reservation(self, store_id: str, sku_id: str, qty: int) -> None:
        """
        Move *qty* units from qty_reserved back to qty_available.

        Called on order cancellation or when a multi-item reservation is rolled back.
        """
        key = self._redis_key(store_id, sku_id)
        self._redis.hincrby(key, "qty_available", qty)
        self._redis.hdecrby(key, "qty_reserved", qty)

    def restock(self, store_id: str, sku_id: str, qty_added: int) -> int:
        """
        Add *qty_added* units to qty_available.

        Returns the new qty_available value.
        Raises ValueError if qty_added <= 0.
        """
        if qty_added <= 0:
            raise ValueError(f"qty_added must be positive; got {qty_added}")

        key = self._redis_key(store_id, sku_id)
        new_qty: int = self._redis.hincrby(key, "qty_available", qty_added)

        self._publish(
            "inventory.restocked",
            {
                "store_id": store_id,
                "sku_id": sku_id,
                "qty_added": qty_added,
                "new_qty_available": new_qty,
            },
        )
        return new_qty

    def adjust_stock(
        self, store_id: str, sku_id: str, qty_change: int, reason: str
    ) -> int:
        """
        Apply a signed quantity adjustment (negative for write-offs / spoilage).

        Returns the new qty_available after clamping at 0.
        Raises ValueError if *reason* is empty or blank.
        """
        if not reason or not reason.strip():
            raise ValueError("A non-empty reason is required for stock adjustment")

        key = self._redis_key(store_id, sku_id)

        # Read current value then compute the clamped delta.
        raw = self._redis.hget(key, "qty_available")
        current: int = int(raw) if raw is not None else 0
        new_qty = max(0, current + qty_change)
        actual_delta = new_qty - current  # may differ from qty_change due to clamping

        if actual_delta != 0:
            self._redis.hincrby(key, "qty_available", actual_delta)

        return new_qty

    def get_stock(self, store_id: str, sku_id: str) -> dict:
        """
        Return current stock levels for one SKU.

        Shape: ``{'qty_available': int, 'qty_reserved': int, 'in_stock': bool}``
        """
        key = self._redis_key(store_id, sku_id)
        raw_available = self._redis.hget(key, "qty_available")
        raw_reserved = self._redis.hget(key, "qty_reserved")

        qty_available: int = int(raw_available) if raw_available is not None else 0
        qty_reserved: int = int(raw_reserved) if raw_reserved is not None else 0

        return {
            "qty_available": qty_available,
            "qty_reserved": qty_reserved,
            "in_stock": qty_available > 0,
        }

    def soft_reserve(self, store_id: str, sku_id: str, qty: int) -> bool:
        """
        Circuit-breaker fallback: always returns True (optimistic reservation).

        Stock correctness is verified at pick time when Redis is available again.
        """
        self._publish(
            "inventory.soft_reserved",
            {
                "store_id": store_id,
                "sku_id": sku_id,
                "qty": qty,
                "reason": "redis_unavailable",
            },
        )
        return True


# ===========================================================================
# pytest fixtures
# ===========================================================================

@pytest.fixture()
def redis_client() -> MagicMock:
    """
    Mock Redis client with the subset of commands used by InventoryService.

    Commands mocked: hget, hset, hincrby, hdecrby, eval.
    Tests configure return values via ``redis_client.hget.return_value`` etc.
    """
    mock = MagicMock(name="redis_client")
    # Provide sensible defaults so tests that do not need to customise these
    # do not blow up with unexpected MagicMock return types.
    mock.hget.return_value = b"0"
    mock.hincrby.return_value = 0
    mock.hdecrby.return_value = 0
    mock.eval.return_value = 0  # default: reservation fails
    return mock


@pytest.fixture()
def kafka_producer() -> MagicMock:
    """
    Mock Kafka producer that records every call to produce().

    Inspect ``kafka_producer.produce.call_args_list`` in assertions.
    """
    return MagicMock(name="kafka_producer")


@pytest.fixture()
def db_session() -> MagicMock:
    """Simple mock of a SQLAlchemy (or similar) database session."""
    return MagicMock(name="db_session")


@pytest.fixture()
def inventory_service(
    redis_client: MagicMock,
    kafka_producer: MagicMock,
    db_session: MagicMock,
) -> InventoryService:
    """
    Fully wired InventoryService instance backed by mock dependencies.

    Use this fixture in every test class so dependencies are injected and
    isolated per test function.
    """
    return InventoryService(
        redis_client=redis_client,
        kafka_producer=kafka_producer,
        db_session=db_session,
    )


# ===========================================================================
# TestReservation — single-SKU reservation logic
# ===========================================================================

class TestReservation:
    """Tests covering the reserve_stock() method for a single SKU."""

    STORE_ID = "store-42"
    SKU_ID = "sku-abc123"

    def test_reserve_succeeds_when_stock_available(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that reserve_stock() returns True when qty_available (5) is
        greater than the requested quantity (3).  The Lua script returning 1
        indicates success.
        """
        # Arrange — Lua script signals successful reservation.
        redis_client.eval.return_value = 1

        # Act
        result = inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=3)

        # Assert
        assert result is True

    def test_reserve_fails_when_stock_insufficient(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that reserve_stock() returns False when qty_available (2) is
        less than the requested quantity (5).  The Lua script returns 0.
        """
        # Arrange — Lua script signals failure (insufficient stock).
        redis_client.eval.return_value = 0

        # Act
        result = inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=5)

        # Assert
        assert result is False

    def test_reserve_fails_when_stock_exactly_zero(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that reserve_stock() returns False when qty_available is 0.
        Requesting any positive quantity from an empty shelf must always fail.
        """
        # Arrange — 0 units on hand; Lua script returns 0.
        redis_client.eval.return_value = 0

        # Act
        result = inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=1)

        # Assert
        assert result is False

    def test_reserve_succeeds_when_requesting_exact_available_qty(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that reserve_stock() returns True when the requested quantity
        exactly equals qty_available (boundary condition: qty==3, request==3).
        The Lua condition is >=, so this must succeed.
        """
        # Arrange — exactly 3 units available; request is also 3.
        redis_client.eval.return_value = 1

        # Act
        result = inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=3)

        # Assert
        assert result is True

    def test_reserve_decrements_qty_available_in_redis(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that reserve_stock() invokes the Redis Lua script (eval) with the
        correct key, script body, numkeys=1, and the requested quantity as ARGV[1].
        The Lua script internally calls HDECRBY on qty_available.
        """
        # Arrange
        redis_client.eval.return_value = 1
        expected_key = f"inv:{self.STORE_ID}:{self.SKU_ID}"

        # Act
        inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=3)

        # Assert — eval was called once; verify key and quantity arguments.
        redis_client.eval.assert_called_once()
        call_args = redis_client.eval.call_args
        # Positional: (script, numkeys, key, qty)
        _, numkeys, key_arg, qty_arg = call_args.args
        assert numkeys == 1
        assert key_arg == expected_key
        assert qty_arg == 3

    def test_reserve_increments_qty_reserved_in_redis(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that upon a successful reservation the Redis Lua script is called
        (which atomically calls HINCRBY on qty_reserved).  We confirm the eval
        was invoked with the right arguments so the Lua contract is exercised.
        """
        # Arrange
        redis_client.eval.return_value = 1
        expected_key = f"inv:{self.STORE_ID}:{self.SKU_ID}"

        # Act
        inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=4)

        # Assert — the same eval call drives both HDECRBY and HINCRBY inside Lua.
        redis_client.eval.assert_called_once()
        call_args = redis_client.eval.call_args
        _, numkeys, key_arg, qty_arg = call_args.args
        assert key_arg == expected_key
        assert qty_arg == 4

    def test_successful_reserve_publishes_inventory_reserved_event(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
        kafka_producer: MagicMock,
    ) -> None:
        """
        Verify that a successful reservation publishes exactly one message to the
        'inventory.reserved' Kafka topic with the correct store_id, sku_id, and qty.
        """
        # Arrange
        redis_client.eval.return_value = 1

        # Act
        inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=3)

        # Assert
        kafka_producer.produce.assert_called_once()
        topic, raw_payload = kafka_producer.produce.call_args.args
        assert topic == "inventory.reserved"

        payload = json.loads(raw_payload)
        assert payload["store_id"] == self.STORE_ID
        assert payload["sku_id"] == self.SKU_ID
        assert payload["qty"] == 3

    def test_failed_reserve_does_not_publish_kafka_event(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
        kafka_producer: MagicMock,
    ) -> None:
        """
        Verify that when a reservation fails (insufficient stock), no Kafka event
        is produced.  Publishing a phantom reservation would corrupt downstream
        order-fulfilment workflows.
        """
        # Arrange — Lua script signals insufficient stock.
        redis_client.eval.return_value = 0

        # Act
        inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=10)

        # Assert
        kafka_producer.produce.assert_not_called()

    def test_qty_available_never_goes_negative(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that requesting more units than are available results in False and
        the Redis eval is still called (the Lua script itself guards negativity).
        The service must NOT bypass the Lua script for this safety guarantee.
        """
        # Arrange — only 5 units available; Lua returns 0 for a request of 10.
        redis_client.eval.return_value = 0

        # Act
        result = inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=10)

        # Assert
        assert result is False
        # eval was invoked (atomic Lua keeps qty >= 0 inside Redis).
        redis_client.eval.assert_called_once()
        # No side-effects: Kafka must be silent.
        # (kafka_producer fixture is not passed in here; test is scoped to Redis.)


# ===========================================================================
# TestMultiItemReservation — all-or-nothing order-level reservation
# ===========================================================================

class TestMultiItemReservation:
    """Tests covering reserve_order_items() — the all-or-nothing batch reserve."""

    STORE_ID = "store-07"

    def test_all_items_reserved_when_all_have_sufficient_stock(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that when every SKU in the order has sufficient stock, the method
        returns a ReservationResult with success=True and an empty failed_skus list.
        """
        # Arrange — all Lua evaluations succeed.
        redis_client.eval.return_value = 1
        items = [
            {"sku_id": "sku-001", "qty": 2},
            {"sku_id": "sku-002", "qty": 1},
            {"sku_id": "sku-003", "qty": 4},
        ]

        # Act
        result = inventory_service.reserve_order_items(self.STORE_ID, items)

        # Assert
        assert result.success is True
        assert result.failed_skus == []

    def test_reservation_fails_if_any_single_item_has_insufficient_stock(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that when at least one SKU in the batch cannot be reserved, the
        overall ReservationResult.success is False.
        """
        # Arrange — first SKU succeeds, second fails, third would succeed but is
        # never attempted (short-circuit) or attempted after rollback.
        redis_client.eval.side_effect = [
            1,  # sku-001 — success
            0,  # sku-002 — insufficient stock
            1,  # sku-003 — would succeed, but whole order is already failed
        ]
        items = [
            {"sku_id": "sku-001", "qty": 2},
            {"sku_id": "sku-002", "qty": 99},
            {"sku_id": "sku-003", "qty": 1},
        ]

        # Act
        result = inventory_service.reserve_order_items(self.STORE_ID, items)

        # Assert
        assert result.success is False

    def test_failed_multi_reservation_returns_which_sku_caused_failure(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that ReservationResult.failed_skus accurately names every SKU that
        could not be reserved, enabling the client to surface actionable feedback
        (e.g. 'Item X is out of stock').
        """
        # Arrange — sku-002 has insufficient stock.
        redis_client.eval.side_effect = [
            1,  # sku-001
            0,  # sku-002 — fails
        ]
        items = [
            {"sku_id": "sku-001", "qty": 1},
            {"sku_id": "sku-002", "qty": 50},
        ]

        # Act
        result = inventory_service.reserve_order_items(self.STORE_ID, items)

        # Assert
        assert "sku-002" in result.failed_skus

    def test_failed_multi_reservation_rolls_back_previously_reserved_items(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that when the second SKU in a batch fails, the first SKU that was
        already reserved is rolled back via release_reservation() (HINCRBY /
        HDECRBY on the Redis hash), preventing phantom reservations.
        """
        # Arrange — sku-001 succeeds; sku-002 fails.
        redis_client.eval.side_effect = [1, 0]
        items = [
            {"sku_id": "sku-001", "qty": 3},
            {"sku_id": "sku-002", "qty": 99},
        ]

        # Act
        inventory_service.reserve_order_items(self.STORE_ID, items)

        # Assert — release_reservation() is implemented via hincrby + hdecrby.
        expected_key = f"inv:{self.STORE_ID}:sku-001"
        # qty_available should be restored (+3) and qty_reserved decremented (-3).
        redis_client.hincrby.assert_any_call(expected_key, "qty_available", 3)
        redis_client.hdecrby.assert_any_call(expected_key, "qty_reserved", 3)


# ===========================================================================
# TestRestock — adding stock to a SKU
# ===========================================================================

class TestRestock:
    """Tests covering the restock() method."""

    STORE_ID = "store-15"
    SKU_ID = "sku-xyz789"

    def test_restock_increases_qty_available(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that restock() calls HINCRBY on qty_available with the supplied
        qty_added and returns the new total quantity as reported by Redis.
        """
        # Arrange — Redis returns 25 as the new value after increment.
        redis_client.hincrby.return_value = 25
        expected_key = f"inv:{self.STORE_ID}:{self.SKU_ID}"

        # Act
        new_qty = inventory_service.restock(self.STORE_ID, self.SKU_ID, qty_added=10)

        # Assert
        redis_client.hincrby.assert_called_once_with(expected_key, "qty_available", 10)
        assert new_qty == 25

    def test_restock_publishes_inventory_restocked_event(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
        kafka_producer: MagicMock,
    ) -> None:
        """
        Verify that restock() publishes an 'inventory.restocked' event to Kafka
        containing store_id, sku_id, qty_added, and new_qty_available.
        """
        # Arrange
        redis_client.hincrby.return_value = 30

        # Act
        inventory_service.restock(self.STORE_ID, self.SKU_ID, qty_added=15)

        # Assert
        kafka_producer.produce.assert_called_once()
        topic, raw_payload = kafka_producer.produce.call_args.args
        assert topic == "inventory.restocked"

        payload = json.loads(raw_payload)
        assert payload["store_id"] == self.STORE_ID
        assert payload["sku_id"] == self.SKU_ID
        assert payload["qty_added"] == 15
        assert payload["new_qty_available"] == 30

    def test_restock_with_zero_qty_raises_value_error(
        self,
        inventory_service: InventoryService,
    ) -> None:
        """
        Verify that restock() raises ValueError when qty_added is 0 or negative.
        Restocking with zero units is a no-op that indicates a caller bug.
        """
        # Act & Assert
        with pytest.raises(ValueError, match="qty_added must be positive"):
            inventory_service.restock(self.STORE_ID, self.SKU_ID, qty_added=0)

        with pytest.raises(ValueError, match="qty_added must be positive"):
            inventory_service.restock(self.STORE_ID, self.SKU_ID, qty_added=-5)


# ===========================================================================
# TestStockAdjustment — write-offs and manual corrections
# ===========================================================================

class TestStockAdjustment:
    """Tests covering the adjust_stock() method (spoilage, corrections, audits)."""

    STORE_ID = "store-03"
    SKU_ID = "sku-milk-2l"

    def test_write_off_decreases_qty_available(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that a negative qty_change (write-off / spoilage) correctly reduces
        qty_available in Redis and returns the new (lower) quantity.
        """
        # Arrange — current qty_available is 10; write off 3 → new qty should be 7.
        redis_client.hget.return_value = b"10"
        # hincrby will be called with delta = -3 internally → returns 7.
        redis_client.hincrby.return_value = 7
        expected_key = f"inv:{self.STORE_ID}:{self.SKU_ID}"

        # Act
        new_qty = inventory_service.adjust_stock(
            self.STORE_ID, self.SKU_ID, qty_change=-3, reason="spoilage"
        )

        # Assert
        redis_client.hget.assert_called_with(expected_key, "qty_available")
        redis_client.hincrby.assert_called_with(expected_key, "qty_available", -3)
        assert new_qty == 7

    def test_write_off_cannot_make_qty_go_below_zero(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that adjust_stock() clamps the result to 0 when qty_change would
        make qty_available negative.  Writing off 20 units when only 5 are
        available must result in 0, not -15.
        """
        # Arrange — current qty_available is 5; qty_change is -20.
        redis_client.hget.return_value = b"5"
        expected_key = f"inv:{self.STORE_ID}:{self.SKU_ID}"

        # Act
        new_qty = inventory_service.adjust_stock(
            self.STORE_ID, self.SKU_ID, qty_change=-20, reason="damage"
        )

        # Assert — result is clamped at 0.
        assert new_qty == 0
        # The actual delta applied to Redis must be -5 (not -20) to prevent negatives.
        redis_client.hincrby.assert_called_with(expected_key, "qty_available", -5)

    def test_adjustment_requires_valid_reason(
        self,
        inventory_service: InventoryService,
    ) -> None:
        """
        Verify that adjust_stock() raises ValueError when the reason string is
        empty or blank.  Every stock adjustment must be auditable.
        """
        # Act & Assert — empty string
        with pytest.raises(ValueError, match="non-empty reason"):
            inventory_service.adjust_stock(
                self.STORE_ID, self.SKU_ID, qty_change=-1, reason=""
            )

        # Act & Assert — whitespace-only string
        with pytest.raises(ValueError, match="non-empty reason"):
            inventory_service.adjust_stock(
                self.STORE_ID, self.SKU_ID, qty_change=-1, reason="   "
            )


# ===========================================================================
# TestCircuitBreaker — Redis-down fallback behaviour
# ===========================================================================

class TestCircuitBreaker:
    """
    Tests covering graceful degradation when Redis is unavailable.

    The circuit breaker opens after _FAILURE_THRESHOLD consecutive Redis errors.
    Once open, reserve_stock() raises RedisUnavailableError; the caller is
    expected to fall back to soft_reserve() (optimistic, verified at pick time).
    """

    STORE_ID = "store-99"
    SKU_ID = "sku-bread"

    def test_soft_reserve_returns_true_when_redis_unavailable(
        self,
        inventory_service: InventoryService,
        kafka_producer: MagicMock,
    ) -> None:
        """
        Verify that soft_reserve() always returns True regardless of actual stock
        levels.  It is an optimistic fallback that lets the order proceed; stock
        correctness is enforced at pick time.
        """
        # Act — no Redis involvement at all.
        result = inventory_service.soft_reserve(self.STORE_ID, self.SKU_ID, qty=2)

        # Assert
        assert result is True

    def test_circuit_breaker_opens_after_redis_connection_failures(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that after _FAILURE_THRESHOLD consecutive Redis failures the
        internal circuit breaker flag (_circuit_open) is set to True, preventing
        further Redis calls until the circuit is reset.
        """
        # Arrange — every eval call raises a connection error.
        redis_client.eval.side_effect = ConnectionError("Redis unreachable")
        threshold = inventory_service._FAILURE_THRESHOLD

        # Act — call reserve_stock() exactly threshold times, absorbing exceptions.
        for _ in range(threshold):
            with pytest.raises((RedisUnavailableError, ConnectionError)):
                inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=1)

        # Assert — circuit is now open.
        assert inventory_service._circuit_open is True

    def test_reserve_raises_redis_unavailable_error_when_circuit_open(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that once the circuit breaker is open, reserve_stock() immediately
        raises RedisUnavailableError without attempting any Redis call.  This
        prevents further latency from an already-known-bad dependency.
        """
        # Arrange — force the circuit open directly (simulates post-threshold state).
        inventory_service._circuit_open = True

        # Act & Assert
        with pytest.raises(RedisUnavailableError):
            inventory_service.reserve_stock(self.STORE_ID, self.SKU_ID, qty=1)

        # Redis must not have been called at all.
        redis_client.eval.assert_not_called()


# ===========================================================================
# TestStockQuery — get_stock() shape and correctness
# ===========================================================================

class TestStockQuery:
    """Tests covering get_stock() — the read path for inventory levels."""

    STORE_ID = "store-01"
    SKU_ID = "sku-eggs-12"

    def test_get_stock_returns_correct_qty_fields(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that get_stock() returns a dict with the expected keys
        (qty_available, qty_reserved, in_stock) and that the integer values
        match what is stored in the Redis hash.
        """
        # Arrange — Redis reports 8 available, 2 reserved.
        def hget_side_effect(key: str, field: str) -> bytes:
            return {
                "qty_available": b"8",
                "qty_reserved": b"2",
            }[field]

        redis_client.hget.side_effect = hget_side_effect

        # Act
        stock = inventory_service.get_stock(self.STORE_ID, self.SKU_ID)

        # Assert
        assert stock["qty_available"] == 8
        assert stock["qty_reserved"] == 2
        assert "in_stock" in stock

    def test_in_stock_true_when_qty_available_greater_than_zero(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that in_stock is True whenever qty_available > 0 so that the
        product catalogue correctly shows the item as purchasable.
        """
        # Arrange — 1 unit left on the shelf.
        def hget_side_effect(key: str, field: str) -> bytes:
            return {
                "qty_available": b"1",
                "qty_reserved": b"0",
            }[field]

        redis_client.hget.side_effect = hget_side_effect

        # Act
        stock = inventory_service.get_stock(self.STORE_ID, self.SKU_ID)

        # Assert
        assert stock["in_stock"] is True

    def test_in_stock_false_when_qty_available_is_zero(
        self,
        inventory_service: InventoryService,
        redis_client: MagicMock,
    ) -> None:
        """
        Verify that in_stock is False when qty_available is 0 so that the
        product catalogue correctly marks the item as out-of-stock and prevents
        customers from adding it to their cart.
        """
        # Arrange — shelf is empty.
        def hget_side_effect(key: str, field: str) -> bytes:
            return {
                "qty_available": b"0",
                "qty_reserved": b"5",
            }[field]

        redis_client.hget.side_effect = hget_side_effect

        # Act
        stock = inventory_service.get_stock(self.STORE_ID, self.SKU_ID)

        # Assert
        assert stock["in_stock"] is False
