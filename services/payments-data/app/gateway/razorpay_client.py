"""
Razorpay integration - order creation (Orders API) and webhook signature
verification. Raw httpx, no razorpay-python SDK dependency - same
convention as every other cross-service/cross-vendor call in this
codebase (see e.g. app/payments/quotation_client.py, quotation service's
job_client.py) rather than introducing a new dependency pattern for one
integration.

HONEST CAVEAT (read before wiring real keys): this was written without
live access to Razorpay's current API documentation - no internet access
was available in the environment that built it. What's here follows
Razorpay's long-stable, well-documented Orders API request/response shape
and the standard HMAC-SHA256 webhook signature scheme, both of which have
been unchanged for years and are exactly what every razorpay-python SDK
release still implements under the hood - but this should be checked
against https://razorpay.com/docs/api/orders/ and
https://razorpay.com/docs/webhooks/validate-test/ before this ever
touches a real payment, not assumed correct from memory. If anything below
doesn't match current Razorpay docs, trust the docs and fix this file, not
the other way around.

Two real API keys are needed to actually use this, both from the Razorpay
Dashboard (Settings -> API Keys for the first two, Settings -> Webhooks
for the third):
- RAZORPAY_KEY_ID       (public - also returned to the frontend for Checkout)
- RAZORPAY_KEY_SECRET   (private - used to authenticate the Orders API call)
- RAZORPAY_WEBHOOK_SECRET (private - separate from KEY_SECRET; used only
  to verify webhook signatures, configured when you set up the webhook
  endpoint in the Razorpay dashboard, not derived from the API keys)

Until those are set, order creation and webhook verification both fail
closed (RazorpayNotConfigured) rather than silently no-op or fake success -
see get_razorpay_config()'s docstring.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from decimal import Decimal

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayNotConfigured(Exception):
    """Real credentials aren't set. Distinct from RazorpayApiError (a
    genuine call to Razorpay that failed) - this means the call was never
    even attempted, which should never be confused with "Razorpay said no."
    """


class RazorpayApiError(Exception):
    """Razorpay's API returned a non-2xx response to a real, authenticated
    call."""


class WebhookSignatureInvalid(Exception):
    """The X-Razorpay-Signature header didn't match what we computed - the
    request is not trusted and must not be processed. Distinguished from
    a missing signature (also rejected, but a different failure mode
    worth distinguishing in logs)."""


@dataclass
class RazorpayConfig:
    key_id: str
    key_secret: str
    webhook_secret: str


def get_razorpay_config() -> RazorpayConfig:
    """Reads the 3 required env vars. Raises RazorpayNotConfigured if any
    are missing - deliberately fails closed. A payment flow that silently
    skipped real gateway verification because a var was unset would be a
    far worse failure mode than a clear 502 telling an operator to check
    their environment."""
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not key_id or not key_secret or not webhook_secret:
        raise RazorpayNotConfigured(
            "RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_WEBHOOK_SECRET "
            "must all be set - see services/payments-data/.env.example."
        )
    return RazorpayConfig(key_id=key_id, key_secret=key_secret, webhook_secret=webhook_secret)


def to_paise(amount: Decimal) -> int:
    """Razorpay's Orders API takes amount in the currency's smallest unit
    (paise for INR, i.e. amount * 100), as an integer - never a decimal or
    float. Rejects anything that isn't already at 2-decimal-place INR
    precision (which every amount in this platform already is - see the
    MONEY/Numeric(12,2) convention across every service) rather than
    silently rounding, since silently rounding a payment amount is exactly
    the kind of bug that costs real money."""
    scaled = amount * 100
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f"amount {amount} does not convert to a whole number of paise - "
            "this should be impossible given the MONEY/Numeric(12,2) convention "
            "used everywhere upstream; check the caller."
        )
    return int(scaled)


def create_order(payment_id: str, amount: Decimal, config: RazorpayConfig | None = None) -> dict:
    """Creates a Razorpay Order. Returns Razorpay's response dict (at
    minimum: {"id": "order_...", "amount": <paise>, "currency": "INR",
    "status": "created"}).

    payment_id is passed as Razorpay's `receipt` field - Razorpay's own
    doc description for `receipt`: "a unique identifier from your end,
    for your own reference/reconciliation." This is what lets a support
    agent look up a Razorpay order by our internal payment_id from the
    Razorpay dashboard directly, without needing a separate mapping table.
    """
    cfg = config or get_razorpay_config()
    try:
        response = httpx.post(
            f"{RAZORPAY_API_BASE}/orders",
            auth=(cfg.key_id, cfg.key_secret),  # HTTP Basic Auth - Razorpay's documented scheme
            json={
                "amount": to_paise(amount),
                "currency": "INR",
                "receipt": payment_id,
                "payment_capture": 1,  # auto-capture, not authorize-then-manually-capture
            },
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise RazorpayApiError(f"could not reach Razorpay: {exc}") from exc

    if response.status_code not in (200, 201):
        raise RazorpayApiError(
            f"Razorpay order creation returned {response.status_code}: {response.text}"
        )
    return response.json()


def verify_webhook_signature(
    raw_body: bytes, signature_header: str | None, config: RazorpayConfig | None = None
) -> None:
    """Verifies X-Razorpay-Signature against the raw request body, per
    Razorpay's documented webhook signature scheme: HMAC-SHA256 of the
    exact raw request body bytes, keyed with the webhook secret, compared
    against the header as a hex digest.

    CRITICAL: this must run against the raw, unparsed request bytes, not
    a re-serialized version of the parsed JSON - a re-serialization can
    differ in whitespace/key-ordering from what Razorpay actually signed,
    which would make every signature check fail (or, far worse if done
    wrong in the other direction, appear to pass when it shouldn't -
    hence taking `raw_body: bytes` as the explicit parameter here rather
    than a dict, so a caller can't accidentally pass the parsed/re-
    serialized form).

    Raises WebhookSignatureInvalid if the signature is missing or doesn't
    match. Callers MUST reject the request (4xx) on this exception before
    doing anything else with the payload - the payload is untrusted until
    this passes.
    """
    cfg = config or get_razorpay_config()
    if not signature_header:
        raise WebhookSignatureInvalid("X-Razorpay-Signature header missing")

    expected = hmac.new(
        cfg.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    # hmac.compare_digest, not ==: constant-time comparison, so response
    # timing can't leak how many leading bytes of the signature matched
    # (a real, if narrow, side-channel for forging a valid signature byte
    # by byte). This is the standard, correct way to compare a computed
    # HMAC against an attacker-supplied one - never use == here.
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureInvalid("signature does not match computed HMAC")
