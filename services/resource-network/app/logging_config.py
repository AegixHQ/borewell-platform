"""
Structured JSON logging setup.

Per-service copy, not packages/ - same reasoning as events.py in this
same app/ folder (see docs/adr/0003-events-package-location-and-docker-wiring.md):
each service's Dockerfile build context is ./services/<name>/ only, so
anything in a shared packages/ folder never reaches the built image.

WHY THIS EXISTS: Architecture doc section 11 claims "structured JSON logs
per service... are sufficient to know if something is broken" - checked
against the actual code, that was aspirational, not true. Every service
had `logger = logging.getLogger(__name__)` calls but no `basicConfig()`
anywhere, which means Python's logging defaults applied: root logger at
WARNING level, no handler configured. Concretely this meant every
`logger.info(...)` call (event-published confirmations, the happy path)
was silently dropped, and the `logger.warning`/`.exception()` calls that
DID print went to stderr as plain interpolated text with no timestamp,
no service name, and no structure - unusable by any log aggregator, and
barely usable by a human reading `docker compose logs` across 4
interleaved services. Verified directly (not assumed) by running
`logger.info(...)` against an unconfigured logger and observing it
produce zero output.

This fixes both problems: INFO and above now actually emit, and every
line is one JSON object a log aggregator can parse without a custom
parser, while remaining perfectly readable as plain text too (each field
is on the line, just JSON-quoted).
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone

SERVICE_NAME = "resource-network"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # record.getMessage() applies %s-style interpolation (e.g.
        # logger.info("event.published channel=%s", channel)) - every
        # existing logger.X(...) call site in this service keeps working
        # completely unchanged, this formatter is the only thing that's new.
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # trace_id is attached via LoggerAdapter (see request_logging_middleware
        # in main.py) when logging inside a request; background-thread logging
        # (payment_consumer's subscriber loop) has no request, so no trace_id -
        # that absence is itself informative (tells you it's not tied to any
        # one HTTP call), not a bug to paper over with a fake value.
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if record.exc_info:
            # logger.exception(...) call sites (payment_consumer.py's crash
            # handlers) - keep the real traceback, don't swallow it for
            # the sake of a tidier JSON blob. A log line that hides the
            # actual exception is worse than an ugly one that has it.
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    """
    Call once, at import time, before any request is served. Idempotent -
    safe to call more than once (e.g. once from main.py, again from a test
    fixture) without producing duplicate log lines, because it clears any
    handlers it previously added before adding new ones.
    """
    root = logging.getLogger()
    # LOG_LEVEL env var, not hardcoded - so a real incident can be debugged
    # with DEBUG-level detail via a restart-with-env-var, not a code change
    # and redeploy. Defaults to INFO: WARNING (Python's own default) was
    # exactly the bug this file fixes, so INFO is the deliberate new floor.
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # uvicorn's own access-log lines are separate from this app's `logger.*`
    # calls (they come from uvicorn.access) - leave uvicorn's own format
    # alone (it's already reasonably structured on its own, and re-wrapping
    # a request-completed line uvicorn already emits would just duplicate
    # request_logging_middleware's own line in main.py). Only silence its
    # duplicate startup banner noise at DEBUG level; nothing else touched.
    logging.getLogger("uvicorn.access").propagate = True
