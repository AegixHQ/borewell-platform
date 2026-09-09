"""
Endpoint-level tests for POST /v1/payments/{id}/create-order and
POST /v1/payments/webhook - proves the wiring in main.py is correct, not
just the underlying app/gateway/razorpay_client.py functions in isolation
(see test_razorpay_client.py for those). Razorpay calls are mocked
(unittest.mock.patch), matching this file's existing pattern for
quotation_fetcher - no live credentials needed to run these.
"""
import hashlib
import hmac
import json
import uuid
from unittest.mock import patch

from app.gateway.razorpay_client import RazorpayConfig

from tests.conftest import make_token

CUST_TOKEN = make_token("cust-order-1", "customer")

FAKE_CFG = RazorpayConfig(
    key_id="rzp_test_fake", key_secret="fake_secret", webhook_secret="fake_webhook_secret"
)

# Reused verbatim across every webhook test below where verify_webhook_signature
# is mocked out (so the header VALUE is never actually checked) - a named
# constant instead of repeating the same long dict literal 6+ times.
_WEBHOOK_HEADERS = {"X-Razorpay-Signature": "irrelevant-mocked", "Content-Type": "application/json"}


def _payment_payload(**overrides):
    payload = {
        "job_id": str(uuid.uuid4()),
        "quotation_id": str(uuid.uuid4()),
        "amount": 95450.0,
        "idempotency_key": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return payload


def _create_pending_payment(client, job_id=None):
    """Helper: create a real pending payment via the normal flow, so
    create-order/webhook tests have a genuine row to operate against."""
    from tests.conftest import DEFAULT_JOB_ID

    resp = client.post(
        "/v1/payments",
        json=_payment_payload(job_id=job_id or DEFAULT_JOB_ID),
        headers={"Authorization": f"Bearer {CUST_TOKEN}"},
    )
    assert resp.status_code == 201
    return resp.json()


def _sign(body: bytes, secret: str = FAKE_CFG.webhook_secret) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ---------- POST /v1/payments/{id}/create-order ----------


def test_create_order_success(client):
    payment = _create_pending_payment(client)

    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_fake123", "amount": 9545000, "currency": "INR"},
    ):
        resp = client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["razorpay_order_id"] == "order_fake123"
    assert body["razorpay_key_id"] == "rzp_test_fake"
    assert body["amount_paise"] == 9545000

    # The payment row itself should now carry the order_id.
    get_resp = client.get(
        f"/v1/payments/{payment['payment_id']}", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert get_resp.json()["razorpay_order_id"] == "order_fake123"


def test_create_order_is_idempotent_reuses_existing_order(client):
    payment = _create_pending_payment(client)

    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_first_call", "amount": 9545000, "currency": "INR"},
    ) as mock_create:
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )
        # Second call - a customer reopening the payment screen - must
        # NOT call Razorpay's create_order a second time.
        second = client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )
    assert mock_create.call_count == 1
    assert second.json()["razorpay_order_id"] == "order_first_call"


def test_create_order_rejects_non_pending_payment(client):
    payment = _create_pending_payment(client)
    admin_token = make_token("admin-order-1", "admin")
    client.post(
        f"/v1/payments/{payment['payment_id']}/confirm",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        f"/v1/payments/{payment['payment_id']}/create-order",
        headers={"Authorization": f"Bearer {CUST_TOKEN}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PAYMENT_NOT_PENDING"


def test_create_order_rejects_other_customer(client):
    payment = _create_pending_payment(client)
    other_token = make_token("cust-order-other", "customer")

    resp = client.post(
        f"/v1/payments/{payment['payment_id']}/create-order",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_create_order_returns_502_when_gateway_not_configured(client):
    from app.gateway.razorpay_client import RazorpayNotConfigured

    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", side_effect=RazorpayNotConfigured("not set")):
        resp = client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "GATEWAY_NOT_CONFIGURED"


def test_create_order_returns_502_on_razorpay_api_error(client):
    from app.gateway.razorpay_client import RazorpayApiError

    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order", side_effect=RazorpayApiError("auth failed")
    ):
        resp = client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "GATEWAY_ERROR"


# ---------- POST /v1/payments/webhook ----------


def _webhook_payload(event, order_id, payment_id="pay_fake123"):
    return {
        "event": event,
        "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}},
    }


def test_webhook_payment_captured_completes_payment(client):
    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_webhook1", "amount": 9545000, "currency": "INR"},
    ):
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )

    body = json.dumps(_webhook_payload("payment.captured", "order_webhook1")).encode()

    with patch("app.main.verify_webhook_signature") as mock_verify:
        # verify_webhook_signature raises on failure, returns None on
        # success - patch as a no-op success, since the crypto itself is
        # already proven in test_razorpay_client.py and this test is
        # about the endpoint's REACTION to a verified webhook, not the
        # signature math itself.
        mock_verify.return_value = None
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    check = client.get(
        f"/v1/payments/{payment['payment_id']}", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert check.json()["status"] == "completed"
    assert check.json()["razorpay_payment_id"] == "pay_fake123"


def test_webhook_payment_failed_fails_payment(client):
    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_webhook2", "amount": 9545000, "currency": "INR"},
    ):
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )

    body = json.dumps(_webhook_payload("payment.failed", "order_webhook2")).encode()

    with patch("app.main.verify_webhook_signature", return_value=None):
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"

    check = client.get(
        f"/v1/payments/{payment['payment_id']}", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert check.json()["status"] == "failed"


def test_webhook_rejects_invalid_signature(client):
    from app.gateway.razorpay_client import WebhookSignatureInvalid

    body = json.dumps(_webhook_payload("payment.captured", "order_x")).encode()
    with patch("app.main.verify_webhook_signature", side_effect=WebhookSignatureInvalid("bad sig")):
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers={"X-Razorpay-Signature": "wrong", "Content-Type": "application/json"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


def test_webhook_ignores_unhandled_event_types(client):
    body = json.dumps({"event": "order.paid", "payload": {}}).encode()
    with patch("app.main.verify_webhook_signature", return_value=None):
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_no_matching_payment_is_not_an_error(client):
    body = json.dumps(_webhook_payload("payment.captured", "order_never_created")).encode()
    with patch("app.main.verify_webhook_signature", return_value=None):
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_matching_payment"


def test_webhook_captured_is_idempotent_on_redelivery(client):
    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_redeliver", "amount": 9545000, "currency": "INR"},
    ):
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )

    body = json.dumps(_webhook_payload("payment.captured", "order_redeliver")).encode()
    with patch("app.main.verify_webhook_signature", return_value=None):
        first = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
        # Razorpay redelivers the same event - must not double-fire the
        # payment_completed event or error.
        second = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert first.json()["status"] == "completed"
    assert second.json()["status"] == "already_completed"


