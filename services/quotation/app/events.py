"""
Redis pub/sub event publisher - quotation service only publishes
job.quoted, the one event that originates here (RFC 0001 section 8 /
Architecture doc section 7's data-flow diagram).

Per ADR-0003 (docs/adr/0003-events-package-location-and-docker-wiring.md):
this used to live at packages/events/__init__.py, shared across services.
Moved to a per-service copy - see that ADR for why (STRUCTURE.md scopes
packages/ to contracts-only, and the shared module was never actually
reachable from inside this service's Docker build context).

Design decisions (unchanged from the original shared module - see
platform-spine/app/events.py for the fuller version of this comment):
lazy Redis connection, fire-and-forget publish, never raises.
"""
import json
import logging
import os
from decimal import Decimal

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client = None


def _get_client():
    global _client
    if _client is None:
        import redis
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    return _client


def publish(channel: str, payload: dict) -> bool:
    """Publish an event. Returns True if delivered, False if dropped."""
    try:
        _get_client().publish(channel, json.dumps(payload, default=str))
        logger.info("event.published channel=%s", channel)
        return True
    except Exception as exc:
        logger.warning("event.dropped channel=%s reason=%s", channel, exc)
        return False


def job_quoted(job_id: str, quotation_id: str, total_estimate: Decimal, quoted_at) -> bool:
    if hasattr(quoted_at, "isoformat"):
        quoted_at = quoted_at.isoformat()
    # total_estimate serialized as a string in the payload (json.dumps'
    # default=str handles the Decimal), same reasoning as the HTTP contract
    # fix in this session: a bare JSON number round-trips through float in
    # any consumer and silently reintroduces the Bug 2 precision loss this
    # value was specifically fixed to avoid (see app/models.py's MONEY
    # comment). A consumer of this event should parse it back with
    # Decimal(str(x)), same convention as everywhere else in this codebase.
    return publish("job.quoted", {
        "job_id": job_id,
        "quotation_id": quotation_id,
        "total_estimate": str(total_estimate),
        "quoted_at": str(quoted_at),
    })
