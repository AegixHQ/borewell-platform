"""
Small in-process sliding-window rate limiter for the auth endpoints.

Why hand-rolled and not slowapi: it is ~60 lines, adds no dependency (so no
Docker image or lockfile churn), raises errors in this service's shared
error format, and is trivially testable. Why in-process and not Redis: each
service runs as ONE container in the pilot topology (Architecture section
10), so a per-process counter is the real counter. If platform-spine is ever
scaled to several replicas, each replica counts separately - the effective
limit becomes limit x replicas - and this should move to Redis (already in
the stack) at that point.

Configuration (all env, all optional):
  RATE_LIMIT_ENABLED=0          turn the limiter off (the test suite does)
  RATE_LIMIT_LOGIN=10/minute    per client IP, every login attempt counts
  RATE_LIMIT_REGISTER=10/hour   per client IP
  RATE_LIMIT_TRUST_FORWARDED_FOR=1
        Key on the LAST X-Forwarded-For entry (the one the nearest proxy
        appended) instead of the TCP peer. Required behind the Traefik
        gateway - otherwise every user shares the gateway's IP and one
        shared limit - and ONLY safe if the service port cannot be reached
        directly from outside (a direct caller can forge the header). See
        docs/deployment/PRODUCTION.md.
"""

import math
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
_MAX_KEYS = 50_000  # memory ceiling: an attacker rotating IPs must not grow this forever


def parse_limit(spec: str) -> tuple[int, int]:
    """'10/minute' -> (10, 60). Raises ValueError on anything else, at the
    moment of use - a typo in an env var should fail loudly, not silently
    disable the limit."""
    count, _, unit = spec.strip().partition("/")
    unit = unit.strip().rstrip("s")
    if not count.strip().isdigit() or int(count) < 1 or unit not in _UNITS:
        raise ValueError(f"invalid rate limit {spec!r}; expected e.g. '10/minute'")
    return int(count), _UNITS[unit]


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def check(self, key: str, limit: int, window_s: int) -> int | None:
        """Record one hit. Returns None if allowed, else seconds until the
        oldest hit in the window expires (the Retry-After value)."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_sweep > 300 or len(self._hits) > _MAX_KEYS:
                self._sweep(now, window_s)
            hits = self._hits[key]
            while hits and now - hits[0] >= window_s:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, math.ceil(window_s - (now - hits[0])))
            hits.append(now)
            return None

    def _sweep(self, now: float, window_s: int) -> None:
        # Keys are scoped per endpoint but windows differ; the longest
        # configured window is a day, so anything idle longer is dead.
        horizon = max(window_s, _UNITS["day"])
        for k in [k for k, h in self._hits.items() if not h or now - h[-1] >= horizon]:
            del self._hits[k]
        if len(self._hits) > _MAX_KEYS:
            self._hits.clear()  # last resort - fail open on memory, never grow unbounded
        self._last_sweep = now

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    if os.getenv("RATE_LIMIT_TRUST_FORWARDED_FOR") == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, env_var: str, default: str):
    """FastAPI dependency factory. Runs before the request body is
    validated, so a flood of malformed requests is limited too."""

    def dependency(request: Request) -> None:
        if os.getenv("RATE_LIMIT_ENABLED", "1") == "0":
            return
        limit, window = parse_limit(os.getenv(env_var, default))
        retry_after = limiter.check(f"{scope}:{client_ip(request)}", limit, window)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMITED",
                    "message": f"Too many attempts. Try again in {retry_after} seconds.",
                },
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


login_rate_limit = rate_limit("login", "RATE_LIMIT_LOGIN", "10/minute")
register_rate_limit = rate_limit("register", "RATE_LIMIT_REGISTER", "10/hour")
