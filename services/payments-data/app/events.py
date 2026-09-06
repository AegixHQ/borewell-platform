"""
Redis pub/sub event publisher - payments-data only publishes
payment.completed, matching packages/contracts/events/payment.completed.schema.json.

Per ADR-0003 (docs/adr/0003-events-package-location-and-docker-wiring.md):
this used to live at packages/events/__init__.py, shared across services.
Moved to a per-service copy - see that ADR for why. See
platform-spine/app/events.py for the fuller version of the lazy-connect /
fire-and-forget design rationale, unchanged here.
"""
import json
import logging
import os
from datetime import datetime
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


def payment_completed(
    payment_id: str, job_id: str, amount: Decimal, completed_at: datetime
) -> bool:
    # amount serialized as a string (str(Decimal(...))) for the same reason
    # as quotation's job_quoted event - a bare JSON number would round-trip
    # through float in any consumer and reintroduce the Bug 2 precision
    # loss this value was fixed to avoid. Matches
    # packages/contracts/events/payment.completed.schema.json's required
    # fields exactly (payment_id, job_id, amount, completed_at) - that
    # schema predates this wiring and is the real contract here.
    return publish("payment.completed", {
        "payment_id": payment_id,
        "job_id": job_id,
        "amount": str(amount),
        "completed_at": completed_at.isoformat(),
    })
