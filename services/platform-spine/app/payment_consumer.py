"""
Real event CONSUMER - platform-spine subscribes to payment.completed,
records a receipt for the job, and advances it from "completion" to
"payment" once its completion record is also logged (RFC 0001 section 8's
state order; BR-03: "A job cannot enter payment-complete status without a
completed payment record" - this IS that enforcement, not just a
convenience). The advance also runs when the completion record is logged,
because the payment usually arrives first.

This is the first real subscriber anywhere in this codebase. Every
service's app/events.py (this one included) has only ever published,
fire-and-forget, with nothing on the consuming side - confirmed
repeatedly across several sessions via `grep -rn "subscribe"
services/*/app/` returning nothing, every time, until this file.

Design, deliberately proportionate to actually being used by one
consumer, not a general event-bus framework:
- A single background thread (not asyncio, not a separate worker
  process/service) started on FastAPI startup, running
  redis.pubsub().listen() in a blocking loop. One event type, one
  reaction - a full task queue or worker framework would be solving a
  scale problem that doesn't exist yet, same reasoning Architecture doc
  section 12 already applies elsewhere in this platform.
- Fails soft, matching the publish side's own "fire-and-forget" honesty:
  if Redis is unreachable at startup, the thread logs and the service
  still starts and serves HTTP normally - a broken event subscription
  must never take down the whole API. The manual admin-override path
  (PATCH /v1/jobs/{id}/status, already existing) remains available
  regardless, so this is a convenience layer on top of a working
  manual path, not a new single point of failure.
- A malformed/unexpected payload logs and continues the loop - one bad
  message must never kill the subscriber thread.
"""
import json
import logging
import os
import threading

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Job, JobCompletion, PaymentReceipt

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Module-level so tests can call this directly without starting a real
# background thread/Redis connection - same "no module-level Redis
# client" discipline as events.py, applied to the consumer side too.
_subscriber_thread = None


def handle_payment_completed(payload: dict, db=None) -> None:
    """The actual reaction - factored out from the Redis-listening loop
    so it's directly unit-testable (see tests/test_payment_consumer.py)
    without needing a live Redis connection for every test case.

    db: pass an explicit session in tests; production code (start()
    below) leaves this None and opens/closes its own session per event,
    same lifecycle as a normal request's get_db() dependency.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        job_id = payload.get("job_id")
        if not job_id:
            logger.warning("payment.completed event missing job_id, dropping: %s", payload)
            return

        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            # A payment.completed event for a job this service has no
            # record of - shouldn't happen in practice (payments-data's
            # own job_id came from a real job originally), but logging
            # and moving on is correct either way: there's nothing to
            # advance, and killing the subscriber over a lookup miss
            # would be a worse failure than skipping one event.
            logger.warning("payment.completed for unknown job_id=%s, dropping", job_id)
            return

        # The customer normally pays long before the job reaches
        # "completion", so this event usually can't be acted on yet. Record
        # it first - Redis pub/sub never replays - and let
        # advance_to_payment_if_ready() decide whether the job can move now
        # or when its completion record is logged later. Redelivery is
        # harmless: one receipt row per job.
        if not db.query(PaymentReceipt.id).filter(PaymentReceipt.job_id == job.id).first():
            db.add(PaymentReceipt(job_id=job.id))
            try:
                db.commit()
            except IntegrityError:
                # A concurrent redelivery inserted the same receipt first.
                db.rollback()

        if advance_to_payment_if_ready(db, job):
            logger.info("job_id=%s advanced to 'payment' via payment.completed event", job_id)
        else:
            logger.info(
                "payment.completed recorded for job_id=%s; job stays at '%s' until it is ready",
                job_id,
                job.status,
            )
    finally:
        if owns_session:
            db.close()


def advance_to_payment_if_ready(db, job) -> bool:
    """Move a job from "completion" to "payment" iff both are on record:
    its completion record (actual depth and cost) AND a payment.completed
    receipt (BR-03). Called from both sides - when the payment event arrives
    and when the completion record is logged - so whichever comes last does
    the advance. Returns True if the job was advanced. Safe to call repeatedly:
    anything other than exactly "completion" is left alone (RFC 0001 section 8).
    """
    if job.status != "completion":
        return False
    has_completion = db.query(JobCompletion.id).filter(JobCompletion.job_id == job.id).first()
    has_receipt = db.query(PaymentReceipt.id).filter(PaymentReceipt.job_id == job.id).first()
    if not (has_completion and has_receipt):
        return False
    job.status = "payment"
    db.commit()
    return True


def _listen_loop():
    import redis

    while True:
        try:
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = client.pubsub()
            pubsub.subscribe("payment.completed")
            logger.info("subscribed to payment.completed")
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("payment.completed: could not parse message, dropping: %s", exc)
                    continue
                try:
                    handle_payment_completed(payload)
                except Exception:
                    # A DB error or anything else unexpected reacting to
                    # ONE event must not kill the whole subscriber thread -
                    # log it and keep listening for the next message.
                    logger.exception("error handling payment.completed event: %s", payload)
        except Exception:
            # Connection-level failure (Redis down, network blip) - log
            # and retry rather than let the background thread die
            # silently and leave the service running with no subscriber
            # and no visible error.
            logger.exception("payment.completed subscriber loop crashed, retrying")
            import time

            time.sleep(5)


def start():
    """Called once from main.py's startup event. Idempotent - calling
    twice (e.g. in a test) does not start a second thread."""
    global _subscriber_thread
    if _subscriber_thread is not None:
        return
    _subscriber_thread = threading.Thread(target=_listen_loop, daemon=True)
    _subscriber_thread.start()
