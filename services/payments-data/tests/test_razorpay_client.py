"""
Pure unit tests for app/gateway/razorpay_client.py - no live Razorpay
credentials needed. Signature verification and paise conversion are pure
functions/HMAC math, fully testable with synthetic values. Order creation
is tested against a mocked httpx call (same pattern as every other
cross-service client test in this codebase - see test_payments.py's
quotation_fetcher mocking).
"""
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from app.gateway.razorpay_client import (
    RazorpayApiError,
    RazorpayConfig,
    RazorpayNotConfigured,
    WebhookSignatureInvalid,
    create_order,
    get_razorpay_config,
    to_paise,
    verify_webhook_signature,
)

FAKE_CONFIG = RazorpayConfig(
    key_id="rzp_test_fake_key_id",
    key_secret="fake_key_secret",
    webhook_secret="fake_webhook_secret",
)


def _sign(body: bytes, secret: str) -> str:
    """Test helper - computes what a real Razorpay webhook signature would
    be for a given body+secret, so tests can construct genuinely valid
    signatures rather than only testing the rejection paths."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ---------- to_paise ----------


def test_to_paise_converts_exact_rupees():
    assert to_paise(Decimal("100.00")) == 10000


def test_to_paise_converts_paise_precision():
    assert to_paise(Decimal("95450.50")) == 9545050


def test_to_paise_rejects_more_than_2_decimal_places():
    # Should be structurally impossible given the MONEY/Numeric(12,2)
    # convention upstream, but this function must not silently round if
    # it ever happens - see the function's own docstring.
    with pytest.raises(ValueError):
        to_paise(Decimal("100.005"))


# ---------- get_razorpay_config ----------


def test_config_raises_when_unset(monkeypatch):
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RazorpayNotConfigured):
        get_razorpay_config()


def test_config_raises_when_partially_set(monkeypatch):
    # Only 2 of 3 set - must still fail closed, not proceed with a None secret.
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_x")
    monkeypatch.delenv("RAZORPAY_WEBHOOK_SECRET", raising=False)
    with pytest.raises(RazorpayNotConfigured):
        get_razorpay_config()


def test_config_loads_when_all_set(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_x")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook_x")
    cfg = get_razorpay_config()
    assert cfg.key_id == "rzp_test_x"
    assert cfg.key_secret == "secret_x"
    assert cfg.webhook_secret == "webhook_x"


# ---------- verify_webhook_signature ----------


def test_valid_signature_passes():
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, FAKE_CONFIG.webhook_secret)
    # Must not raise.
    verify_webhook_signature(body, signature, config=FAKE_CONFIG)


def test_missing_signature_header_rejected():
    body = b'{"event": "payment.captured"}'
    with pytest.raises(WebhookSignatureInvalid):
        verify_webhook_signature(body, None, config=FAKE_CONFIG)


def test_wrong_signature_rejected():
    body = b'{"event": "payment.captured"}'
    with pytest.raises(WebhookSignatureInvalid):
        verify_webhook_signature(body, "0" * 64, config=FAKE_CONFIG)


def test_signature_for_different_body_rejected():
    # Signature computed for one payload must not validate a different one -
    # this is what actually stops a replay/tamper attack, not just "some
    # signature was present."
    original_body = b'{"event": "payment.captured", "amount": 10000}'
    tampered_body = b'{"event": "payment.captured", "amount": 1}'
    signature = _sign(original_body, FAKE_CONFIG.webhook_secret)
    with pytest.raises(WebhookSignatureInvalid):
        verify_webhook_signature(tampered_body, signature, config=FAKE_CONFIG)


def test_signature_with_wrong_secret_rejected():
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, "a_completely_different_secret")
    with pytest.raises(WebhookSignatureInvalid):
        verify_webhook_signature(body, signature, config=FAKE_CONFIG)


def test_verify_uses_get_razorpay_config_when_none_passed(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret_x")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook_from_env")
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, "webhook_from_env")
    verify_webhook_signature(body, signature)  # no config= passed


# ---------- create_order ----------


def test_create_order_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "order_fake123",
        "amount": 9545000,
        "currency": "INR",
        "status": "created",
    }
    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = create_order("payment-abc", Decimal("95450.00"), config=FAKE_CONFIG)

    assert result["id"] == "order_fake123"
    # Verify what was actually sent, not just that something was sent -
    # amount must be in paise (integer), receipt must be our payment_id.
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["amount"] == 9545000
    assert kwargs["json"]["currency"] == "INR"
    assert kwargs["json"]["receipt"] == "payment-abc"
    assert kwargs["json"]["payment_capture"] == 1
    assert kwargs["auth"] == (FAKE_CONFIG.key_id, FAKE_CONFIG.key_secret)


def test_create_order_raises_on_non_2xx():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = '{"error": {"description": "Authentication failed"}}'
    with patch("httpx.post", return_value=mock_response):
        with pytest.raises(RazorpayApiError):
            create_order("payment-abc", Decimal("95450.00"), config=FAKE_CONFIG)


def test_create_order_raises_on_network_error():
    import httpx

    with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
        with pytest.raises(RazorpayApiError):
            create_order("payment-abc", Decimal("95450.00"), config=FAKE_CONFIG)
