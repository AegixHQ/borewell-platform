#!/usr/bin/env python3
"""
Real cross-service integration test - runs against LIVE services started
via `docker compose up` (see .github/workflows/ci-integration.yml), not
mocks. This is the Development Plan Milestone 2 requirement that no
per-service CI workflow can satisfy on its own: "End-to-end flow (lead ->
quote -> approve -> pay -> track -> complete) runs against real services,
not mocks" (Development Plan section 2, Milestone 2 row 1) and "the
Milestone 2 end-to-end flow, run via Docker Compose in CI, not just
locally" (Development Plan section 5, Testing Strategy).

Every per-service pytest suite (services/*/tests/) proves each service is
internally correct using mocked cross-service calls (fake_job_fetcher,
fake_quotation_fetcher, fake_location_fetcher, etc. - see each service's
tests/conftest.py). None of them prove the services actually work
TOGETHER over real HTTP. This script is what does that.

HONEST SCOPE NOTE: of the 4 events (job.created, job.quoted, job.completed,
payment.completed - published by every service, see app/events.py in
each), only one has a real consumer: platform-spine's payment.completed
-> advances a job from "completion" to "payment"
(services/platform-spine/app/payment_consumer.py, unit-tested in
tests/test_payment_consumer.py). This script now covers that one real
consumer end-to-end for real (step 8 below): it confirms a real payment
via POST /v1/payments/{id}/confirm (which is what actually calls
events.payment_completed() - see services/payments-data/app/main.py;
plain POST /v1/payments only creates a 'pending' row and does NOT
publish), then polls the job via GET /v1/jobs/{id} until platform-spine's
background subscriber thread picks the message up off real Redis and
advances the job to 'payment' - proving publish, delivery, AND the
consumer's reaction, not just that a message was sent. The other 3
events remain publish-only - confirmed by `grep -rn "subscribe"
services/*/app/` returning exactly one file - and still are not
exercised by this script. Development Plan Milestone 2's second row
("Each event is both emitted and consumed correctly") is still only
partially true for those 3; do not read a green run of this script as
proof that all 4 events work end-to-end, only that the one real
consumer does.

Exit code 0 = every step passed. Exit code 1 = a step failed; the
specific step and response are printed before exiting, so CI logs show
exactly what broke without needing to reproduce locally first.
"""
import os
import sys
import time
import uuid

import redis
import requests

PLATFORM_SPINE_URL = os.getenv("PLATFORM_SPINE_URL", "http://localhost:8001")
QUOTATION_URL = os.getenv("QUOTATION_URL", "http://localhost:8002")
RESOURCE_NETWORK_URL = os.getenv("RESOURCE_NETWORK_URL", "http://localhost:8003")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://localhost:8004")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

READY_TIMEOUT_SECONDS = 90
READY_POLL_INTERVAL_SECONDS = 2

# How long to wait for platform-spine's background subscriber thread to
# pick up the payment.completed message and advance the job. Generous
# relative to how fast this actually happens locally (sub-second - it's
# a blocking pubsub.listen() loop, not a poll) because CI runners under
# load are slower and this is genuinely asynchronous: unlike every other
# step in this script, there's no synchronous HTTP response that proves
# the reaction already happened by the time we get a 200 back.
EVENT_CONSUMER_TIMEOUT_SECONDS = 15
EVENT_CONSUMER_POLL_INTERVAL_SECONDS = 1

# Unique per run so re-running this script against a stack that already
# has data from a prior run (e.g. a developer running it twice locally
# without tearing down volumes) doesn't collide on unique constraints
# (email, idempotency_key) - see registration/payment steps below.
RUN_ID = uuid.uuid4().hex[:8]


class StepFailed(Exception):
    """Raised with a human-readable description; caught once at the top
    level so every failure prints the same way and exits 1, rather than
    an unhandled traceback per call site."""


def _request(method, url, **kwargs):
    """Thin wrapper - not because requests needs wrapping, but so every
    call site gets the same "print what actually happened" behavior on
    an unexpected status, instead of each step re-implementing that."""
    resp = requests.request(method, url, timeout=10, **kwargs)
    return resp


