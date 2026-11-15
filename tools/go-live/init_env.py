#!/usr/bin/env python3
"""Create .env.prod from .env.prod.example and generate the internal secrets.

    python3 tools/go-live/init_env.py [--domain api.example.in] [--email me@example.in]

Never overwrites an existing .env.prod. Only the three AUTO secrets are
generated (database password, JWT secret, Grafana password); everything that
needs a third party's account (Razorpay, Google, your domain) is left for you.
ALLOWED_ORIGINS is left blank, which means https://<PUBLIC_DOMAIN>.
"""
import argparse
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def set_value(text: str, key: str, value: str) -> str:
    """Replace the first uncommented `KEY=...` line."""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if not pattern.search(text):
        raise SystemExit(f"{key} is missing from the template - cannot continue")
    return pattern.sub(lambda _m: f"{key}={value}", text, count=1)


def build(template: str, domain: str = "", email: str = "") -> str:
    text = template
    # token_urlsafe has no characters that need quoting in a .env file or in a
    # postgres:// URL (the DB password is embedded in a connection string).
    text = set_value(text, "POSTGRES_PASSWORD", secrets.token_urlsafe(24))
    text = set_value(text, "JWT_SECRET", secrets.token_urlsafe(48))
    text = set_value(text, "GRAFANA_ADMIN_PASSWORD", secrets.token_urlsafe(18))
    if domain:
        text = set_value(text, "PUBLIC_DOMAIN", domain)
    if email:
        text = set_value(text, "LETSENCRYPT_EMAIL", email)
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--domain", default="", help="e.g. api.yourdomain.in")
    parser.add_argument("--email", default="", help="Let's Encrypt contact")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root)
    target = root / ".env.prod"
    if target.exists():
        print(f"{target} already exists - leaving it alone.")
        print("Delete it first if you really want a fresh one (that would")
        print("replace the database password and log everyone out).")
        return 1
    text = build((root / ".env.prod.example").read_text(), args.domain, args.email)
    # 0600 from the start: the file will hold the Razorpay secret.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    print(f"Created {target} (permissions 600) with generated secrets.")
    print("Next: open it, fill in the '>>> YOU ENTER <<<' section, then run")
    print("  make prod-check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
