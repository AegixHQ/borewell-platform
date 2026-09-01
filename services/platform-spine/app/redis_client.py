import json
import os

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Redis connection
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def publish_event(channel: str, data: dict):
    """
    Publish an event to the Redis pub/sub mechanism.
    """
    redis_client.publish(channel, json.dumps(data))
