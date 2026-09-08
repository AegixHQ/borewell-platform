"""
Calls resource-network's GET /v1/service-areas/lookup to check whether a
job's location falls within a configured pilot service area (Madurai
district villages, see docs/adr/0004). Same call pattern as
app/jobs/job_client.py.

Unlike job_client, a lookup MISS (404) is not a failure - it's the
expected result outside the pilot villages, and callers should fall back
to the contractor's flat assumed_depth_ft, not treat it as an error. Only
a genuine service outage (JOB_SERVICE_UNAVAILABLE-equivalent) fails
closed; a location simply not being covered fails open to the existing
MVP behavior, since that's what every job outside these pilot villages
already does today.
"""
import os

import httpx

RESOURCE_NETWORK_URL = os.getenv("RESOURCE_NETWORK_URL", "http://resource-network:8000")


class LocationServiceError(Exception):
    """resource-network is unreachable or errored - distinct from a
    legitimate "no coverage" miss. Callers should fall back to the flat
    assumed_depth_ft on this too (never block quotation generation on this
    lookup being unavailable), but it's worth distinguishing in logs/
    metrics from an expected 404 miss."""


def lookup_service_area(lat: float, lng: float, auth_header: str) -> dict | None:
    """Returns the covering ServiceArea dict, or None if no configured
    area covers this point (expected outside pilot villages) or the
    lookup service is unreachable (fails open, not closed - pricing must
    never block on this optional enrichment)."""
    try:
        response = httpx.get(
            f"{RESOURCE_NETWORK_URL}/v1/service-areas/lookup",
            params={"lat": lat, "lng": lng},
            headers={"Authorization": auth_header},
            timeout=3.0,
        )
    except httpx.RequestError:
        # Fails open: an unreachable resource-network must not block
        # quotation generation. The flat assumed_depth_ft fallback is a
        # correct MVP behavior on its own, not degraded service.
        return None

    if response.status_code == 404:
        return None
    if response.status_code != 200:
        return None
    return response.json()
