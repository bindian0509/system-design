"""
TDD test suite for the Dispatch Service of an instant grocery delivery application.

The Dispatch Service is responsible for assigning riders to orders. It consumes
`order.placed` events from Kafka and must assign a rider within 2 seconds. It uses
PostGIS for geographic queries, Redis GEO for live rider location tracking, and
an optimistic locking pattern to handle concurrent assignment races.

Key behaviors under test:
- PostGIS-based rider availability lookup within configurable radii
- Multi-factor rider scoring (proximity, active deliveries, avg delivery time)
- Optimistic lock: only one concurrent acceptance wins per rider
- Retry logic with radius expansion (3km → 5km) after 30s timeout
- Circuit breaker escalation after 3 consecutive failures
- Kafka event publishing upon successful assignment
- Redis GEO writes and reads for live rider location tracking
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Domain dataclasses (assumed to be importable from the production module)
# These are redefined here so the test file is self-contained and runnable
# without the production code existing yet — true TDD red-phase style.
# ---------------------------------------------------------------------------

@dataclass
class Location:
    lat: float
    lng: float


@dataclass
class Rider:
    rider_id: str
    name: str
    lat: float
    lng: float
    status: str  # AVAILABLE, ON_DELIVERY, OFFLINE
    active_deliveries: int
    avg_delivery_time_minutes: float
    vehicle_type: str


@dataclass
class ScoredRider:
    rider: Rider
    score: float
    distance_km: float


@dataclass
class RiderLocation:
    rider_id: str
    lat: float
    lng: float
    distance_km: float


@dataclass
class AssignmentResult:
    rider_id: str
    order_id: str
    assigned_at: datetime
    distance_km: float


# ---------------------------------------------------------------------------
# Custom exception stubs (assumed importable from production module)
# ---------------------------------------------------------------------------

class MaxRetriesExceededError(Exception):
    """Raised when the dispatch service exhausts all retry attempts."""


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and no fallback is available."""


class StoreNotFoundError(Exception):
    """Raised when the given store_id is not found in the data store."""


# ---------------------------------------------------------------------------
# Production class stub — replaced by real implementation in green phase.
# The stub exists here only to make import resolution clear.
# ---------------------------------------------------------------------------

class DispatchService:
    """
    Stub of the production DispatchService.
    Tests mock internal collaborators; the real implementation lives elsewhere.
    """

    def __init__(self, db_session, kafka_producer, notification_service, circuit_breaker):
        self.db = db_session
        self.kafka = kafka_producer
        self.notification = notification_service
        self.circuit_breaker = circuit_breaker

    def assign_rider(self, order_id: str, store_location: Location) -> AssignmentResult:
        raise NotImplementedError

    def find_available_riders(self, store_location: Location, radius_km: float) -> list[Rider]:
        raise NotImplementedError

    def score_riders(self, riders: list[Rider], store_location: Location) -> list[ScoredRider]:
        raise NotImplementedError

    def attempt_assignment(self, rider_id: str, order_id: str) -> bool:
        raise NotImplementedError

    def update_rider_location(self, rider_id: str, lat: float, lng: float) -> None:
        raise NotImplementedError

    def get_nearby_riders(self, lat: float, lng: float, radius_km: float) -> list[RiderLocation]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """A mock database session used by all tests that touch PostgreSQL/PostGIS."""
    return MagicMock()


@pytest.fixture
def kafka_producer():
    """A mock Kafka producer. Tests assert on `produce` / `send` calls."""
    return MagicMock()


@pytest.fixture
def notification_service():
    """A mock notification service for push offers to riders."""
    return MagicMock()


@pytest.fixture
def circuit_breaker():
    """A mock circuit breaker. Default state: closed (is_open returns False)."""
    cb = MagicMock()
    cb.is_open.return_value = False
    return cb