def _expect(resp, expected_status, step_name):
    if resp.status_code != expected_status:
        raise StepFailed(
            f"{step_name}: expected {expected_status}, got {resp.status_code}\n"
            f"URL: {resp.request.method} {resp.request.url}\n"
            f"Body: {resp.text[:2000]}"
        )
    return resp


def wait_for_ready(name, url):
    """Polls /readyz (checks real DB connectivity, not just process
    liveness - see each service's readyz handler) until it succeeds or
    READY_TIMEOUT_SECONDS elapses. Real service startup includes running
    Alembic migrations before uvicorn even starts (see each Dockerfile's
    CMD) - a plain /healthz-only wait would race ahead of migrations
    actually finishing, causing this script's first real request to hit
    a service whose schema doesn't exist yet."""
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    last_error = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{url}/readyz", timeout=5)
            if resp.status_code == 200:
                print(f"[ready] {name}")
                return
            last_error = f"status {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(READY_POLL_INTERVAL_SECONDS)
    raise StepFailed(f"{name} never became ready within {READY_TIMEOUT_SECONDS}s: {last_error}")


def register_and_login(role, label):
    email = f"integration-{RUN_ID}-{label}@example.com"
    password = "integration-test-password-12345"
    reg = _request(
        "POST",
        f"{PLATFORM_SPINE_URL}/v1/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    _expect(reg, 201, f"register {label} ({role})")

    login = _request(
        "POST",
        f"{PLATFORM_SPINE_URL}/v1/auth/login",
        json={"email": email, "password": password},
    )
    _expect(login, 200, f"login {label} ({role})")
    token = login.json()["access_token"]
    print(f"[ok] registered + logged in {label} as {role}")
    return token


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def run():
    print(f"=== Integration test run {RUN_ID} ===")

    # ---------- 0. Wait for every service to actually be ready ----------
    wait_for_ready("platform-spine", PLATFORM_SPINE_URL)
    wait_for_ready("quotation", QUOTATION_URL)
    wait_for_ready("resource-network", RESOURCE_NETWORK_URL)
    wait_for_ready("payments-data", PAYMENTS_URL)

    # ---------- 1. Register the 4 roles this flow needs ----------
    customer_token = register_and_login("customer", "customer")
    contractor_token = register_and_login("contractor", "contractor")
    owner_token = register_and_login("resource_owner", "owner")
    # admin only needed for step 8's POST /v1/payments/{id}/confirm - see
    # that endpoint's own docstring for why this is the real path a
    # frontend would never call directly (Razorpay's webhook is), but is
    # exactly right here since this script has no real Razorpay account
    # to trigger a real webhook with.
    admin_token = register_and_login("admin", "admin")

    # ---------- 2. lead: customer creates a job ----------
    # Real coordinates inside Virudhunagar (pilot service area territory -
    # see docs/adr/0004) so the location-aware pricing path is exercised,
    # not just the flat-assumption fallback.
    job_resp = _expect(
        _request(
            "POST",
            f"{PLATFORM_SPINE_URL}/v1/jobs",
            json={"location": {"lat": 9.5851, "lng": 77.9624}, "job_type": "residential"},
            headers=auth_header(customer_token),
        ),
        201,
        "create job",
    )
    job = job_resp.json()
    job_id = job["job_id"]
    print(f"[ok] job created: {job_id}, status={job['status']}")

    # ---------- 2b. resource_owner lists a rig, contractor books it ----------
    # Not in the Development Plan's original lead->quote->approve->pay->
    # track->complete wording (that predates the marketplace pivot), but
    # genuinely load-bearing now - see docs/adr/0004. Included as an
    # honest extension of the documented flow, not invented scope: a real
    # contractor session today would do this before quoting.
    resource_resp = _expect(
        _request(
            "POST",
            f"{RESOURCE_NETWORK_URL}/v1/resources",
            json={
                "resource_type": "rig",
                "name": f"Integration Test Rig {RUN_ID}",
                "lat": 9.5851,
                "lng": 77.9624,
                "hourly_rate": "850.00",
                "vehicle_type": "DTH Rig - Truck Mounted",
            },
            headers=auth_header(owner_token),
        ),
        201,
        "resource_owner lists a rig",
    )
    resource_id = resource_resp.json()["resource_id"]
    print(f"[ok] resource listed: {resource_id}")

    match_resp = _expect(
        _request(
            "POST",
            f"{RESOURCE_NETWORK_URL}/v1/resources/match",
            json={"lat": 9.5851, "lng": 77.9624},
            headers=auth_header(contractor_token),
        ),
        200,
        "contractor searches nearby resources",
    )
    matches = match_resp.json()
    if not any(r["resource_id"] == resource_id for r in matches):
        raise StepFailed(
            f"contractor search did not return the resource just listed - "
            f"got {len(matches)} results, expected to find {resource_id} among them"
        )
    print(
        f"[ok] cross-owner marketplace search found the listed resource "
        f"({len(matches)} total nearby)"
    )

    booking_resp = _expect(
        _request(
            "POST",
            f"{RESOURCE_NETWORK_URL}/v1/bookings",
            json={"resource_id": resource_id, "job_id": job_id},
            headers=auth_header(contractor_token),
        ),
        201,
        "contractor requests booking",
    )
    booking_id = booking_resp.json()["booking_id"]

    accept_resp = _expect(
        _request(
            "POST",
            f"{RESOURCE_NETWORK_URL}/v1/bookings/{booking_id}/accept",
            headers=auth_header(owner_token),
        ),
        200,
        "resource_owner accepts booking",
    )
    if accept_resp.json()["status"] != "accepted":
        raise StepFailed(
            f"booking accept returned status={accept_resp.json()['status']}, "
            "expected 'accepted'"
        )
    print(f"[ok] booking request accepted: {booking_id}")

    # ---------- 2c. configure a pilot service area covering the job's location ----------
    # Without this, quotation generation below would correctly fall back
    # to the flat/'low'-confidence path (that fallback is itself proven
    # correct by services/quotation/tests/test_estimation_engine.py's
    # unit tests) - but this script's whole point is proving the REAL
    # cross-service path works, so it needs an actual service area
    # configured, not just to rely on the fallback silently succeeding.
    area_resp = _expect(
        _request(
            "POST",
            f"{RESOURCE_NETWORK_URL}/v1/service-areas",
            json={
                "name": f"Virudhunagar-{RUN_ID}",
                "district": "Virudhunagar",
                "state": "Tamil Nadu",
                "center_lat": 9.5851,
                "center_lng": 77.9624,
                "radius_km": 15,
                "estimated_water_depth_ft": 280,
                "confidence_band_ft": 40,
            },
            headers=auth_header(contractor_token),
        ),
        201,
        "configure pilot service area",
    )
    print(f"[ok] service area configured: {area_resp.json()['area_id']}")

    # ---------- 3. quote: contractor configures pricing, generates a quote ----------
    _expect(
        _request(
            "POST",
            f"{QUOTATION_URL}/v1/pricing-rules",
            json={
                "job_type": "residential",
                "base_rate_per_ft": 120,
                "casing_rate_per_ft": 40,
                "labour_flat_fee": 5000,
                "transport_flat_fee": 3000,
                "equipment_flat_fee": 2000,
                "installation_flat_fee": 4000,
                "margin_percent": 15,
                "minimum_job_charge": 30000,
                "assumed_depth_ft": 300,
                "depth_confidence_band_ft": 50,
                "depth_overage_rate_per_ft": 150,
            },
            headers=auth_header(contractor_token),
        ),
        200,  # not 201 - POST /v1/pricing-rules has no explicit status_code
        # override in main.py, so FastAPI's default (200) applies even
        # though this creates a row on first call. Found by actually
        # running this script against real services, not assumed.
        "configure pricing rule",
    )
    print("[ok] pricing rule configured")

    quote_resp = _expect(
        _request(
            "POST",
            f"{QUOTATION_URL}/v1/quotations",
            json={
                "job_id": job_id,
                "location": {"lat": 9.5851, "lng": 77.9624},
                "job_type": "residential",
            },
            headers=auth_header(contractor_token),
        ),
        201,
        "generate quotation",
    )
    quotation = quote_resp.json()
    quotation_id = quotation["quotation_id"]
    depth_range = quotation["estimated_depth_range"]
    # Real assertion, not just a log line: with the service area configured
    # above covering these exact coordinates, quotation service's real
    # HTTP call to resource-network's /v1/service-areas/lookup must have
    # found it and used 'medium' confidence (see app/estimation/engine.py) -
    # this is the actual cross-service location-pricing path proven live,
    # not the fallback.
    if depth_range["confidence"] != "medium":
        raise StepFailed(
            f"expected 'medium' confidence (service area should have matched "
            f"the configured Virudhunagar area), got '{depth_range['confidence']}' - "
            f"the cross-service quotation -> resource-network location lookup "
            f"did not behave as expected"
        )
    print(
        f"[ok] quotation generated: {quotation_id}, total={quotation['total_estimate']}, "
        f"confidence={depth_range['confidence']} (confirmed real cross-service calls: "
        f"platform-spine for job verification, resource-network for location-aware "
        f"pricing - both genuinely exercised, not mocked, not just attempted-and-fell-back)"
    )

    # ---------- 4. approve: customer approves the quote ----------
    approve_resp = _expect(
        _request(
            "POST",
            f"{QUOTATION_URL}/v1/quotations/{quotation_id}/approve",
            headers=auth_header(customer_token),
        ),
        200,
        "customer approves quotation",
    )
    if approve_resp.json()["status"] != "approved":
        raise StepFailed(
            f"approve returned status={approve_resp.json()['status']}, expected 'approved'"
        )
    print("[ok] quotation approved")

    # ---------- 5. pay: customer creates a payment for the approved quote ----------
    payment_resp = _expect(
        _request(
            "POST",
            f"{PAYMENTS_URL}/v1/payments",
            json={
                "job_id": job_id,
                "quotation_id": quotation_id,
                "amount": quotation["total_estimate"],
                "idempotency_key": f"integration-{RUN_ID}",
            },
            headers=auth_header(customer_token),
        ),
        201,
        "create payment",
    )
    payment = payment_resp.json()
    payment_id = payment["payment_id"]
    print(
        f"[ok] payment created: {payment_id}, status={payment['status']} "
        f"(real cross-service call to quotation service for exact-amount "
        f"validation happened here, not a mock)"
    )

    # ---------- 6. track: advance the job through its real lifecycle ----------
    # RFC 0001 section 8 order - platform-spine's job_state_machine.py is
    # the actual enforcement, this script just exercises it for real.
    stages = [
        "site_location", "requirement", "estimation", "price_calculation",
        "quotation", "customer_approval", "booking", "resource_allocation",
        "drilling", "progress", "completion",
    ]
    for stage in stages:
        resp = _expect(
            _request(
                "PATCH",
                f"{PLATFORM_SPINE_URL}/v1/jobs/{job_id}/status",
                json={"status": stage},
                headers=auth_header(contractor_token),
            ),
            200,
            f"advance job to '{stage}'",
        )
        if resp.json()["status"] != stage:
            raise StepFailed(
                f"advanced to '{stage}' but job now reports status={resp.json()['status']}"
            )
    print(f"[ok] job advanced through all {len(stages)} lifecycle stages to 'completion'")

    # ---------- 7. complete: contractor logs actual depth/cost, variance computed ----------
    completion_resp = _expect(
        _request(
            "POST",
            f"{PLATFORM_SPINE_URL}/v1/jobs/{job_id}/completion",
            json={
                "actual_depth_ft": 310.0,
                "actual_cost": float(quotation["total_estimate"]) - 500,
            },
            headers=auth_header(contractor_token),
        ),
        201,
        "log job completion",
    )
    completion = completion_resp.json()
    print(
        f"[ok] completion logged: actual_cost={completion['actual_cost']}, "
        f"quoted_total={completion['quoted_total']}, variance={completion['variance']} "
        f"(real cross-service call from platform-spine to quotation for the "
        f"approved total happened here, not a mock)"
    )

    # ---------- 8. payment.completed event: publish, deliver, AND consume ----------
    # Steps 1-7 above only prove the synchronous HTTP flow. This step is
    # what's new: it proves the one real event consumer in this codebase
    # (platform-spine/app/payment_consumer.py) actually works against a
    # real Redis instance in the real docker-compose stack, not just in
    # the unit tests (which call handle_payment_completed() directly,
    # bypassing Redis entirely - see tests/test_payment_consumer.py).
    #
    # First: prove the message is really published to real Redis, before
    # even checking the consumer's effect - if this subscription is set
    # up AFTER payments-data already published (a race), a channel-based
    # pubsub subscriber here would miss it silently and this step would
    # give a false negative. Subscribing before triggering the publish
    # avoids that ordering bug.
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    pubsub.subscribe("payment.completed")
    # Consume the subscribe confirmation message itself so the next
    # get_message() call returns the real event, not this bookkeeping one.
    pubsub.get_message(timeout=5)

    confirm_resp = _expect(
        _request(
            "POST",
            f"{PAYMENTS_URL}/v1/payments/{payment_id}/confirm",
            headers=auth_header(admin_token),
        ),
        200,
        "admin confirms payment (triggers events.payment_completed publish)",
    )
    if confirm_resp.json()["status"] != "completed":
        raise StepFailed(
            f"confirm returned status={confirm_resp.json()['status']}, expected 'completed'"
        )
    print(f"[ok] payment confirmed: {payment_id}, status=completed")

    # Second: prove this script's own subscriber actually received the
    # message over real Redis pub/sub - not platform-spine's internal
    # state, a genuinely independent observation of the same channel.
    published_message = pubsub.get_message(timeout=10)
    if published_message is None or published_message.get("type") != "message":
        raise StepFailed(
            "payment.completed was not observed on real Redis pub/sub within 10s "
            "after confirming the payment - either payments-data did not publish, "
            "or this script's own subscription did not receive it"
        )
    pubsub.close()
    print("[ok] payment.completed observed on real Redis pub/sub (publish side proven)")

    # Third: prove the actual reaction - platform-spine's background
    # subscriber thread (a separate process's thread, running in its own
    # container) picks up that same message and advances the job. This is
    # genuinely asynchronous from this script's perspective (the confirm
    # call above already returned 200 before this happens), so poll
    # rather than assume it's instantaneous.
    deadline = time.monotonic() + EVENT_CONSUMER_TIMEOUT_SECONDS
    final_status = None
    while time.monotonic() < deadline:
        job_check = _expect(
            _request(
                "GET",
                f"{PLATFORM_SPINE_URL}/v1/jobs/{job_id}",
                headers=auth_header(customer_token),
            ),
            200,
            "poll job status after payment.completed",
        )
        final_status = job_check.json()["status"]
        if final_status == "payment":
            break
        time.sleep(EVENT_CONSUMER_POLL_INTERVAL_SECONDS)

    if final_status != "payment":
        raise StepFailed(
            f"job {job_id} did not advance to 'payment' within "
            f"{EVENT_CONSUMER_TIMEOUT_SECONDS}s of payment.completed being published "
            f"(last observed status: '{final_status}') - the message was confirmed "
            f"delivered over Redis (previous step passed), so this points at "
            f"platform-spine's payment_consumer.py subscriber thread specifically, "
            f"not at publishing or delivery"
        )
    print(
        f"[ok] job {job_id} advanced to 'payment' via the real payment_consumer.py "
        f"subscriber thread reacting to a real Redis message - the one real event "
        f"consumer in this codebase, proven end-to-end for the first time by this script"
    )

    print(f"\n=== All steps passed (run {RUN_ID}) ===")


if __name__ == "__main__":
    try:
        run()
    except StepFailed as exc:
        print(f"\n=== INTEGRATION TEST FAILED ===\n{exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"\n=== INTEGRATION TEST FAILED (network error) ===\n{exc}", file=sys.stderr)
        sys.exit(1)
