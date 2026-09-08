"""
Location Intelligence & Estimation Engine - MVP scope, now with real
location-based estimation for pilot service areas (docs/adr/0004).

Two tiers:
1. If the job's location falls within a configured service area (a
   handful of Madurai district villages, contractor/admin-edited water
   depth estimates - NOT a real geological data source, see the ADR),
   use that area's estimate. Confidence is "medium" - a real location-
   specific estimate, but still a manually-entered village-level number,
   not a per-site survey or verified measurement, so "high" would overstate
   it.
2. Outside any configured area (or if the lookup is unavailable), fall
   back to the flat contractor-configured assumed_depth_ft at "low"
   confidence - the exact original MVP behavior, unchanged. This is the
   expected, common case everywhere outside the pilot villages, not a
   degraded fallback to apologize for.

RFC 0001 section 6's full scope (historical-job averaging, richer
confidence bucketing) is still not implemented - this is the pilot-scope
slice between "flat assumption everywhere" and that full vision.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DepthEstimate:
    min_ft: float
    max_ft: float
    confidence: str


def estimate_depth(
    assumed_depth_ft: float,
    confidence_band_ft: float,
    service_area: Optional[dict] = None,
) -> DepthEstimate:
    """service_area, if provided, is the dict returned by
    location_client.lookup_service_area - a ServiceArea response with
    estimated_water_depth_ft/confidence_band_ft. None means no pilot
    coverage at this location (or the lookup wasn't attempted) - falls
    back to the flat per-job-type assumption, unchanged from pre-pilot
    MVP behavior.
    """
    if service_area is not None:
        depth = service_area["estimated_water_depth_ft"]
        band = service_area["confidence_band_ft"]
        confidence = "medium"
    else:
        depth = assumed_depth_ft
        band = confidence_band_ft
        confidence = "low"

    min_ft = max(0.0, depth - band)
    max_ft = depth + band
    return DepthEstimate(min_ft=min_ft, max_ft=max_ft, confidence=confidence)
