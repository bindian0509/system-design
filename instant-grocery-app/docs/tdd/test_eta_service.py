"""
TDD test suite for the ETA Service of an instant grocery delivery application.

The ETA Service provides two distinct ETA calculation modes:

Phase 1 — Pre-checkout (< 100ms, approximate):
    Uses Redis store-load data and a zone travel-time cache. The Maps API is
    never consulted. Returns an (eta_min, eta_max) range with a congestion label.

Phase 2 — Post-order / live (< 500ms, precise):
    Uses the live rider position from the Dispatch Service, a Maps API call for
    real routing, and the store's picking time. Falls back to the Redis zone cache
    if the Maps API circuit breaker is open.

Additional behaviors under test:
    - Delta suppression: only push ETA updates when the change exceeds 2 minutes
      or when the rider has been stationary for > 120 seconds.
    - Congestion multiplier: derived from active_orders / picker_count ratio.

Formulae:
    T_pick = (2 + 0.5 × item_count) × congestion_multiplier
    congestion_multiplier:
        1.0  if ratio ≤ 10
        1.5  if ratio ≤ 20
        2.0  if ratio > 20
    T_wait = distance(rider → store) / 25 km/h  (converted to minutes)
    eta_min = T_pick + T_travel - 2
    eta_max = T_pick + T_travel + 3
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Location:
    lat: float
    lng: float


@dataclass
class PreCheckoutETA:
    eta_min: int
    eta_max: int
    congestion_level: str   # LOW, MEDIUM, HIGH
    store_id: str


@dataclass
class OrderETA:
    eta_minutes: int
    t_pick_minutes: int
    t_wait_minutes: int
    t_travel_minutes: int
    used_cache_fallback: bool


# ---------------------------------------------------------------------------
# Custom exception stubs
# ---------------------------------------------------------------------------

class ZoneCacheExpiredError(Exception):
    """Raised when the Redis zone cache entry has expired (TTL elapsed)."""


class StoreNotFoundError(Exception):
    """Raised when the requested store_id has no entry in Redis."""


class MapsAPIError(Exception):
    """Raised when the Maps API returns a non-2xx response or times out."""


class CircuitOpenError(Exception):
    """Raised when the Maps API circuit breaker is open."""


# ---------------------------------------------------------------------------
# Production class stub
# ---------------------------------------------------------------------------

class ETAService:
    """
    Stub of the production ETAService used during the TDD red phase.
    Each method raises NotImplementedError until the green implementation
    is written.
    """

    def __init__(self, redis_client, maps_client, circuit_breaker):
        self.redis = redis_client
        self.maps = maps_client
        self.circuit_breaker = circuit_breaker

    def get_pre_checkout_eta(
        self, store_id: str, item_count: int, delivery_zone: str
    ) -> PreCheckoutETA:
        raise NotImplementedError

    def get_order_eta(
        self,
        order_id: str,
        rider_location: Location,
        store_location: Location,
        delivery_location: Location,
        item_count: int,
    ) -> OrderETA:
        raise NotImplementedError

    def should_push_update(
        self,
        new_eta_minutes: int,
        shown_eta_minutes: int,
        rider_stationary_seconds: int,
    ) -> bool:
        raise NotImplementedError

    def get_congestion_multiplier(self, store_id: str) -> float:
        raise NotImplementedError

    def get_zone_travel_time(self, store_id: str, delivery_zone: str) -> int:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def redis_client():
    """Mock Redis client. Tests configure .hget, .get returns as needed."""
    return MagicMock()


@pytest.fixture
def maps_client():
    """Mock Maps API client (e.g., Google Maps Distance Matrix)."""
    return MagicMock()


@pytest.fixture
def circuit_breaker():
    """Mock circuit breaker. Default: closed (is_open → False)."""
    cb = MagicMock()
    cb.is_open.return_value = False
    return cb


@pytest.fixture
def eta_service(redis_client, maps_client, circuit_breaker):
    """Fully wired ETAService with all collaborators mocked."""
    return ETAService(
        redis_client=redis_client,
        maps_client=maps_client,
        circuit_breaker=circuit_breaker,
    )


@pytest.fixture
def store_id():
    return "store-saket-001"


@pytest.fixture
def delivery_zone():
    return "zone-south-delhi-a"


@pytest.fixture
def store_location():
    """Dark store coordinates (Saket, New Delhi)."""
    return Location(lat=28.5275, lng=77.2096)


@pytest.fixture
def delivery_location():
    """Customer delivery coordinates."""
    return Location(lat=28.5420, lng=77.2250)


@pytest.fixture
def rider_location_near_store():
    """Rider is 0.5 km from the store — very short wait time."""
    return Location(lat=28.5300, lng=77.2110)


@pytest.fixture
def rider_location_far_from_store():
    """Rider is 4.0 km from the store — longer wait time."""
    return Location(lat=28.5620, lng=77.2400)


# ---------------------------------------------------------------------------
# Helper: configure Redis to return store load data
# ---------------------------------------------------------------------------

def _setup_redis_store_load(
    redis_client: MagicMock,
    store_id: str,
    active_orders: int,
    picker_count: int,
    zone_travel_minutes: int = 15,
    delivery_zone: str = "zone-south-delhi-a",
):
    """
    Configure the mock Redis client to return store-load and zone-cache data.
    The production code is expected to call hget/hgetall on Redis hash keys.
    """
    def hget_side_effect(key, field):
        if store_id in key:
            if field == "active_orders":
                return active_orders
            if field == "picker_count":
                return picker_count
        if delivery_zone in key or "zone" in str(key):
            return zone_travel_minutes
        return None

    redis_client.hget.side_effect = hget_side_effect

    def get_side_effect(key):
        if "zone" in str(key) and (delivery_zone in str(key) or store_id in str(key)):
            return zone_travel_minutes
        return None

    redis_client.get.side_effect = get_side_effect

    # Also configure hgetall to return a dict for flexibility
    redis_client.hgetall.return_value = {
        "active_orders": active_orders,
        "picker_count": picker_count,
    }


# ===========================================================================
# TestPreCheckoutETA
# ===========================================================================

class TestPreCheckoutETA:
    """
    Unit tests for ETAService.get_pre_checkout_eta (Phase 1).

    Phase 1 is the fast path shown before the customer checks out.
    It must respond in < 100ms and must never call the Maps API.
    It uses:
        - Redis to get store load (active_orders, picker_count)
        - Redis zone cache for approximate travel time
    """

    def test_pre_checkout_eta_uses_only_redis_not_maps_api(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        The Maps client must never be called during pre-checkout ETA
        computation. Any call would violate the < 100ms SLA since Maps API
        round-trips average 50–200ms on their own.
        """
        _setup_redis_store_load(redis_client, store_id, active_orders=5, picker_count=3)

        eta_service.get_pre_checkout_eta(store_id, item_count=5, delivery_zone=delivery_zone)

        maps_client.get_distance_matrix.assert_not_called()
        maps_client.get_eta.assert_not_called()
        maps_client.directions.assert_not_called()

    def test_eta_increases_with_more_items(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        T_pick = (2 + 0.5 × item_count) × multiplier.
        A basket with 10 items must yield a higher eta_max than a basket
        with 3 items, assuming the same store load and zone cache.
        """
        _setup_redis_store_load(redis_client, store_id, active_orders=5, picker_count=3)

        eta_few = eta_service.get_pre_checkout_eta(
            store_id, item_count=3, delivery_zone=delivery_zone
        )
        eta_many = eta_service.get_pre_checkout_eta(
            store_id, item_count=10, delivery_zone=delivery_zone
        )

        assert eta_many.eta_max > eta_few.eta_max, (
            "More items must increase ETA due to longer picking time"
        )

    def test_eta_range_has_correct_min_and_max_spread(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        eta_min = T_pick + T_travel - 2
        eta_max = T_pick + T_travel + 3
        The spread between eta_max and eta_min must always be exactly 5 minutes.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            zone_travel_minutes=15, delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=5, delivery_zone=delivery_zone
        )

        assert eta.eta_max - eta.eta_min == 5, (
            f"ETA spread must be 5 minutes, got {eta.eta_max - eta.eta_min}"
        )

    def test_congestion_multiplier_1_when_ratio_below_10(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        ratio = active_orders / picker_count = 6 / 3 = 2.0 (≤ 10).
        congestion_multiplier must be 1.0 (no congestion).
        Verify indirectly: T_pick for 4 items with multiplier 1.0 = (2 + 2) × 1.0 = 4 min.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=6, picker_count=3,
            zone_travel_minutes=15, delivery_zone=delivery_zone,
        )

        # T_pick = (2 + 0.5*4) * 1.0 = 4, T_travel=15
        # eta_min = 4 + 15 - 2 = 17, eta_max = 4 + 15 + 3 = 22
        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=4, delivery_zone=delivery_zone
        )

        assert eta.eta_min == 17
        assert eta.eta_max == 22

    def test_congestion_multiplier_1_5_when_ratio_between_10_and_20(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        ratio = 30 / 2 = 15.0 (10 < ratio ≤ 20).
        congestion_multiplier must be 1.5.
        T_pick for 4 items = (2 + 2) × 1.5 = 6 min.
        eta_min = 6 + 15 - 2 = 19, eta_max = 6 + 15 + 3 = 24.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=30, picker_count=2,
            zone_travel_minutes=15, delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=4, delivery_zone=delivery_zone
        )

        assert eta.eta_min == 19
        assert eta.eta_max == 24

    def test_congestion_multiplier_2_when_ratio_above_20(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        ratio = 50 / 2 = 25.0 (> 20).
        congestion_multiplier must be 2.0.
        T_pick for 4 items = (2 + 2) × 2.0 = 8 min.
        eta_min = 8 + 15 - 2 = 21, eta_max = 8 + 15 + 3 = 26.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=50, picker_count=2,
            zone_travel_minutes=15, delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=4, delivery_zone=delivery_zone
        )

        assert eta.eta_min == 21
        assert eta.eta_max == 26

    def test_congestion_level_low_when_multiplier_1(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        When ratio ≤ 10 (multiplier = 1.0), congestion_level must be 'LOW'.
        This label is displayed in the UI to set customer expectations.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=5, delivery_zone=delivery_zone
        )

        assert eta.congestion_level == "LOW"

    def test_congestion_level_medium_when_multiplier_1_5(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        When 10 < ratio ≤ 20 (multiplier = 1.5), congestion_level must be 'MEDIUM'.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=30, picker_count=2,
            delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=5, delivery_zone=delivery_zone
        )

        assert eta.congestion_level == "MEDIUM"

    def test_congestion_level_high_when_multiplier_2(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
        delivery_zone: str,
    ):
        """
        When ratio > 20 (multiplier = 2.0), congestion_level must be 'HIGH'.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=50, picker_count=2,
            delivery_zone=delivery_zone,
        )

        eta = eta_service.get_pre_checkout_eta(
            store_id, item_count=5, delivery_zone=delivery_zone
        )

        assert eta.congestion_level == "HIGH"

    def test_raises_error_when_store_not_found(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        delivery_zone: str,
    ):
        """
        When the store_id does not exist in Redis (all hget calls return None),
        the service must raise StoreNotFoundError. Silently returning a zero
        ETA would show incorrect information to the customer.
        """
        redis_client.hget.return_value = None
        redis_client.get.return_value = None
        redis_client.hgetall.return_value = {}

        with pytest.raises(StoreNotFoundError):
            eta_service.get_pre_checkout_eta(
                "store-does-not-exist", item_count=5, delivery_zone=delivery_zone
            )


