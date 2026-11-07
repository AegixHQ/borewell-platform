"""
Operator-created accounts.

Two roles cannot be self-registered, by design:
  - admin: POST /v1/auth/register never accepts it (models.PUBLIC_ROLES) -
    otherwise anyone on the internet could make themselves one.
  - contractor, once ALLOW_PUBLIC_CONTRACTOR_REGISTRATION=0 - a contractor can
    read every customer's jobs and payments, so after the pilot contractor
    exists, new ones are vetted and created by an operator.

Ways to create one:
  - first admin at service start: set BOOTSTRAP_ADMIN_EMAIL and
    BOOTSTRAP_ADMIN_PASSWORD (app.main's lifespan calls
    bootstrap_admin_from_env), then REMOVE the password from the environment;
  - any role, by hand (prompts for the password, nothing on the command line
    or in shell history):
        docker compose exec -it platform-spine \
            python -m app.bootstrap create-user --role contractor --email owner@example.com

Rules, all deliberate:
  - Create-only. If the email already exists the account is left exactly as
    it is - this never resets a password and never promotes a customer to
    admin or contractor. Promotion is a manual database decision.
"""

import argparse
import getpass
import logging
import os
import sys

from sqlalchemy.orm import Session

from app import models
from app.security import hash_password

logger = logging.getLogger(__name__)
MIN_PASSWORD_LENGTH = 8  # same floor as RegisterRequest.password
MAX_PASSWORD_BYTES = 72  # bcrypt limit, same as RegisterRequest.password


def ensure_user(db: Session, email: str, password: str, role: str) -> bool:
    """Create the account if no user has this email. Returns True if created."""
    if role not in models.ROLES:
        raise ValueError(f"role must be one of {models.ROLES}")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        if existing.role != role:
            logger.warning(
                "bootstrap_user.skipped email=%s exists with role=%s; not changing it",
                email,
                existing.role,
            )
        return False
    db.add(models.User(email=email, password_hash=hash_password(password), role=role))
    db.commit()
    logger.info("bootstrap_user.created email=%s role=%s", email, role)
    return True


def ensure_admin(db: Session, email: str, password: str) -> bool:
    return ensure_user(db, email, password, "admin")


def bootstrap_admin_from_env() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    _with_session(lambda db: ensure_admin(db, email, password))


def _with_session(fn):
    from app.database import SessionLocal  # late import: keeps tests off the prod engine

    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    from app.logging_config import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.bootstrap")
    sub = parser.add_subparsers(dest="command")
    create = sub.add_parser(
        "create-user", help="create an account of any role (prompts for the password)"
    )
    create.add_argument("--role", required=True, choices=models.ROLES)
    create.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    if args.command == "create-user":
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
        created = _with_session(lambda db: ensure_user(db, args.email, password, args.role))
        print(
            "created" if created else "an account with this email already exists - left unchanged"
        )
        return 0 if created else 2
    bootstrap_admin_from_env()  # no subcommand: the original env-driven admin bootstrap
    return 0


if __name__ == "__main__":
    sys.exit(main())
