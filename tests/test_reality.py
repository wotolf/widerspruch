"""Tests für backend.core.reality."""
from backend.core.reality import (
    DRIFT_THRESHOLD,
    apply_action_drift,
    corruption_intensity,
)


def test_corruption_zero_when_above_threshold():
    assert corruption_intensity(1.0) == 0.0
    assert corruption_intensity(DRIFT_THRESHOLD) == 0.0
    assert corruption_intensity(DRIFT_THRESHOLD + 0.1) == 0.0


def test_corruption_increases_below_threshold():
    high = corruption_intensity(0.5)
    higher = corruption_intensity(0.2)
    assert 0 < high < higher <= 1


def test_action_drift_clamps_to_zero():
    assert apply_action_drift(0.0, "investigate_emotional_lead") == 0.0


def test_action_drift_clamps_to_one():
    assert apply_action_drift(1.0, "discover_contradiction") == 1.0


def test_action_drift_unknown_action_no_change():
    assert apply_action_drift(0.5, "made_up_action") == 0.5
