"""Body-size cap, optional /metrics token, optional API-docs switch.
Identical in every service (the app/hardening.py it covers is too)."""
import asyncio

import pytest
from app.hardening import BodySizeLimitMiddleware, RequestTooLarge, api_docs_kwargs
from fastapi import FastAPI


def test_declared_oversize_body_is_refused_with_413_before_routing(client):
    resp = client.post("/healthz", content=b"x" * 1_048_577)
    assert resp.status_code == 413
    error = resp.json()["error"]
    assert error["code"] == "REQUEST_TOO_LARGE"
    assert error["trace_id"] == resp.headers["X-Trace-Id"]


def test_body_under_the_limit_reaches_routing(client):
    # /healthz is GET-only: a 405 proves the request got past the size check
    assert client.post("/healthz", content=b"x" * 1000).status_code == 405


def test_limit_is_configurable(client, monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "100")
    assert client.post("/healthz", content=b"x" * 101).status_code == 413
    assert client.post("/healthz", content=b"x" * 100).status_code == 405


def test_streamed_body_without_content_length_is_cut_off():
    """Chunked uploads declare no length; they must be counted as they stream."""
    consumed = []

    async def reader(scope, receive, send):
        while True:
            message = await receive()
            consumed.append(len(message.get("body", b"")))
            if not message.get("more_body"):
                break

    chunks = [
        {"type": "http.request", "body": b"a" * 8, "more_body": True},
        {"type": "http.request", "body": b"b" * 8, "more_body": True},
        {"type": "http.request", "body": b"c" * 8, "more_body": False},
    ]

    async def receive():
        return chunks.pop(0)

    async def send(message):
        pass

    middleware = BodySizeLimitMiddleware(reader, max_bytes=10)
    with pytest.raises(RequestTooLarge):
        asyncio.run(middleware({"type": "http", "headers": []}, receive, send))
    assert sum(consumed) <= 10  # the app was never handed the oversize remainder


def test_metrics_open_by_default(client):
    assert client.get("/metrics").status_code == 200


def test_metrics_require_the_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "s3cret-metrics-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret-metrics-token"})
    assert ok.status_code == 200


def test_api_docs_switch(monkeypatch):
    assert FastAPI(**api_docs_kwargs()).docs_url == "/docs"
    monkeypatch.setenv("ENABLE_API_DOCS", "0")
    off = FastAPI(**api_docs_kwargs())
    assert (off.docs_url, off.redoc_url, off.openapi_url) == (None, None, None)


def test_tokens_missing_required_claims_are_rejected():
    """A token with no exp could never expire; one with no role/sub would
    surface later as a KeyError (a 500). Reject them at decode time."""
    import time

    import jwt
    from app.security import JWT_SECRET, decode_access_token

    soon = int(time.time()) + 60
    for claims in (
        {"sub": "u", "role": "customer"},  # no exp
        {"role": "customer", "exp": soon},  # no sub
        {"sub": "u", "exp": soon},  # no role
    ):
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(jwt.encode(claims, JWT_SECRET, algorithm="HS256"))
    good = jwt.encode({"sub": "u", "role": "customer", "exp": soon}, JWT_SECRET, algorithm="HS256")
    assert decode_access_token(good)["role"] == "customer"
