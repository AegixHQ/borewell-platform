"""
Event consumer: when a job is completed (job.completed, published by
platform-spine once the actual depth and cost are saved) the rigs booked for
that job are freed, so the owner's fleet shows them as available again and
they can be booked by someone else.

Same shape as platform-spine's payment_consumer, kept just as small: one
background thread, started from main.py's lifespan, that logs and carries on
when Redis is down or one message is bad. Redis pub/sub does not replay, so a
dropped event is not fatal - POST /v1/bookings/{id}/release (contractor or
owner) is the manual way to free a rig, and it is always available.
"""
import json
import logging
import os
import threading
import time

from app import models
from app.database import SessionLocal

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_subscriber_thread = None


def handle_job_completed(payload: dict, db=None) -> int:
    """Free every accepted booking made for payload['job_id']. Returns how many
    were released. `db` is injectable for tests; production opens its own."""
    job_id = payload.get("job_id") if isinstance(payload, dict) else None
    if not job_id:
        logger.warning("job.completed without a job_id, ignoring: %s", payload)
        return 0

    from app.main import release_booking  # late: app.main imports this module

    def work(session) -> int:
        bookings = (
            session.query(models.BookingRequest)
            .filter(
                models.BookingRequest.job_id == str(job_id),
                models.BookingRequest.status == "accepted",
            )
            .all()
        )
        for booking in bookings:
            release_booking(session, booking)
        session.commit()
        return len(bookings)

    if db is not None:
        released = work(db)
    else:
        session = SessionLocal()
        try:
            released = work(session)
        finally:
            session.close()
    if released:
        logger.info("job_id=%s completed: released %s booking(s)", job_id, released)
    return released


def _listen_loop():
    import redis

    while True:
        try:
            pubsub = redis.Redis.from_url(REDIS_URL, decode_responses=True).pubsub()
            pubsub.subscribe("job.completed")
            logger.info("subscribed to job.completed")
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("job.completed: could not parse message, dropping: %s", exc)
                    continue
                try:
                    handle_job_completed(payload)
                except Exception:
                    logger.exception("error handling job.completed event: %s", payload)
        except Exception:
            logger.exception("job.completed subscriber loop crashed, retrying")
            time.sleep(5)


def start():
    """Idempotent: calling it twice does not start a second thread."""
    global _subscriber_thread
    if _subscriber_thread is not None:
        return
    _subscriber_thread = threading.Thread(target=_listen_loop, daemon=True)
    _subscriber_thread.start()
