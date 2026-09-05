import os

import httpx

PLATFORM_SPINE_URL = os.getenv("PLATFORM_SPINE_URL", "http://platform-spine:8000")


class JobServiceError(Exception):
    """Quotation generation must never proceed on an unverifiable job -
    fail closed, not open, same principle as payments-data's
    QuotationServiceError."""


class JobNotFound(Exception):
    pass


def fetch_job(job_id: str, auth_header: str) -> dict:
    try:
        response = httpx.get(
            f"{PLATFORM_SPINE_URL}/v1/jobs/{job_id}",
            headers={"Authorization": auth_header},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise JobServiceError(f"platform-spine unreachable: {exc}") from exc

    if response.status_code == 404:
        raise JobNotFound("job not found")
    if response.status_code != 200:
        raise JobServiceError(f"platform-spine returned {response.status_code}")
    return response.json()
