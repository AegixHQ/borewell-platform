"""An exception that escapes a dependency must be logged server-side with its
traceback and must reach the client as the shared error format - never a
bare Starlette 500, never any internals."""
import logging

from app.database import get_db
from app.main import app


def test_unhandled_dependency_error_is_logged_and_leaks_nothing(client, caplog):
    def broken_db():
        raise RuntimeError("secret-internal-detail postgres://user:pw@db/x")

    app.dependency_overrides[get_db] = broken_db
    with caplog.at_level(logging.ERROR):
        resp = client.get("/readyz")

    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error["trace_id"] == resp.headers["X-Trace-Id"]
    assert "secret-internal-detail" not in resp.text
    assert any(
        "request.failed" in r.getMessage() and r.exc_info and r.trace_id == error["trace_id"]
        for r in caplog.records
    ), "the failure must be logged with its traceback and the same trace_id the client received"
