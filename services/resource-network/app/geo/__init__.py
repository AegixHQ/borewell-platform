"""
Pure distance calculation - no I/O, no framework dependency (same design
philosophy as quotation service's app/pricing/engine.py: a pure function
is trivially unit-testable and has no hidden coupling to the DB session).

Haversine formula - standard great-circle distance, accurate enough for
same-district straight-line "nearest" ranking. Not accurate for actual
travel distance/time (roads, terrain) - that's a real routing API
integration, explicitly out of scope here, same reasoning as the water-
depth ADR: build the real interface now, swap in a real provider later.
"""
import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c