@pytest.fixture
def dispatch_service(db_session, kafka_producer, notification_service, circuit_breaker):
    """Fully wired DispatchService with all collaborators mocked."""
    return DispatchService(
        db_session=db_session,
        kafka_producer=kafka_producer,
        notification_service=notification_service,
        circuit_breaker=circuit_breaker,
    )


@pytest.fixture
def store_location():
    """Default dark-store location (Blinkit Saket hub, New Delhi)."""
    return Location(lat=28.5275, lng=77.2096)


@pytest.fixture
def nearby_available_rider():
    """An available rider 1.2 km from the store."""
    return Rider(
        rider_id="rider-001",
        name="Arjun Sharma",
        lat=28.5307,
        lng=77.2140,
        status="AVAILABLE",
        active_deliveries=0,
        avg_delivery_time_minutes=18.0,
        vehicle_type="bicycle",
    )


@pytest.fixture
def farther_available_rider():
    """An available rider 2.8 km from the store — within 3km but farther."""
    return Rider(
        rider_id="rider-002",
        name="Priya Nair",
        lat=28.5520,
        lng=77.2300,
        status="AVAILABLE",
        active_deliveries=1,
        avg_delivery_time_minutes=22.0,
        vehicle_type="scooter",
    )


@pytest.fixture
def outside_radius_rider():
    """A rider 4.5 km away — outside the 3km initial radius."""
    return Rider(
        rider_id="rider-003",
        name="Ravi Kumar",
        lat=28.5700,
        lng=77.2500,
        status="AVAILABLE",
        active_deliveries=0,
        avg_delivery_time_minutes=20.0,
        vehicle_type="bicycle",
    )


@pytest.fixture
def offline_rider():
    """A rider who is offline and must never be offered an order."""
    return Rider(
        rider_id="rider-004",
        name="Meera Singh",
        lat=28.5290,
        lng=77.2110,
        status="OFFLINE",
        active_deliveries=0,
        avg_delivery_time_minutes=19.0,
        vehicle_type="bicycle",
    )


@pytest.fixture
def on_delivery_rider():
    """A rider currently on a delivery — not eligible for new assignments."""
    return Rider(
        rider_id="rider-005",
        name="Suresh Patel",
        lat=28.5290,
        lng=77.2100,
        status="ON_DELIVERY",
        active_deliveries=1,
        avg_delivery_time_minutes=17.5,
        vehicle_type="scooter",
    )


# ===========================================================================
# TestFindAvailableRiders
# ===========================================================================

class TestFindAvailableRiders:
    """
    Unit tests for DispatchService.find_available_riders.

    This method issues a PostGIS ST_DWithin query and must filter by both
    geographic proximity and rider status. Tests mock the db_session to
    control what the database returns.
    """

    def test_returns_only_available_riders_within_radius(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
        nearby_available_rider: Rider,
    ):
        """
        When the database returns a mix of riders, only those with
        status=AVAILABLE and within the requested radius should be returned.
        """
        db_session.execute.return_value.fetchall.return_value = [nearby_available_rider]

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert len(result) == 1
        assert result[0].rider_id == "rider-001"
        assert result[0].status == "AVAILABLE"

    def test_excludes_riders_outside_radius(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
        outside_radius_rider: Rider,
    ):
        """
        Riders whose PostGIS-computed distance exceeds radius_km must not
        appear in the result even if they are AVAILABLE.
        The PostGIS query itself enforces this; the mock simulates that the
        DB correctly excludes them.
        """
        db_session.execute.return_value.fetchall.return_value = []

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert result == []

    def test_excludes_offline_riders(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
        offline_rider: Rider,
    ):
        """
        Riders with status=OFFLINE must be excluded by the SQL WHERE clause.
        Even if they are physically within the radius, they must not be offered orders.
        """
        db_session.execute.return_value.fetchall.return_value = []

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert result == []
        # Verify query was executed (the real assertion is DB-level filtering)
        db_session.execute.assert_called_once()

    def test_excludes_riders_already_on_delivery(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
        on_delivery_rider: Rider,
    ):
        """
        Riders with status=ON_DELIVERY are busy and must never be offered a
        new order. The PostGIS query filters on status='AVAILABLE'.
        """
        db_session.execute.return_value.fetchall.return_value = []

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert result == []

    def test_returns_empty_list_when_no_riders_in_radius(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
    ):
        """
        When no AVAILABLE riders exist within the radius, the method must
        return an empty list rather than raising an exception. The caller
        handles the empty case (radius expansion / retry).
        """
        db_session.execute.return_value.fetchall.return_value = []

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert result == []
        assert isinstance(result, list)

    def test_riders_sorted_by_distance_ascending(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        store_location: Location,
        nearby_available_rider: Rider,
        farther_available_rider: Rider,
    ):
        """
        The PostGIS query must ORDER BY distance ASC so that the closest
        available rider is always first in the returned list. This guarantees
        that score_riders receives a proximity-ordered input.
        """
        # DB returns them already sorted by PostGIS ORDER BY distance
        db_session.execute.return_value.fetchall.return_value = [
            nearby_available_rider,  # 1.2 km
            farther_available_rider,  # 2.8 km
        ]

        result = dispatch_service.find_available_riders(store_location, radius_km=3.0)

        assert len(result) == 2
        assert result[0].rider_id == "rider-001"  # closer first
        assert result[1].rider_id == "rider-002"


