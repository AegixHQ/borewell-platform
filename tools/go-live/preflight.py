#!/usr/bin/env python3
# ruff: noqa: E501  (long, human-readable messages are the point of this file)
"""Check .env.prod before deploying. Exit 1 on any ERROR; WARNs are advice.

    python3 tools/go-live/preflight.py [--env .env.prod] [--dns]

Catches the mistakes that otherwise show up as a confusing failure on the
phone: an http:// origin, a half-filled Razorpay trio, a test key you thought
was live, a domain with a scheme in it, a rate-limit setting that is only safe
with the service ports closed.
"""
import argparse
import os
import re
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envfile  # noqa: E402

HOSTNAME = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACEHOLDERS = {"", "CHANGE_ME", "changeme", "dev-only-secret-change-in-production"}
RAZORPAY_KEY = re.compile(r"^rzp_(live|test)_[A-Za-z0-9]{6,}$")
GOOGLE_ID = re.compile(r"^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$")


def check(env: dict, file_mode=None):
    """Returns (errors, warnings, info) as lists of strings."""
    errors, warnings, info = [], [], []
    get = lambda k: env.get(k, "").strip()  # noqa: E731

    def secret(key, minimum):
        value = get(key)
        if value in PLACEHOLDERS:
            errors.append(f"{key} is not set - run `make prod-init` (it generates it).")
        elif len(value) < minimum:
            errors.append(f"{key} is too short ({len(value)} chars, need {minimum}+).")

    secret("POSTGRES_PASSWORD", 16)
    secret("JWT_SECRET", 32)
    secret("GRAFANA_ADMIN_PASSWORD", 12)
    if get("POSTGRES_PASSWORD") and get("POSTGRES_PASSWORD") == get("JWT_SECRET"):
        errors.append("POSTGRES_PASSWORD and JWT_SECRET must be different values.")

    domain = get("PUBLIC_DOMAIN")
    if not domain:
        errors.append("PUBLIC_DOMAIN is empty - enter the hostname the apps will call.")
    elif "://" in domain or "/" in domain or ":" in domain:
        errors.append("PUBLIC_DOMAIN must be a bare hostname: no https://, slash or port.")
    elif domain in ("localhost", "example.com") or not HOSTNAME.match(domain.lower()):
        errors.append(f"PUBLIC_DOMAIN '{domain}' is not a real public hostname "
                      "(Let's Encrypt cannot issue for IP addresses or localhost).")

    email = get("LETSENCRYPT_EMAIL")
    if not email or not EMAIL.match(email):
        errors.append("LETSENCRYPT_EMAIL must be a real email address.")

    origins = [o.strip() for o in get("ALLOWED_ORIGINS").split(",") if o.strip()]
    if not origins and domain:
        origins = [f"https://{domain}"]  # what the compose file falls back to
    for origin in origins:
        if not origin.startswith("https://"):
            errors.append(f"ALLOWED_ORIGINS has '{origin}' - production origins must be https://.")
        if origin.endswith("/"):
            errors.append(f"ALLOWED_ORIGINS entry '{origin}' must not end with a slash.")
        if "localhost" in origin or "127.0.0.1" in origin:
            errors.append(f"ALLOWED_ORIGINS has '{origin}' - localhost does not belong in production.")

    # Razorpay: all three or none.
    rz = {k: get(k) for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")}
    filled = [k for k, v in rz.items() if v and v not in PLACEHOLDERS]
    if not filled:
        warnings.append("Razorpay is blank: the app will run CASH-ONLY (online payment off).")
    elif len(filled) < 3:
        missing = ", ".join(k for k in rz if k not in filled)
        errors.append(f"Razorpay is half-configured (missing {missing}) - fill all three or none.")
    else:
        match = RAZORPAY_KEY.match(rz["RAZORPAY_KEY_ID"])
        if not match:
            errors.append("RAZORPAY_KEY_ID should look like rzp_test_XXXX or rzp_live_XXXX.")
        elif match.group(1) == "test":
            warnings.append("Razorpay is in TEST mode (rzp_test_): no real money moves. "
                            "Switch to rzp_live_ keys after a successful test payment.")
        else:
            info.append("Razorpay is in LIVE mode - real money.")
        if len(rz["RAZORPAY_KEY_SECRET"]) < 16:
            errors.append("RAZORPAY_KEY_SECRET looks too short - copy the whole secret.")
        if len(rz["RAZORPAY_WEBHOOK_SECRET"]) < 8:
            errors.append("RAZORPAY_WEBHOOK_SECRET must be at least 8 characters "
                          "(Razorpay's own minimum for webhook secrets).")
        if rz["RAZORPAY_WEBHOOK_SECRET"] in (rz["RAZORPAY_KEY_SECRET"], rz["RAZORPAY_KEY_ID"]):
            errors.append("RAZORPAY_WEBHOOK_SECRET is a different value from the API keys - "
                          "it is the secret you typed into the Webhooks page.")

    google = [g.strip() for g in get("GOOGLE_CLIENT_IDS").split(",") if g.strip()]
    if not google:
        warnings.append("GOOGLE_CLIENT_IDS is blank: Google sign-in is OFF.")
    for gid in google:
        if not GOOGLE_ID.match(gid):
            errors.append(f"GOOGLE_CLIENT_IDS entry '{gid}' should end in "
                          ".apps.googleusercontent.com (use the *Web application* client ID).")

    admin_email, admin_pw = get("BOOTSTRAP_ADMIN_EMAIL"), get("BOOTSTRAP_ADMIN_PASSWORD")
    if bool(admin_email) != bool(admin_pw):
        errors.append("Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD together, or neither.")
    elif admin_email:
        if not EMAIL.match(admin_email) or admin_email.lower().endswith((".local", ".test")):
            errors.append("BOOTSTRAP_ADMIN_EMAIL must be a real address (the login rejects .local).")
        if len(admin_pw) < 12:
            errors.append("BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters.")
        warnings.append("Admin bootstrap is set: after the first deploy, DELETE "
                        "BOOTSTRAP_ADMIN_PASSWORD from .env.prod and redeploy.")

    bind, trust = get("SERVICE_BIND_ADDR") or "0.0.0.0", get("RATE_LIMIT_TRUST_FORWARDED_FOR") or "0"
    if trust not in ("0", "1"):
        errors.append("RATE_LIMIT_TRUST_FORWARDED_FOR must be 0 or 1.")
    if trust == "1" and bind != "127.0.0.1":
        errors.append("RATE_LIMIT_TRUST_FORWARDED_FOR=1 is only safe with SERVICE_BIND_ADDR=127.0.0.1 "
                      "(otherwise anyone can forge X-Forwarded-For and dodge the login rate limit).")
    if bind != "127.0.0.1":
        warnings.append(f"SERVICE_BIND_ADDR={bind}: ports 8001-8004 are reachable from outside, "
                        "bypassing HTTPS. Use 127.0.0.1 when all clients go through the gateway.")
    if get("ALLOW_PUBLIC_CONTRACTOR_REGISTRATION") not in ("", "0", "1"):
        errors.append("ALLOW_PUBLIC_CONTRACTOR_REGISTRATION must be 0 or 1.")
    if get("ALLOW_PUBLIC_CONTRACTOR_REGISTRATION") == "1":
        warnings.append("Anyone can register as a contractor and read every customer's jobs "
                        "and payments. Keep this at 0 and create contractors with `make prod-contractor`.")
    if get("GRAFANA_BIND_ADDR") not in ("", "127.0.0.1"):
        warnings.append("GRAFANA_BIND_ADDR exposes Grafana beyond this machine.")
    if "acme-staging" in get("LETSENCRYPT_CA_SERVER"):
        warnings.append("LETSENCRYPT_CA_SERVER is the STAGING CA: certificates will not be "
                        "trusted by phones. Remove it for the real run.")

    if file_mode is not None and file_mode & 0o077:
        warnings.append(f".env.prod permissions are {oct(file_mode & 0o777)} - run `chmod 600 .env.prod`.")

    if domain and not errors:
        info.append(f"Razorpay webhook URL to register: https://{domain}/v1/payments/webhook "
                    "(events: payment.captured, payment.failed)")
        info.append(f"App API URL (all four services): https://{domain}")
    return errors, warnings, info


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--env", default=".env.prod")
    parser.add_argument("--dns", action="store_true", help="also check PUBLIC_DOMAIN resolves")
    args = parser.parse_args(argv)

    path = Path(args.env)
    if not path.exists():
        print(f"ERROR: {path} not found - run `make prod-init` first.")
        return 1
    env = envfile.load(path)
    errors, warnings, info = check(env, os.stat(path).st_mode)

    if args.dns and env.get("PUBLIC_DOMAIN") and not errors:
        try:
            ip = socket.gethostbyname(env["PUBLIC_DOMAIN"])
            info.append(f"DNS: {env['PUBLIC_DOMAIN']} -> {ip} (must be THIS server's public IP)")
        except OSError:
            errors.append(f"DNS: {env['PUBLIC_DOMAIN']} does not resolve yet - add the A record "
                          "and wait for it to propagate, or Let's Encrypt will fail.")

    for line in errors:
        print(f"ERROR  {line}")
    for line in warnings:
        print(f"WARN   {line}")
    for line in info:
        print(f"INFO   {line}")
    if errors:
        print(f"\n{len(errors)} error(s) - fix them in {path} and run again.")
        return 1
    print("\nPreflight passed." + (f" ({len(warnings)} warning(s) above)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
