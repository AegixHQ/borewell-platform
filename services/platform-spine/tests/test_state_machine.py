import pytest
from app.job_state_machine import (
    STATE_ORDER,
    InvalidTransitionError,
    next_allowed_state,
    validate_transition,
)


def test_first_step_is_lead():
    assert STATE_ORDER[0] == "lead"


def test_valid_sequential_transition():
    validate_transition("lead", "site_location")  # should not raise


def test_rejects_skipping_a_state():
    with pytest.raises(InvalidTransitionError):
        validate_transition("lead", "requirement")


def test_rejects_backward_transition():
    with pytest.raises(InvalidTransitionError):
        validate_transition("booking", "lead")


def test_rejects_unknown_status():
    with pytest.raises(InvalidTransitionError):
        validate_transition("lead", "not_a_real_status")


def test_terminal_state_has_no_next():
    assert next_allowed_state("service_history") is None


def test_every_non_terminal_state_has_exactly_one_next():
    for i, state in enumerate(STATE_ORDER[:-1]):
        assert next_allowed_state(state) == STATE_ORDER[i + 1]
