#!/usr/bin/env python3
# ruff: noqa: E501  (long, human-readable messages are the point of this file)
"""Post-deploy smoke test against the PUBLIC address, the way the phone sees it.

    python3 tools/go-live/smoke.py --env .env.prod
    python3 tools/go-live/smoke.py --domain api.yourdomain.in [--expect-razorpay] [--expect-google]
    python3 tools/go-live/smoke.py --base http://localhost:8080   # no TLS checks

Needs no login and creates nothing. Exit 1 if anything required is wrong.
"""
import argparse
import http.client
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# Every path prefix the gateway is supposed to route, one cheap GET each. A
# 401/403 is the *right* answer (routed, auth enforced); 404 means the gateway
# is not routing it; 5xx means the service behind it is down.
ROUTED = [
    ("platform-spine", "GET", "/v1/jobs"),
    ("quotation", "GET", "/v1/pricing-rules"),
    ("resource-network", "GET", "/v1/resources"),
    ("payments-data", "GET", "/v1/payments"),
]
OK_STATUSES = {200, 401, 403, 405, 422}


class Result:
    def __init__(self):
        self.failures, self.notes = 0, 0

    def ok(self, msg):
        print(f"  ok    {msg}")

    def fail(self, msg):
        self.failures += 1
        print(f"  FAIL  {msg}")

    def note(self, msg):
        self.notes += 1
        print(f"  note  {msg}")


def call(base, method, path, body=None, timeout=15):
    """Returns (status, headers, text). Connection problems raise OSError."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read().decode("utf-8", "replace")


def run(base, expect_razorpay=False, expect_google=False, https=True):
    res = Result()
    print(f"Smoke test: {base}")

    for service, method, path in ROUTED:
        try:
            status, _, _ = call(base, method, path)
        except OSError as exc:
            res.fail(f"{service}: {path} unreachable ({exc})")
            continue
        if status in OK_STATUSES:
            res.ok(f"{service}: {method} {path} -> {status}")
        elif status == 404:
            res.fail(f"{service}: {path} -> 404, the gateway is not routing it")
        else:
            res.fail(f"{service}: {path} -> {status}, the service behind it is unhealthy")

    # Bad login should be rejected by platform-spine (proves it and its DB are up).
    try:
        status, _, _ = call(base, "POST", "/v1/auth/login",
                            {"email": "smoke-test@invalid.example", "password": "not-a-real-password"})
        if status in (401, 422):
            res.ok(f"login endpoint rejects bad credentials -> {status}")
        else:
            res.fail(f"POST /v1/auth/login with bad credentials -> {status} (expected 401)")
    except OSError as exc:
        res.fail(f"login endpoint unreachable ({exc})")

    # Google: 503 = switched off, 401 = on and verifying, 502 = on but cannot reach Google.
    try:
        # The server validates the body (id_token >= 20 chars) once Google is ON, so the
        # dummy must be long enough to reach the token check and get a 401, not a 422.
        status, _, _ = call(base, "POST", "/v1/auth/google",
                            {"id_token": "smoke-test-not-a-real-google-token"})
        if status == 401:
            res.ok("Google sign-in: ON (rejects a bad token)")
            if not expect_google:
                res.note("Google sign-in is on")
        elif status == 503:
            (res.fail if expect_google else res.note)("Google sign-in is OFF (GOOGLE_CLIENT_IDS blank)")
        elif status == 502:
            res.fail("Google sign-in is on but the server cannot fetch Google's signing keys "
                     "(outbound internet from the container?)")
        else:
            res.fail(f"POST /v1/auth/google -> {status} (expected 401 on, 503 off)")
    except OSError as exc:
        res.fail(f"Google endpoint unreachable ({exc})")

    # Razorpay: webhook with no signature. 502 = secret not configured, 400 = configured.
    try:
        status, _, _ = call(base, "POST", "/v1/payments/webhook", {"event": "smoke.test"})
        if status == 400:
            res.ok("Razorpay webhook: secret configured, unsigned request rejected")
        elif status == 502:
            (res.fail if expect_razorpay else res.note)(
                "Razorpay is NOT configured (cash-only): webhook secret missing")
        else:
            res.fail(f"POST /v1/payments/webhook (unsigned) -> {status} (expected 400)")
    except OSError as exc:
        res.fail(f"webhook endpoint unreachable ({exc})")

    # Things that must not be public.
    for path in ("/metrics", "/docs", "/openapi.json"):
        try:
            status, _, _ = call(base, "GET", path)
            (res.ok if status == 404 else res.fail)(
                f"{path} is {'not exposed' if status == 404 else f'EXPOSED (-> {status})'}")
        except OSError as exc:
            res.fail(f"{path} check failed ({exc})")

    if https:
        host = urlparse(base).hostname
        try:  # the default context verifies the certificate chain and hostname
            with socket.create_connection((host, 443), timeout=10) as sock:
                with ssl.create_default_context().wrap_socket(sock, server_hostname=host) as tls:
                    tls.getpeercert()
            res.ok("TLS certificate is valid and trusted")
        except (OSError, ssl.SSLError) as exc:
            res.fail(f"TLS certificate problem: {exc}")
        try:
            _, headers, _ = call(base, "GET", "/v1/jobs")
            if headers.get("Strict-Transport-Security"):
                res.ok("HSTS header present")
            else:
                res.fail("no Strict-Transport-Security header (is the TLS overlay running?)")
        except OSError:
            pass
        try:
            conn = http.client.HTTPConnection(host, 80, timeout=10)
            conn.request("GET", "/v1/jobs")
            resp = conn.getresponse()
            location = resp.getheader("Location", "")
            if resp.status in (301, 302, 307, 308) and location.startswith("https://"):
                res.ok("port 80 redirects to https")
            else:
                res.fail(f"port 80 does not redirect to https (status {resp.status})")
            conn.close()
        except OSError as exc:
            res.fail(f"port 80 unreachable ({exc})")
        for port in (8001, 8002, 8003, 8004):
            try:
                socket.create_connection((host, port), timeout=3).close()
                res.fail(f"port {port} is open to the internet - set SERVICE_BIND_ADDR=127.0.0.1 "
                         "and close it in the firewall")
            except OSError:
                res.ok(f"port {port} is closed from outside")

    print()
    if res.failures:
        print(f"{res.failures} check(s) FAILED.")
        return 1
    print("All checks passed." + (f" ({res.notes} note(s))" if res.notes else ""))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--env", help="read the domain and Razorpay/Google expectations from .env.prod")
    parser.add_argument("--domain", help="public hostname (https is assumed)")
    parser.add_argument("--base", help="explicit base URL; an http:// base skips the TLS checks")
    parser.add_argument("--expect-razorpay", action="store_true")
    parser.add_argument("--expect-google", action="store_true")
    args = parser.parse_args(argv)
    if args.env:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import envfile
        env = envfile.load(args.env)
        args.domain = args.domain or env.get("PUBLIC_DOMAIN")
        args.expect_razorpay = args.expect_razorpay or bool(env.get("RAZORPAY_WEBHOOK_SECRET"))
        args.expect_google = args.expect_google or bool(env.get("GOOGLE_CLIENT_IDS"))
    if not args.domain and not args.base:
        parser.error("give --env, --domain or --base")
    base = (args.base or f"https://{args.domain}").rstrip("/")
    return run(base, args.expect_razorpay, args.expect_google, https=base.startswith("https://"))


if __name__ == "__main__":
    sys.exit(main())
