"""Cash payments (customer chooses, contractor confirms) and the Razorpay
client-side verify endpoint."""

import hashlib
import hmac
import uuid
from unittest.mock import patch

from app.gateway.razorpay_client import RazorpayConfig

from tests.conftest import make_token
from tests.test_payments import CUST_TOKEN, _payment_payload

CONTRACTOR = make_token("contractor-1", "contractor")
OWNER = make_token("owner-1", "resource_owner")
OTHER_CUST = make_token("cust-2", "customer")
CFG = RazorpayConfig(key_id="rzp_test_x", key_secret="key_secret_x", webhook_secret="wh_x")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _new_payment(client):
    resp = client.post("/v1/payments", json=_payment_payload(), headers=_h(CUST_TOKEN))
    assert resp.status_code == 201
    return resp.json()["payment_id"]


def _create(client, quotation_id):
    payload = _payment_payload(quotation_id=quotation_id)
    return client.post("/v1/payments", json=payload, headers=_h(CUST_TOKEN))


def _post(client, pid, action, token, **kw):
    return client.post(f"/v1/payments/{pid}/{action}", headers=_h(token), **kw)


def _sig(order, pay, secret=CFG.key_secret):
    return hmac.new(secret.encode(), f"{order}|{pay}".encode(), hashlib.sha256).hexdigest()


def _with_order(client, pid, order_id="order_abc"):
    with patch("app.main.get_razorpay_config", return_value=CFG), patch(
        "app.main.create_order", return_value={"id": order_id, "amount": 9545000}
    ):
        assert _post(client, pid, "create-order", CUST_TOKEN).status_code == 200


# ---------- cash ----------
def test_new_payment_defaults_to_online(client):
    pid = _new_payment(client)
    assert client.get(f"/v1/payments/{pid}", headers=_h(CUST_TOKEN)).json()["method"] == "online"


def test_cash_flow_customer_chooses_contractor_confirms(client):
    pid = _new_payment(client)
    chosen = _post(client, pid, "choose-cash", CUST_TOKEN)
    assert chosen.status_code == 200
    assert chosen.json()["method"] == "cash" and chosen.json()["status"] == "pending"

    done = _post(client, pid, "confirm-cash", CONTRACTOR)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["cash_confirmed_at"] is not None


