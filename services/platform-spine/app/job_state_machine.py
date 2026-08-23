"""
Job lifecycle state machine - RFC 0001 section 8 / SRS FR-JOB-03.

Transitions are strictly sequential: a job can only move to the next state
in STATE_ORDER, never skip ahead, never move backward. This module has no
I/O and no framework dependency, so it's fully unit-testable on its own
(see tests/test_state_machine.py) without needing a database or an app.
"""

STATE_ORDER = [
    "lead",
    "site_location",
    "requirement",
    "estimation",
    "price_calculation",
    "quotation",
    "customer_approval",
    "booking",
    "resource_allocation",
    "drilling",
    "progress",
    "completion",
    "payment",
    "service_history",
]


class InvalidTransitionError(Exception):
    pass


def next_allowed_state(current_status: str) -> str | None:
    idx = STATE_ORDER.index(current_status)
    if idx + 1 >= len(STATE_ORDER):
        return None
    return STATE_ORDER[idx + 1]


def validate_transition(current_status: str, requested_status: str) -> None:
    """Raises InvalidTransitionError if the transition isn't allowed.
    Returns None (does nothing) if it's valid."""
    if current_status not in STATE_ORDER:
        raise InvalidTransitionError(f"Unknown current status: {current_status}")
    if requested_status not in STATE_ORDER:
        raise InvalidTransitionError(f"Unknown requested status: {requested_status}")

    expected_next = next_allowed_state(current_status)
    if expected_next is None:
        raise InvalidTransitionError(
            f"'{current_status}' is a terminal state; no further transitions allowed"
        )
    if requested_status != expected_next:
        raise InvalidTransitionError(
            f"Cannot move from '{current_status}' to '{requested_status}' - "
            f"the only allowed next state is '{expected_next}'"
        )
