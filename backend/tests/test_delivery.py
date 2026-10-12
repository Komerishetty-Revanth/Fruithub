import math
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.services.delivery_service import require_delivery
from app.utils.geo import EARTH_RADIUS_KM, haversine_km, is_within_radius

STORE_LAT, STORE_LNG = 17.3500, 78.5500


def point_north(km: float):
    """A point exactly `km` kilometres north of the store."""
    return STORE_LAT + math.degrees(km / EARTH_RADIUS_KM), STORE_LNG


@pytest.fixture
def store():
    return SimpleNamespace(latitude=STORE_LAT, longitude=STORE_LNG, delivery_radius_km=5.0)


def test_same_point_is_zero_distance():
    assert haversine_km(STORE_LAT, STORE_LNG, STORE_LAT, STORE_LNG) == 0


def test_distance_is_accurate():
    lat, lng = point_north(4.9)
    assert haversine_km(STORE_LAT, STORE_LNG, lat, lng) == pytest.approx(4.9, abs=0.001)


def test_4_9_km_passes(store):
    lat, lng = point_north(4.9)
    assert require_delivery(store, lat, lng) == pytest.approx(4.9, abs=0.001)


def test_exactly_5_0_km_passes(store):
    lat, lng = point_north(5.0)
    require_delivery(store, lat, lng)


def test_5_1_km_fails(store):
    lat, lng = point_north(5.1)
    with pytest.raises(AppError) as err:
        require_delivery(store, lat, lng)
    assert err.value.code == "OUTSIDE_DELIVERY_RADIUS"


def test_far_away_fails(store):
    with pytest.raises(AppError):
        require_delivery(store, 28.6139, 77.2090)  # Delhi


def test_custom_radius_is_respected():
    small = SimpleNamespace(latitude=STORE_LAT, longitude=STORE_LNG, delivery_radius_km=2.0)
    lat, lng = point_north(3.0)
    with pytest.raises(AppError):
        require_delivery(small, lat, lng)


def test_is_within_radius_edges():
    assert is_within_radius(5.0, 5.0)
    assert is_within_radius(5.0000001, 5.0)
    assert not is_within_radius(5.01, 5.0)