def test_customer_cannot_confirm_their_own_cash(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    assert _post(client, pid, "confirm-cash", CUST_TOKEN).status_code == 403
    assert client.get(f"/v1/payments/{pid}", headers=_h(CUST_TOKEN)).json()["status"] == "pending"


def test_resource_owner_cannot_confirm_cash(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    assert _post(client, pid, "confirm-cash", OWNER).status_code == 403


def test_contractor_cannot_confirm_a_payment_the_customer_has_not_set_to_cash(client):
    pid = _new_payment(client)
    resp = _post(client, pid, "confirm-cash", CONTRACTOR)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NOT_A_CASH_PAYMENT"


def test_confirm_cash_twice_is_harmless_and_fires_one_event(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    with patch("app.main.events.payment_completed") as fired:
        assert _post(client, pid, "confirm-cash", CONTRACTOR).status_code == 200
        assert _post(client, pid, "confirm-cash", CONTRACTOR).status_code == 200
    assert fired.call_count == 1


def test_confirming_cash_announces_payment_completed(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    with patch("app.main.events.payment_completed") as fired:
        _post(client, pid, "confirm-cash", CONTRACTOR)
    assert fired.call_args.kwargs["payment_id"] == pid


def test_other_customer_cannot_choose_cash_for_my_payment(client):
    pid = _new_payment(client)
    assert _post(client, pid, "choose-cash", OTHER_CUST).status_code == 403


def test_cannot_choose_cash_once_an_online_order_exists(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    resp = _post(client, pid, "choose-cash", CUST_TOKEN)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ONLINE_ORDER_OPEN"


def test_cash_payment_cannot_open_a_razorpay_order(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    with patch("app.main.get_razorpay_config", return_value=CFG), patch(
        "app.main.create_order"
    ) as mk:
        resp = _post(client, pid, "create-order", CUST_TOKEN)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "PAYMENT_IS_CASH"
    mk.assert_not_called()


def test_customer_can_switch_back_to_online_before_confirmation(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    back = _post(client, pid, "choose-online", CUST_TOKEN)
    assert back.json()["method"] == "online"
    assert _post(client, pid, "confirm-cash", CONTRACTOR).status_code == 409


def test_cannot_switch_method_after_completion(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    _post(client, pid, "confirm-cash", CONTRACTOR)
    assert _post(client, pid, "choose-online", CUST_TOKEN).status_code == 409


def test_rejecting_cash_closes_it_and_lets_the_customer_start_over(client):
    quotation = str(uuid.uuid4())
    first = _create(client, quotation)
    pid = first.json()["payment_id"]
    _post(client, pid, "choose-cash", CUST_TOKEN)
    rejected = _post(client, pid, "reject-cash", CONTRACTOR)
    assert rejected.json()["status"] == "failed"
    # confirm after reject is refused
    assert _post(client, pid, "confirm-cash", CONTRACTOR).status_code == 409
    # a fresh payment for the same quotation is allowed again
    retry = _create(client, quotation)
    assert retry.status_code == 201 and retry.json()["payment_id"] != pid


def test_cannot_reject_cash_that_was_already_confirmed(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    _post(client, pid, "confirm-cash", CONTRACTOR)
    resp = _post(client, pid, "reject-cash", CONTRACTOR)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "PAYMENT_ALREADY_COMPLETED"


def test_contractor_sees_the_customers_cash_payment_in_the_list(client):
    pid = _new_payment(client)
    _post(client, pid, "choose-cash", CUST_TOKEN)
    rows = client.get("/v1/payments", headers=_h(CONTRACTOR)).json()
    row = next(r for r in rows if r["payment_id"] == pid)
    assert row["method"] == "cash" and row["status"] == "pending"


# ---------- razorpay verify ----------
def test_verify_completes_the_payment_with_a_valid_signature(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    body = {
        "razorpay_order_id": "order_abc",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": _sig("order_abc", "pay_123"),
    }
    with patch("app.main.get_razorpay_config", return_value=CFG), patch(
        "app.gateway.razorpay_client.get_razorpay_config", return_value=CFG
    ), patch("app.main.events.payment_completed") as fired:
        resp = _post(client, pid, "verify", CUST_TOKEN, json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["razorpay_payment_id"] == "pay_123"
    assert fired.call_count == 1


def test_verify_rejects_a_forged_signature(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    body = {
        "razorpay_order_id": "order_abc",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": _sig("order_abc", "pay_123", secret="not-the-secret"),
    }
    with patch("app.gateway.razorpay_client.get_razorpay_config", return_value=CFG):
        resp = _post(client, pid, "verify", CUST_TOKEN, json=body)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert client.get(f"/v1/payments/{pid}", headers=_h(CUST_TOKEN)).json()["status"] == "pending"


def test_verify_rejects_an_order_that_is_not_this_payments(client):
    pid = _new_payment(client)
    _with_order(client, pid, "order_abc")
    body = {
        "razorpay_order_id": "order_other",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": _sig("order_other", "pay_123"),
    }
    with patch("app.gateway.razorpay_client.get_razorpay_config", return_value=CFG):
        resp = _post(client, pid, "verify", CUST_TOKEN, json=body)
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "ORDER_MISMATCH"


def test_verify_is_customer_only_and_owner_only(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    body = {
        "razorpay_order_id": "order_abc",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": _sig("order_abc", "pay_123"),
    }
    assert _post(client, pid, "verify", CONTRACTOR, json=body).status_code == 403
    assert _post(client, pid, "verify", OTHER_CUST, json=body).status_code == 403


def test_verify_twice_is_harmless(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    body = {
        "razorpay_order_id": "order_abc",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": _sig("order_abc", "pay_123"),
    }
    with patch("app.gateway.razorpay_client.get_razorpay_config", return_value=CFG), patch(
        "app.main.events.payment_completed"
    ) as fired:
        assert _post(client, pid, "verify", CUST_TOKEN, json=body).status_code == 200
        assert _post(client, pid, "verify", CUST_TOKEN, json=body).status_code == 200
    assert fired.call_count == 1


def test_verify_without_gateway_keys_is_a_clear_502_not_a_pass(client):
    pid = _new_payment(client)
    _with_order(client, pid)
    body = {"razorpay_order_id": "order_abc", "razorpay_payment_id": "p", "razorpay_signature": "s"}
    with patch.dict("os.environ", {}, clear=False):
        import os

        for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
            os.environ.pop(k, None)
        resp = _post(client, pid, "verify", CUST_TOKEN, json=body)
    assert resp.status_code == 502 and resp.json()["error"]["code"] == "GATEWAY_NOT_CONFIGURED"
