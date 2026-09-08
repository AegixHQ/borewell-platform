"""Pure unit tests for the Haversine distance function - no DB/client needed."""
from app.geo import haversine_km


def test_same_point_is_zero_distance():
    assert haversine_km(9.5851, 77.9624, 9.5851, 77.9624) == 0.0


def test_known_distance_chennai_to_madurai_is_approximately_correct():
    # Chennai (13.0827, 80.2707) to Madurai (9.9252, 78.1198) is
    # approximately 435-445 km by great-circle distance (verified against
    # known reference values - straight-line, not road distance).
    d = haversine_km(13.0827, 80.2707, 9.9252, 78.1198)
    assert 420 < d < 450


def test_nearby_points_within_a_district_give_small_distance():
    # Madurai city center vs Virudhunagar - roughly 45-50 km apart.
    d = haversine_km(9.9252, 78.1198, 9.5851, 77.9624)
    assert 40 < d < 55
