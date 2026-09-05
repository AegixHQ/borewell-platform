"""
The one place this service makes a real synchronous cross-service HTTP call
(RFC 0001 section 4 explicitly allows this - services must not touch each
other's databases directly, but calling another service's API is fine).

Why this call exists: SRS section 6's validation table requires "Payment
amount must exactly match the approved quotation total... reject
mismatches" - that's not enforceable without asking the quotation service
what it actually approved. Trusting a client-supplied amount here would be
the exact "highest-cost class of bug in this domain" the Architecture doc
warns about (section 9).

Now that quotation service enforces real ownership (F-01), this call also
inherits that protection for free: forwarding the customer's own
Authorization header means quotation service will 403 a request for a
quotation that customer doesn't own, which main.py maps to a 403 here too
- not a generic "service unavailable" (F-06).

Wrapped as plain functions (not called directly in main.py) so tests can
override them via FastAPI's dependency injection instead of mocking httpx
internals - see tests/conftest.py.
"""
import os

import httpx

QUOTATION_SERVICE_URL = os.getenv("QUOTATION_SERVICE_URL", "http://quotation:8000")


class QuotationServiceError(Exception):
    """A payment mutation must never proceed on an unverifiable quotation -
    fail closed, not open, when the quotation service is unreachable or
    returns something outside the known set of business responses."""


class QuotationNotFound(Exception):
    pass


class QuotationAccessDenied(Exception):
    """The caller's own token was rejected by quotation service's ownership
    check - this is a real 403, not a connectivity problem, and must not
    be flattened into QuotationServiceError's generic 502."""


def fetch_quotation(quotation_id: str, auth_header: str) -> dict:
    try:
        response = httpx.get(
            f"{QUOTATION_SERVICE_URL}/v1/quotations/{quotation_id}",
            headers={"Authorization": auth_header},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise QuotationServiceError(f"quotation service unreachable: {exc}") from exc

    if response.status_code == 404:
        raise QuotationNotFound("quotation not found")
    if response.status_code == 403:
        raise QuotationAccessDenied("caller does not own this quotation")
    if response.status_code != 200:
        raise QuotationServiceError(f"quotation service returned {response.status_code}")
    return response.json()
