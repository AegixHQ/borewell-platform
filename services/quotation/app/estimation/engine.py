"""
Location Intelligence & Estimation Engine - MVP scope only.

RFC 0001 section 6 defines the full scope of this engine: reference-data
lookup, nearby-historical-job averaging, confidence bucketing. MVP
implements only the simplest slice of that - a flat, contractor-configured
depth assumption per job_type, always returned with 'low' confidence.

Historical-job averaging and reference-data lookups are explicitly Phase 1
(RFC 0001 section 7, Sprint 7-8) - not implemented here. A caller passing a
`location` is expected (it's part of the committed contract and will be
used once that phase ships) but this function deliberately does not take
it as a parameter, because nothing here uses it yet - see AGENTS.md's rule
against unnecessary parameters that nothing reads.
"""
from dataclasses import dataclass


@dataclass
class DepthEstimate:
    min_ft: float
    max_ft: float
    confidence: str


def estimate_depth(assumed_depth_ft: float, confidence_band_ft: float) -> DepthEstimate:
    min_ft = max(0.0, assumed_depth_ft - confidence_band_ft)
    max_ft = assumed_depth_ft + confidence_band_ft
    return DepthEstimate(min_ft=min_ft, max_ft=max_ft, confidence="low")
