from app.estimation.engine import estimate_depth


def test_depth_range_centered_on_assumed_depth():
    estimate = estimate_depth(assumed_depth_ft=300, confidence_band_ft=50)
    assert estimate.min_ft == 250
    assert estimate.max_ft == 350
    assert estimate.confidence == "low"


def test_confidence_is_low_without_a_matching_service_area():
    # SRS FR-QUOTE-03: outside any configured pilot service area (docs/
    # adr/0004), this is still the flat per-job-type assumption with no
    # location-specific data behind it - "low" is correct here, same as
    # the original MVP-wide behavior this replaces for pilot villages only.
    estimate = estimate_depth(assumed_depth_ft=1000, confidence_band_ft=10)
    assert estimate.confidence == "low"


def test_min_depth_never_goes_negative():
    estimate = estimate_depth(assumed_depth_ft=20, confidence_band_ft=50)
    assert estimate.min_ft == 0.0
    assert estimate.max_ft == 70


def test_service_area_match_uses_area_depth_and_medium_confidence():
    # docs/adr/0004: a real service-area match (pilot villages) uses that
    # area's water-depth estimate instead of the contractor's flat
    # assumption, at "medium" confidence - a real location-specific
    # number, but still a manually-entered village-level estimate, not a
    # verified per-site measurement (which would be "high").
    service_area = {"estimated_water_depth_ft": 280.0, "confidence_band_ft": 40.0}
    estimate = estimate_depth(
        assumed_depth_ft=1000,  # contractor's flat default - must be ignored
        confidence_band_ft=10,  # contractor's flat band - must be ignored
        service_area=service_area,
    )
    assert estimate.min_ft == 240.0
    assert estimate.max_ft == 320.0
    assert estimate.confidence == "medium"


def test_service_area_none_falls_back_to_flat_assumption():
    # Explicit None (the default) must behave identically to omitting the
    # argument entirely - this is the fallback path for every job outside
    # the pilot villages, and it must be unchanged from pre-pilot behavior.
    with_none = estimate_depth(assumed_depth_ft=300, confidence_band_ft=50, service_area=None)
    without_arg = estimate_depth(assumed_depth_ft=300, confidence_band_ft=50)
    assert with_none == without_arg
