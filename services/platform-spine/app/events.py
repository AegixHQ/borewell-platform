"""
Redis pub/sub event publishers - platform-spine only publishes the events
that originate from its own job state machine (RFC 0001 section 8).

Per ADR-0003 (docs/adr/0003-events-package-location-and-docker-wiring.md):
this used to live at packages/events/__init__.py, shared across services.
Moved to a per-service copy because packages/ is documented in
STRUCTURE.md as contracts-only, and because the shared location was never
actually reachable from inside this service's Docker build context
(Dockerfile only COPYs this service's own app/, not the repo root).

Design decisions (unchanged from the original shared module):
- Lazy connection: Redis client created on first publish, not at import
  time, so the module can be imported in tests without a live Redis.
- Fire-and-forget: publish() never raises. If Redis is unreachable the
  event is logged and dropped. Authoritative state lives in Postgres - a
  dropped event means a downstream service didn't react, not data loss.
  Acceptable for MVP; real delivery guarantees need a persistent broker
  (see RFC 0001 section 12 for when that upgrade gets justified).
- No module-level connection: a module-level `redis.Redis.from_url(...)`
  crashes the service at import time if Redis isn't running - breaks tests.

Payload shapes match packages/contracts/events/*.schema.json - that's the
real contract between services now (see ADR-0003), not this file's
location.
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


def job_created(job_id: str, customer_id: str, location: dict, created_at) -> bool:
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return publish("job.created", {
        "job_id": job_id,
        "customer_id": customer_id,
        "location": location,
        "created_at": str(created_at),
    })


# job.completed is intentionally NOT implemented here yet. Its schema
# (packages/contracts/events/job.completed.schema.json) requires
# actual_depth_ft, actual_cost, and completed_at - the FR-TRACK-03 data
# that gets logged when a contractor marks a job's actual results. That
# capture endpoint doesn't exist in this service yet (see main.py's
# generic PATCH /v1/jobs/{job_id}/status - it advances status but has
# nowhere to receive actual_depth_ft/actual_cost). Firing this event from
# the generic status-transition endpoint would mean inventing values for
# required fields the event doesn't actually have yet, which is worse than
# not firing it. Wire this up alongside whichever endpoint ends up
# implementing FR-TRACK-03, not before.
#
# job.status_changed was in the original packages/events/__init__.py this
# file replaced (see ADR-0003) but has no corresponding schema file under
# packages/contracts/events/, and isn't one of the four events the
# Development Plan's Milestone 2 row actually lists (job.created,
# job.quoted, job.completed, payment.completed). Deliberately dropped
# rather than wired - Development Plan section 3's own rule: an
# undocumented event is scope creep, not a free addition, the same as an
# undocumented endpoint would be.


def job_completed(
    job_id: str,
    actual_depth_ft: float,
    actual_cost,
    completed_at,
) -> bool:
    """Emit job.completed once actual depth/cost are logged (FR-TRACK-03).
    Matches packages/contracts/events/job.completed.schema.json exactly:
    required fields are job_id, actual_depth_ft, actual_cost, completed_at.
    actual_cost serialized as str(Decimal) - same precision discipline as
    job.quoted and payment.completed events (see those publishers).
    """
    if hasattr(completed_at, "isoformat"):
        completed_at = completed_at.isoformat()
    return publish("job.completed", {
        "job_id": job_id,
        "actual_depth_ft": actual_depth_ft,
        "actual_cost": str(actual_cost),
        "completed_at": str(completed_at),
    })