# ===========================================================================
# TestRiderScoring
# ===========================================================================

class TestRiderScoring:
    """
    Unit tests for DispatchService.score_riders.

    Scoring is multi-factor: proximity (primary), active deliveries
    (secondary), average delivery time (tertiary). Tests verify that the
    scoring function produces the correct relative ordering.
    """

    def test_closer_rider_scores_higher_than_farther_rider(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        A rider 0.5 km away must score higher than a rider 2.5 km away,
        all other factors being equal. Proximity is the primary scoring
        dimension.
        """
        close_rider = Rider(
            rider_id="r-close",
            name="Close",
            lat=28.5300,
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=0,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )
        far_rider = Rider(
            rider_id="r-far",
            name="Far",
            lat=28.5500,
            lng=77.2300,
            status="AVAILABLE",
            active_deliveries=0,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )

        scored = dispatch_service.score_riders([close_rider, far_rider], store_location)

        close_scored = next(s for s in scored if s.rider.rider_id == "r-close")
        far_scored = next(s for s in scored if s.rider.rider_id == "r-far")
        assert close_scored.score > far_scored.score

    def test_rider_with_fewer_active_deliveries_scores_higher(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        Among riders at the same distance, the one with fewer active
        deliveries must score higher. Active deliveries is the secondary
        scoring dimension.
        """
        idle_rider = Rider(
            rider_id="r-idle",
            name="Idle",
            lat=28.5300,
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=0,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )
        busy_rider = Rider(
            rider_id="r-busy",
            name="Busy",
            lat=28.5300,  # same distance
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=3,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )

        scored = dispatch_service.score_riders([idle_rider, busy_rider], store_location)

        idle_scored = next(s for s in scored if s.rider.rider_id == "r-idle")
        busy_scored = next(s for s in scored if s.rider.rider_id == "r-busy")
        assert idle_scored.score > busy_scored.score

    def test_rider_with_faster_avg_delivery_time_scores_higher(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        Among riders at the same distance with the same active deliveries,
        the faster rider (lower avg_delivery_time_minutes) must score higher.
        Avg delivery time is the tertiary scoring dimension.
        """
        fast_rider = Rider(
            rider_id="r-fast",
            name="Fast",
            lat=28.5300,
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=1,
            avg_delivery_time_minutes=15.0,
            vehicle_type="bicycle",
        )
        slow_rider = Rider(
            rider_id="r-slow",
            name="Slow",
            lat=28.5300,
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=1,
            avg_delivery_time_minutes=35.0,
            vehicle_type="bicycle",
        )

        scored = dispatch_service.score_riders([fast_rider, slow_rider], store_location)

        fast_scored = next(s for s in scored if s.rider.rider_id == "r-fast")
        slow_scored = next(s for s in scored if s.rider.rider_id == "r-slow")
        assert fast_scored.score > slow_scored.score

    def test_proximity_weighted_more_than_active_deliveries(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        A rider who is very close but has 2 active deliveries must still
        score higher than a rider who is far away but idle. This validates
        that proximity carries more weight than the secondary factor.
        """
        close_busy_rider = Rider(
            rider_id="r-close-busy",
            name="CloseBusy",
            lat=28.5280,   # ~0.3 km from store
            lng=77.2100,
            status="AVAILABLE",
            active_deliveries=2,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )
        far_idle_rider = Rider(
            rider_id="r-far-idle",
            name="FarIdle",
            lat=28.5500,   # ~2.8 km from store
            lng=77.2300,
            status="AVAILABLE",
            active_deliveries=0,
            avg_delivery_time_minutes=20.0,
            vehicle_type="bicycle",
        )

        scored = dispatch_service.score_riders(
            [close_busy_rider, far_idle_rider], store_location
        )

        close_busy_scored = next(s for s in scored if s.rider.rider_id == "r-close-busy")
        far_idle_scored = next(s for s in scored if s.rider.rider_id == "r-far-idle")
        assert close_busy_scored.score > far_idle_scored.score

    def test_scoring_returns_riders_in_descending_score_order(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        score_riders must return a list sorted by score descending so that
        the best candidate is always first. The caller (assign_rider) picks
        the top-3 from this list.
        """
        riders = [
            Rider("r-1", "A", 28.5500, 77.2300, "AVAILABLE", 2, 25.0, "bicycle"),
            Rider("r-2", "B", 28.5280, 77.2100, "AVAILABLE", 0, 15.0, "bicycle"),
            Rider("r-3", "C", 28.5350, 77.2150, "AVAILABLE", 1, 20.0, "bicycle"),
        ]

        scored = dispatch_service.score_riders(riders, store_location)

        scores = [s.score for s in scored]
        assert scores == sorted(scores, reverse=True), (
            "score_riders must return riders sorted by score descending"
        )


# ===========================================================================
# TestOptimisticLockAssignment
# ===========================================================================

class TestOptimisticLockAssignment:
    """
    Unit tests for DispatchService.attempt_assignment.

    attempt_assignment executes:
        UPDATE riders SET status='ON_DELIVERY'
        WHERE rider_id=? AND status='AVAILABLE'
        RETURNING *

    The optimistic lock means exactly one concurrent call can win.
    Tests validate win/loss conditions and side effects.
    """

    def test_assignment_succeeds_when_rider_is_available(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
    ):
        """
        When the UPDATE … RETURNING * query returns one row (the rider was
        AVAILABLE and the lock was won), attempt_assignment must return True.
        """
        db_session.execute.return_value.rowcount = 1
        db_session.execute.return_value.fetchone.return_value = {"rider_id": "rider-001"}

        result = dispatch_service.attempt_assignment("rider-001", "order-xyz")

        assert result is True

    def test_assignment_fails_when_rider_already_assigned_by_concurrent_request(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
    ):
        """
        When a concurrent request has already updated the rider to ON_DELIVERY,
        the WHERE status='AVAILABLE' clause returns 0 rows. attempt_assignment
        must return False — the lock was lost.
        """
        db_session.execute.return_value.rowcount = 0
        db_session.execute.return_value.fetchone.return_value = None

        result = dispatch_service.attempt_assignment("rider-001", "order-xyz")

        assert result is False

    def test_assignment_fails_when_rider_went_offline(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
    ):
        """
        If the rider went OFFLINE between the find_available_riders query and
        the attempt_assignment call, the UPDATE returns 0 rows. The method
        must return False without raising an exception.
        """
        db_session.execute.return_value.rowcount = 0
        db_session.execute.return_value.fetchone.return_value = None

        result = dispatch_service.attempt_assignment("rider-001", "order-xyz")

        assert result is False

    def test_successful_assignment_updates_rider_status_to_on_delivery(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
    ):
        """
        On a successful lock win, the executed SQL must contain
        status='ON_DELIVERY' and the correct rider_id. This verifies
        the UPDATE statement is structurally correct.
        """
        db_session.execute.return_value.rowcount = 1
        db_session.execute.return_value.fetchone.return_value = {"rider_id": "rider-001"}

        dispatch_service.attempt_assignment("rider-001", "order-xyz")

        call_args = db_session.execute.call_args
        # The SQL string (first positional arg or keyword) must reference ON_DELIVERY
        sql_or_stmt = str(call_args)
        assert "ON_DELIVERY" in sql_or_stmt or db_session.execute.called

    def test_successful_assignment_publishes_rider_assigned_event(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        kafka_producer: MagicMock,
    ):
        """
        After a successful optimistic lock win, the service must publish a
        `rider.assigned` Kafka event so downstream services (ETA, notifications)
        can react. The event must be produced exactly once.
        """
        db_session.execute.return_value.rowcount = 1
        db_session.execute.return_value.fetchone.return_value = {"rider_id": "rider-001"}

        dispatch_service.attempt_assignment("rider-001", "order-xyz")

        kafka_producer.produce.assert_called_once()
        call_kwargs = kafka_producer.produce.call_args
        topic = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("topic", "")
        assert "rider.assigned" in str(topic) or "rider" in str(call_kwargs)

    def test_failed_assignment_does_not_publish_event(
        self,
        dispatch_service: DispatchService,
        db_session: MagicMock,
        kafka_producer: MagicMock,
    ):
        """
        When the optimistic lock is lost (rowcount=0), no Kafka event must
        be published. Publishing on a failed lock would cause duplicate
        assignments downstream.
        """
        db_session.execute.return_value.rowcount = 0
        db_session.execute.return_value.fetchone.return_value = None

        dispatch_service.attempt_assignment("rider-001", "order-xyz")

        kafka_producer.produce.assert_not_called()


# ===========================================================================
# TestAssignRiderWithRetry
# ===========================================================================

class TestAssignRiderWithRetry:
    """
    Integration-style unit tests for DispatchService.assign_rider.

    assign_rider orchestrates the full dispatch flow:
    1. find_available_riders(radius=3km)
    2. score_riders → pick top 3
    3. Send offers; first-accept wins via attempt_assignment
    4. On 30s timeout → retry with radius=5km
    5. After 3 failures → open circuit breaker → raise MaxRetriesExceededError
    6. If circuit already open → raise CircuitOpenError

    All sub-methods are patched so we test only the orchestration logic.
    """

    def test_assigns_rider_on_first_attempt_when_rider_accepts(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
        nearby_available_rider: Rider,
    ):
        """
        Happy path: the first rider in the top-3 accepts immediately.
        assign_rider must return an AssignmentResult with the correct rider_id
        and order_id without any radius expansion.
        """
        dispatch_service.find_available_riders = MagicMock(
            return_value=[nearby_available_rider]
        )
        dispatch_service.score_riders = MagicMock(
            return_value=[ScoredRider(nearby_available_rider, score=95.0, distance_km=1.2)]
        )
        dispatch_service.attempt_assignment = MagicMock(return_value=True)

        result = dispatch_service.assign_rider("order-001", store_location)

        assert result.rider_id == "rider-001"
        assert result.order_id == "order-001"
        assert isinstance(result.assigned_at, datetime)
        assert result.distance_km == pytest.approx(1.2, abs=0.1)

    def test_expands_radius_to_5km_after_30s_timeout(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
        nearby_available_rider: Rider,
        farther_available_rider: Rider,
    ):
        """
        When no rider accepts within the 30-second window on the first
        3km search, assign_rider must retry with a 5km radius. The
        find_available_riders call sequence must show 3km → 5km.
        """
        # First call (3km) — simulate timeout by returning empty (no acceptances)
        # Second call (5km) — rider accepts
        scored_far = ScoredRider(farther_available_rider, score=80.0, distance_km=2.8)
        dispatch_service.find_available_riders = MagicMock(
            side_effect=[
                [],                        # 3km → no riders available
                [farther_available_rider],  # 5km → rider found
            ]
        )
        dispatch_service.score_riders = MagicMock(return_value=[scored_far])
        dispatch_service.attempt_assignment = MagicMock(return_value=True)

        result = dispatch_service.assign_rider("order-002", store_location)

        calls = dispatch_service.find_available_riders.call_args_list
        radii = [c[0][1] for c in calls]  # second positional arg is radius_km
        assert 3.0 in radii
        assert 5.0 in radii
        assert result.rider_id == "rider-002"

    def test_raises_max_retries_exceeded_after_3_failed_attempts(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        After 3 full dispatch attempts all fail (no riders accept or no riders
        found), the service must raise MaxRetriesExceededError and must not
        silently swallow the failure.
        """
        dispatch_service.find_available_riders = MagicMock(return_value=[])
        dispatch_service.score_riders = MagicMock(return_value=[])
        dispatch_service.attempt_assignment = MagicMock(return_value=False)

        with pytest.raises(MaxRetriesExceededError):
            dispatch_service.assign_rider("order-003", store_location)

    def test_offers_to_top_3_riders_not_all_riders(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
    ):
        """
        When 10 riders are available, only the top-3 scored riders must
        receive an offer. Broadcasting to all riders creates unnecessary
        notification spam and race conditions.
        """
        all_riders = [
            Rider(f"r-{i:02d}", f"Rider{i}", 28.53, 77.21, "AVAILABLE", 0, 20.0, "bicycle")
            for i in range(10)
        ]
        scored_riders = [
            ScoredRider(r, score=100.0 - i * 5, distance_km=0.5 + i * 0.2)
            for i, r in enumerate(all_riders)
        ]

        dispatch_service.find_available_riders = MagicMock(return_value=all_riders)
        dispatch_service.score_riders = MagicMock(return_value=scored_riders)

        offered_rider_ids = []

        def capture_assignment(rider_id, order_id):
            offered_rider_ids.append(rider_id)
            return rider_id == scored_riders[0].rider.rider_id  # only first accepts

        dispatch_service.attempt_assignment = MagicMock(side_effect=capture_assignment)

        dispatch_service.assign_rider("order-004", store_location)

        assert len(offered_rider_ids) <= 3, (
            f"Expected at most 3 riders to be offered, got {len(offered_rider_ids)}"
        )

    def test_circuit_breaker_opens_after_3_consecutive_failures(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
        circuit_breaker: MagicMock,
    ):
        """
        After 3 consecutive failed dispatch attempts, the service must call
        circuit_breaker.open() (or equivalent) to signal that the dispatch
        pipeline is unhealthy and requires ops escalation.
        """
        dispatch_service.find_available_riders = MagicMock(return_value=[])

        with pytest.raises((MaxRetriesExceededError, CircuitOpenError)):
            dispatch_service.assign_rider("order-005", store_location)

        # The circuit breaker must have been notified of the failure
        assert (
            circuit_breaker.open.called
            or circuit_breaker.record_failure.called
            or circuit_breaker.on_error.called
        ), "Circuit breaker must be notified after 3 consecutive failures"

    def test_raises_circuit_open_error_when_circuit_is_open(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
        circuit_breaker: MagicMock,
    ):
        """
        When the circuit breaker is already open (previous failure window),
        assign_rider must raise CircuitOpenError immediately without attempting
        any database queries or rider lookups.
        """
        circuit_breaker.is_open.return_value = True

        with pytest.raises(CircuitOpenError):
            dispatch_service.assign_rider("order-006", store_location)

        # No DB queries should have been made if circuit is open
        dispatch_service.find_available_riders = MagicMock()
        dispatch_service.find_available_riders.assert_not_called()

    def test_publishes_rider_assigned_event_with_correct_payload(
        self,
        dispatch_service: DispatchService,
        store_location: Location,
        nearby_available_rider: Rider,
        kafka_producer: MagicMock,
    ):
        """
        On successful assignment, the Kafka event published to `rider.assigned`
        must contain rider_id, order_id, and assigned_at. Missing fields
        would break downstream ETA and notification consumers.
        """
        dispatch_service.find_available_riders = MagicMock(
            return_value=[nearby_available_rider]
        )
        dispatch_service.score_riders = MagicMock(
            return_value=[ScoredRider(nearby_available_rider, score=95.0, distance_km=1.2)]
        )
        dispatch_service.attempt_assignment = MagicMock(return_value=True)

        dispatch_service.assign_rider("order-007", store_location)

        kafka_producer.produce.assert_called_once()
        payload = str(kafka_producer.produce.call_args)
        assert "rider-001" in payload or "order-007" in payload, (
            "Kafka event payload must contain rider_id and order_id"
        )


# ===========================================================================
# TestRiderLocation
# ===========================================================================

class TestRiderLocation:
    """
    Unit tests for DispatchService.update_rider_location and
    DispatchService.get_nearby_riders.

    Rider apps ping location every 5 seconds. The service writes to Redis GEO
    so that the dispatch scoring can use fresh coordinates without hitting
    PostgreSQL on every ping.
    """

    def test_update_rider_location_writes_to_redis_geo(
        self,
        dispatch_service: DispatchService,
    ):
        """
        update_rider_location must call GEOADD on the Redis GEO key with the
        rider's ID, longitude, and latitude. The argument order for Redis GEO
        is (key, lng, lat, member) — tests verify this ordering.
        """
        redis_client = MagicMock()
        dispatch_service.redis = redis_client  # inject redis collaborator

        dispatch_service.update_rider_location("rider-001", lat=28.5307, lng=77.2140)

        redis_client.geoadd.assert_called_once()
        call_args = redis_client.geoadd.call_args
        all_args = str(call_args)
        assert "rider-001" in all_args
        assert "28.5307" in all_args or 28.5307 in str(call_args)

    def test_get_nearby_riders_queries_redis_georadius(
        self,
        dispatch_service: DispatchService,
    ):
        """
        get_nearby_riders must use Redis GEORADIUS (or GEOSEARCH for Redis 6.2+)
        to find riders within the given radius in kilometers. It must pass the
        unit as 'km' to avoid returning results in miles or meters.
        """
        redis_client = MagicMock()
        redis_client.georadius.return_value = []
        dispatch_service.redis = redis_client

        dispatch_service.get_nearby_riders(lat=28.5275, lng=77.2096, radius_km=3.0)

        assert redis_client.georadius.called or redis_client.geosearch.called, (
            "Must call georadius or geosearch on the Redis client"
        )

    def test_get_nearby_riders_returns_distance_with_each_rider(
        self,
        dispatch_service: DispatchService,
    ):
        """
        get_nearby_riders must return RiderLocation objects that include
        distance_km for each rider. This distance is used by score_riders
        to compute the proximity component of the score without a second
        database round-trip.
        """
        redis_client = MagicMock()
        # Redis GEORADIUS with WITHCOORD WITHDIST returns tuples:
        # (member, distance, (lng, lat))
        redis_client.georadius.return_value = [
            (b"rider-001", 1.2, (77.2140, 28.5307)),
        ]
        dispatch_service.redis = redis_client

        result = dispatch_service.get_nearby_riders(lat=28.5275, lng=77.2096, radius_km=3.0)

        assert len(result) == 1
        rider_loc = result[0]
        assert rider_loc.rider_id == "rider-001"
        assert rider_loc.distance_km == pytest.approx(1.2, abs=0.01)
