from app.estimation.engine import estimate_depth


def test_depth_range_centered_on_assumed_depth():
    estimate = estimate_depth(assumed_depth_ft=300, confidence_band_ft=50)
    assert estimate.min_ft == 250
    assert estimate.max_ft == 350
    assert estimate.confidence == "low"


def test_confidence_is_always_low_in_mvp():
    # RFC 0001 section 6 / SRS FR-QUOTE-03: MVP has no data-driven confidence
    # yet - this should stay "low" regardless of input until Phase 1 ships.
    estimate = estimate_depth(assumed_depth_ft=1000, confidence_band_ft=10)
    assert estimate.confidence == "low"


def test_min_depth_never_goes_negative():
    estimate = estimate_depth(assumed_depth_ft=20, confidence_band_ft=50)
    assert estimate.min_ft == 0.0
    assert estimate.max_ft == 70
