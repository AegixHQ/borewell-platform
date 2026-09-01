import json
import logging
import os

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

logger = logging.getLogger(__name__)

def get_redis_client():
    try:
        return redis.Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to connect to redis: {e}")
        return None

def publish_event(event_type: str, payload: dict):
    r = get_redis_client()
    if r:
        try:
            r.publish(event_type, json.dumps(payload))
            logger.info(f"Published event {event_type} to redis")
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