def test_webhook_failed_cannot_override_already_completed_payment(client):
    # Out-of-order delivery: a late payment.failed webhook must never
    # regress an already-completed payment back to failed.
    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_outoforder", "amount": 9545000, "currency": "INR"},
    ):
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )

    captured_body = json.dumps(_webhook_payload("payment.captured", "order_outoforder")).encode()
    failed_body = json.dumps(_webhook_payload("payment.failed", "order_outoforder")).encode()

    with patch("app.main.verify_webhook_signature", return_value=None):
        client.post(
            "/v1/payments/webhook",
            content=captured_body,
            headers={"X-Razorpay-Signature": "x", "Content-Type": "application/json"},
        )
        late_failed = client.post(
            "/v1/payments/webhook",
            content=failed_body,
            headers={"X-Razorpay-Signature": "x", "Content-Type": "application/json"},
        )
    assert late_failed.json()["status"] == "ignored_already_completed"

    check = client.get(
        f"/v1/payments/{payment['payment_id']}", headers={"Authorization": f"Bearer {CUST_TOKEN}"}
    )
    assert check.json()["status"] == "completed"


def test_webhook_unexpected_payload_shape_returns_400(client):
    # Signature "valid" (mocked) but payload doesn't have payload.payment.entity.
    body = json.dumps({"event": "payment.captured", "payload": {}}).encode()
    with patch("app.main.verify_webhook_signature", return_value=None):
        resp = client.post(
            "/v1/payments/webhook",
            content=body,
            headers=_WEBHOOK_HEADERS,
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNEXPECTED_PAYLOAD_SHAPE"


def test_webhook_end_to_end_with_real_unmocked_signature_verification(client, monkeypatch):
    # Unlike every other webhook test above (which mocks
    # verify_webhook_signature entirely, isolating "does the endpoint
    # react correctly" from "is the crypto correct"), this one exercises
    # the REAL verify_webhook_signature function through the real HTTP
    # request, proving the raw-body-reading wiring in main.py is actually
    # correct end to end - a body-re-serialization bug (see
    # razorpay_client.py's docstring on why raw bytes matter) would only
    # be caught by a test like this one, not by the mocked tests above.
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_e2e")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "e2e_key_secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "e2e_webhook_secret")

    payment = _create_pending_payment(client)
    with patch("app.main.get_razorpay_config", return_value=FAKE_CFG), patch(
        "app.main.create_order",
        return_value={"id": "order_e2e", "amount": 9545000, "currency": "INR"},
    ):
        client.post(
            f"/v1/payments/{payment['payment_id']}/create-order",
            headers={"Authorization": f"Bearer {CUST_TOKEN}"},
        )

    body = json.dumps(_webhook_payload("payment.captured", "order_e2e")).encode()
    real_signature = _sign(body, secret="e2e_webhook_secret")

    resp = client.post(
        "/v1/payments/webhook",
        content=body,
        headers={"X-Razorpay-Signature": real_signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # And prove a tampered body with the SAME signature is correctly
    # rejected - the actual security property this whole mechanism exists
    # for, tested through the real endpoint, not just the isolated
    # function (already covered in test_razorpay_client.py, but worth
    # confirming the endpoint didn't accidentally skip verification).
    tampered_body = json.dumps(_webhook_payload("payment.captured", "order_e2e_DIFFERENT")).encode()
    tampered_resp = client.post(
        "/v1/payments/webhook",
        content=tampered_body,
        headers={"X-Razorpay-Signature": real_signature, "Content-Type": "application/json"},
    )
    assert tampered_resp.status_code == 400
    assert tampered_resp.json()["error"]["code"] == "INVALID_SIGNATURE"