# ===========================================================================
# TestOrderETA
# ===========================================================================

class TestOrderETA:
    """
    Unit tests for ETAService.get_order_eta (Phase 2).

    Phase 2 is computed after the order is placed and the rider is assigned.
    It uses live rider location and the Maps API for accurate routing.
    Falls back to Redis zone cache when the Maps API circuit breaker is open.
    """

    def test_order_eta_includes_t_pick_t_wait_and_t_travel(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
    ):
        """
        The OrderETA breakdown must always include all three components:
        t_pick_minutes, t_wait_minutes, and t_travel_minutes.
        eta_minutes must equal their sum.
        """
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
        )
        maps_client.get_distance_matrix.return_value = {"duration_minutes": 12}

        result = eta_service.get_order_eta(
            order_id="order-001",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        assert result.eta_minutes == result.t_pick_minutes + result.t_wait_minutes + result.t_travel_minutes
        assert result.t_pick_minutes > 0
        assert result.t_wait_minutes >= 0
        assert result.t_travel_minutes > 0

    def test_t_wait_calculated_from_rider_distance_to_store(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
        rider_location_far_from_store: Location,
    ):
        """
        T_wait = distance(rider → store) / 25 km/h.
        A rider 4km away must produce a substantially higher t_wait than a
        rider 0.5km away. Both are compared for the same item_count and
        same Maps API result.
        """
        _setup_redis_store_load(redis_client, store_id, active_orders=5, picker_count=3)
        maps_client.get_distance_matrix.return_value = {"duration_minutes": 12}

        eta_near = eta_service.get_order_eta(
            order_id="order-002",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )
        eta_far = eta_service.get_order_eta(
            order_id="order-003",
            rider_location=rider_location_far_from_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        assert eta_far.t_wait_minutes > eta_near.t_wait_minutes, (
            "Rider further from store must have a higher t_wait"
        )

    def test_t_travel_uses_maps_api_when_circuit_closed(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
    ):
        """
        When the Maps API circuit breaker is closed (healthy state),
        t_travel must come from the Maps API response, not from the Redis cache.
        """
        circuit_breaker.is_open.return_value = False
        _setup_redis_store_load(redis_client, store_id, active_orders=5, picker_count=3)
        maps_client.get_distance_matrix.return_value = {"duration_minutes": 18}

        result = eta_service.get_order_eta(
            order_id="order-004",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        maps_client.get_distance_matrix.assert_called_once()
        assert result.t_travel_minutes == 18

    def test_t_travel_uses_zone_cache_when_maps_api_circuit_open(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
        delivery_zone: str,
    ):
        """
        When the Maps API circuit breaker is open, the service must fall back
        to the Redis zone cache for t_travel. The Maps API must not be called
        (which would fail and worsen the circuit's failure count).
        """
        circuit_breaker.is_open.return_value = True
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            zone_travel_minutes=14, delivery_zone=delivery_zone,
        )

        result = eta_service.get_order_eta(
            order_id="order-005",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        maps_client.get_distance_matrix.assert_not_called()
        assert result.t_travel_minutes == 14

    def test_used_cache_fallback_is_true_when_circuit_open(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
        delivery_zone: str,
    ):
        """
        When the circuit is open and the Redis zone cache is used for t_travel,
        used_cache_fallback must be True in the returned OrderETA. This flag
        allows the API consumer to show appropriate UI uncertainty indicators.
        """
        circuit_breaker.is_open.return_value = True
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            zone_travel_minutes=14, delivery_zone=delivery_zone,
        )

        result = eta_service.get_order_eta(
            order_id="order-006",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        assert result.used_cache_fallback is True

    def test_used_cache_fallback_is_false_when_maps_api_used(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
    ):
        """
        When the Maps API is successfully used, used_cache_fallback must be
        False so that the consumer knows the ETA is based on real routing data.
        """
        circuit_breaker.is_open.return_value = False
        _setup_redis_store_load(redis_client, store_id, active_orders=5, picker_count=3)
        maps_client.get_distance_matrix.return_value = {"duration_minutes": 12}

        result = eta_service.get_order_eta(
            order_id="order-007",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        assert result.used_cache_fallback is False

    def test_maps_api_circuit_opens_after_3_consecutive_failures(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
        delivery_zone: str,
    ):
        """
        The circuit breaker must be called to record each Maps API failure.
        After 3 consecutive failures, circuit_breaker.open() (or equivalent)
        must be called. Tests verify that the failure is propagated to the
        circuit breaker on each error, not swallowed silently.
        """
        circuit_breaker.is_open.return_value = False
        maps_client.get_distance_matrix.side_effect = MapsAPIError("connection timeout")
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            zone_travel_minutes=14, delivery_zone=delivery_zone,
        )

        for i in range(3):
            try:
                eta_service.get_order_eta(
                    order_id=f"order-{i:03d}",
                    rider_location=rider_location_near_store,
                    store_location=store_location,
                    delivery_location=delivery_location,
                    item_count=5,
                )
            except Exception:
                pass  # Failures are expected; we check circuit state below

        assert (
            circuit_breaker.record_failure.call_count >= 3
            or circuit_breaker.on_error.call_count >= 3
            or circuit_breaker.open.called
        ), (
            "Circuit breaker must record each Maps API failure. "
            "After 3 failures it must open."
        )

    def test_circuit_uses_cache_fallback_immediately_after_opening(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        maps_client: MagicMock,
        circuit_breaker: MagicMock,
        store_id: str,
        store_location: Location,
        delivery_location: Location,
        rider_location_near_store: Location,
        delivery_zone: str,
    ):
        """
        Once the circuit is open (simulated via is_open → True), the very next
        get_order_eta call must immediately use the zone cache without attempting
        the Maps API. There must be zero Maps API calls when the circuit is open.
        """
        circuit_breaker.is_open.return_value = True
        _setup_redis_store_load(
            redis_client, store_id, active_orders=5, picker_count=3,
            zone_travel_minutes=14, delivery_zone=delivery_zone,
        )

        result = eta_service.get_order_eta(
            order_id="order-010",
            rider_location=rider_location_near_store,
            store_location=store_location,
            delivery_location=delivery_location,
            item_count=5,
        )

        maps_client.get_distance_matrix.assert_not_called()
        assert result.used_cache_fallback is True
        assert result.t_travel_minutes == 14


# ===========================================================================
# TestDeltaSuppression
# ===========================================================================

class TestDeltaSuppression:
    """
    Unit tests for ETAService.should_push_update.

    Delta suppression prevents noisy ETA notifications. An update is pushed only
    when the change is meaningful (> 2 minutes) or the rider appears stuck
    (stationary > 120 seconds), which may signal a problem worth surfacing.
    """

    def test_should_push_update_when_delta_greater_than_2_minutes(
        self,
        eta_service: ETAService,
    ):
        """
        A 3-minute increase in ETA (new=25, shown=22) exceeds the 2-minute
        threshold and must trigger a push notification to the customer.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=25,
            shown_eta_minutes=22,
            rider_stationary_seconds=0,
        )

        assert result is True

    def test_should_not_push_update_when_delta_is_exactly_2_minutes(
        self,
        eta_service: ETAService,
    ):
        """
        An exactly 2-minute difference must NOT trigger a push. The rule is
        strictly greater than 2 minutes (> 2, not >= 2). This prevents
        unnecessary notifications for small fluctuations.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=24,
            shown_eta_minutes=22,
            rider_stationary_seconds=0,
        )

        assert result is False

    def test_should_not_push_update_when_delta_less_than_2_minutes(
        self,
        eta_service: ETAService,
    ):
        """
        A 1-minute change in ETA (new=23, shown=22) is below the threshold
        and must not trigger a push. Minor ETA fluctuations are normal and
        create notification fatigue if surfaced.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=23,
            shown_eta_minutes=22,
            rider_stationary_seconds=0,
        )

        assert result is False

    def test_should_push_update_when_rider_stationary_more_than_120_seconds(
        self,
        eta_service: ETAService,
    ):
        """
        If the rider has been stationary for > 120 seconds, the customer must
        be notified even if the ETA delta is below the 2-minute threshold.
        A stationary rider may indicate a problem (accident, wrong address, etc.)
        that the customer needs to know about.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=23,   # delta = 1 min, normally suppressed
            shown_eta_minutes=22,
            rider_stationary_seconds=180,  # > 120s override
        )

        assert result is True

    def test_should_not_push_update_when_no_change_and_rider_moving(
        self,
        eta_service: ETAService,
    ):
        """
        When the ETA has not changed (delta = 0) and the rider is actively
        moving (stationary_seconds = 0), no push must be sent. This is the
        normal in-transit state and produces no actionable information.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=22,
            shown_eta_minutes=22,
            rider_stationary_seconds=0,
        )

        assert result is False

    def test_negative_delta_treated_as_absolute_value(
        self,
        eta_service: ETAService,
    ):
        """
        An ETA improvement of 3 minutes (new=19, shown=22, delta=-3) must
        also trigger a push notification because abs(-3) > 2. Customers want
        to know when their order will arrive sooner, not just when it's later.
        """
        result = eta_service.should_push_update(
            new_eta_minutes=19,
            shown_eta_minutes=22,
            rider_stationary_seconds=0,
        )

        assert result is True, (
            "An ETA improvement of 3 minutes exceeds |2| and must trigger a push"
        )


# ===========================================================================
# TestCongestionMultiplier
# ===========================================================================

class TestCongestionMultiplier:
    """
    Unit tests for ETAService.get_congestion_multiplier.

    The multiplier is derived from the ratio active_orders / picker_count.
    Edge cases (zero pickers, missing data) must be handled defensively
    to prevent division-by-zero errors and silent NaN propagation.
    """

    def test_returns_1_when_store_has_no_active_orders(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
    ):
        """
        When active_orders = 0 and picker_count > 0, ratio = 0 / n = 0.0 (≤ 10).
        The multiplier must be 1.0 (no congestion). This is the standard
        off-peak state where pickers are idle and ready.
        """
        redis_client.hget.side_effect = lambda key, field: (
            0 if field == "active_orders" else 5 if field == "picker_count" else None
        )

        multiplier = eta_service.get_congestion_multiplier(store_id)

        assert multiplier == 1.0

    def test_returns_1_when_picker_count_is_zero_and_no_orders(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
    ):
        """
        Edge case: picker_count = 0 and active_orders = 0. A naive implementation
        would raise ZeroDivisionError. The service must guard against this by
        treating 0/0 as ratio = 0 (no congestion) → multiplier = 1.0.

        A store with no pickers and no orders is effectively closed or idle;
        returning a HIGH multiplier here would be incorrect.
        """
        redis_client.hget.side_effect = lambda key, field: 0

        multiplier = eta_service.get_congestion_multiplier(store_id)

        assert multiplier == 1.0, (
            "Division by zero must be handled; 0 orders / 0 pickers → multiplier 1.0"
        )

    def test_handles_missing_picker_count_gracefully(
        self,
        eta_service: ETAService,
        redis_client: MagicMock,
        store_id: str,
    ):
        """
        When Redis returns None for picker_count (key missing or TTL expired),
        the service must not raise an exception. It should either default to a
        safe multiplier (e.g. 1.0) or raise a well-typed error that the caller
        can handle. It must not propagate a raw TypeError from None arithmetic.
        """
        redis_client.hget.side_effect = lambda key, field: (
            10 if field == "active_orders" else None
        )

        try:
            multiplier = eta_service.get_congestion_multiplier(store_id)
            # If it returns, it must be a valid float (not NaN / infinity)
            assert multiplier in (1.0, 1.5, 2.0), (
                f"Expected a valid congestion multiplier, got {multiplier}"
            )
        except (StoreNotFoundError, ZeroDivisionError, ValueError):
            # Raising a well-typed domain error is also acceptable
            pass
        except TypeError as exc:
            pytest.fail(
                f"get_congestion_multiplier raised raw TypeError on None picker_count: {exc}"
            )
