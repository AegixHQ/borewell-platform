"""
Redis pub/sub event bus - shared across all services.

Design decisions:
- Lazy connection: Redis client created on first publish, not at import
  time. This means the module can be imported in tests without a live Redis.
- Fire-and-forget: publish() never raises. If Redis is unreachable the event
  is logged and dropped. Authoritative state lives in each service's Postgres
  DB - a dropped event means a downstream service didn't react, not data loss.
  Acceptable for MVP; real delivery guarantees need a persistent broker (see
  RFC 0001 section 12 for when that upgrade gets justified).
- No module-level connection: the PR's pattern of
      redis_client = redis.Redis.from_url(...) at module level
  crashes the service at import time if Redis isn't running - breaks tests.
"""
import json
import logging
import os

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


def job_created(job_id: str, customer_id: str, job_type: str, location: dict) -> bool:
    return publish("job.created", {
        "job_id": job_id,
        "customer_id": customer_id,
        "job_type": job_type,
        "location": location,
    })


def job_status_changed(job_id: str, old_status: str, new_status: str, actor_id: str) -> bool:
    return publish("job.status_changed", {
        "job_id": job_id,
        "old_status": old_status,
        "new_status": new_status,
        "actor_id": actor_id,
    })


def job_quoted(job_id: str, quotation_id: str, total_estimate: float) -> bool:
    return publish("job.quoted", {
        "job_id": job_id,
        "quotation_id": quotation_id,
        "total_estimate": float(total_estimate),
    })


def payment_completed(payment_id: str, job_id: str, amount: float) -> bool:
    return publish("payment.completed", {
        "payment_id": payment_id,
        "job_id": job_id,
        "amount": float(amount),
    })


def job_completed(job_id: str, contractor_id: str) -> bool:
    return publish("job.completed", {
        "job_id": job_id,
        "contractor_id": contractor_id,
    })
