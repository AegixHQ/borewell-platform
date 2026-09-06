"""
Calls the quotation service to fetch the approved quotation total at job
completion time (needed for BR-04 variance calculation and BR-05 overage
check). Same design pattern as payments-data/app/payments/quotation_client.py.

Only one call is needed here: get the latest quotation for a job, verify
it's approved, and extract total_estimate + estimated_depth_range.
"""
import os
from decimal import Decimal

import httpx

QUOTATION_SERVICE_URL = os.getenv("QUOTATION_SERVICE_URL", "http://quotation:8000")


class QuotationNotFound(Exception):
    pass


class QuotationNotApproved(Exception):
    pass


class QuotationServiceError(Exception):
    pass


def fetch_approved_quotation(job_id: str, auth_header: str) -> dict:
    """Fetch the approved quotation for a job.

    Returns a dict with:
      - total_estimate: Decimal  (safe parse, not float - see payments-data
        quotation_client.py's comment on why parse_float=Decimal matters)
      - min_ft: float
      - max_ft: float
      - depth_overage_rate_per_ft: Decimal (from pricing rule embedded
        in quotation response)

    Raises QuotationNotFound, QuotationNotApproved, or QuotationServiceError.
    """
    try:
        response = httpx.get(
            f"{QUOTATION_SERVICE_URL}/v1/quotations/job/{job_id}/latest",
            headers={"Authorization": auth_header},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise QuotationServiceError(f"quotation service unreachable: {exc}") from exc

    if response.status_code == 404:
        raise QuotationNotFound("no quotation found for this job")
    if response.status_code != 200:
        raise QuotationServiceError(f"quotation service returned {response.status_code}")

    body = response.json()

    if body.get("status") != "approved":
        raise QuotationNotApproved(
            f"quotation status is '{body.get('status')}', "
            "must be 'approved' before logging completion"
        )

    # total_estimate comes back as a Decimal-string (e.g. "95450.00") -
    # see quotation service's schemas.py and the session note about
    # FastAPI serializing Decimal as a JSON string to avoid float loss.
    total_estimate = Decimal(str(body["total_estimate"]))
    depth_range = body.get("estimated_depth_range", {})

    return {
        "total_estimate": total_estimate,
        "min_ft": depth_range.get("min_ft", 0.0),
        "max_ft": depth_range.get("max_ft", 0.0),
    }
