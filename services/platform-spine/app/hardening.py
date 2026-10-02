"""
Small, dependency-free API hardening shared by every service (the file is
byte-identical in all four - services stay independent, see STRUCTURE.md).

  BodySizeLimitMiddleware  caps request bodies (default 1 MiB; env
                           MAX_REQUEST_BODY_BYTES). The public auth endpoints
                           otherwise accept bodies of any size.
  api_docs_kwargs()        ENABLE_API_DOCS=0 switches off /docs, /redoc and
                           /openapi.json (they publish the whole API surface).
                           Default stays ON so local development is unchanged;
                           docker-compose.prod.yml turns it off.
  metrics_guard            if METRICS_TOKEN is set, /metrics requires
                           "Authorization: Bearer <token>". Unset = open, as
                           before (Prometheus scrapes it inside the compose
                           network). See docs/deployment/PRODUCTION.md.
"""
import hmac
import json
import os
import uuid

from fastapi import HTTPException, Request, status

_DEFAULT_MAX_BODY_BYTES = 1_048_576  # 1 MiB: far above any real JSON payload here


class RequestTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Pure ASGI (not BaseHTTPMiddleware) so it can stop a body mid-stream.

    A declared Content-Length over the limit is refused with 413 before a
    byte is read. A chunked body with no Content-Length is counted as it
    streams and cut off at the limit; FastAPI reports that as a 400 body-
    parsing error, which is fine - the point is that memory stays bounded.
    """

    def __init__(self, app, max_bytes: int | None = None) -> None:
        self.app = app
        self._max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        if self._max_bytes is not None:
            return self._max_bytes
        return int(os.getenv("MAX_REQUEST_BODY_BYTES", str(_DEFAULT_MAX_BODY_BYTES)))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        limit = self.max_bytes
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0  # malformed: let the server's own parsing reject it
                if declared > limit:
                    return await self._reject(scope, send, limit)
                break

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestTooLarge()
            return message

        await self.app(scope, limited_receive, send)

    async def _reject(self, scope, send, limit: int) -> None:
        trace_id = (scope.get("state") or {}).get("trace_id") or str(uuid.uuid4())
        body = json.dumps(
            {
                "error": {
                    "code": "REQUEST_TOO_LARGE",
                    "message": f"Request body exceeds the {limit}-byte limit.",
                    "trace_id": trace_id,
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def api_docs_kwargs() -> dict:
    """Spread into FastAPI(...): turns the interactive docs off when ENABLE_API_DOCS=0."""
    if os.getenv("ENABLE_API_DOCS", "1") == "0":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def metrics_guard(request: Request) -> None:
    token = os.getenv("METRICS_TOKEN", "")
    if not token:
        return
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "METRICS_AUTH_REQUIRED", "message": "Metrics require a bearer token."},
        )
