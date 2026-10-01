"""
Admin bootstrap.

POST /v1/auth/register deliberately cannot create an admin (models.PUBLIC_ROLES) -
otherwise anyone on the internet could make themselves one. The first admin
is created out-of-band instead:

  - at service start, if BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD
    are both set (app.main's lifespan calls bootstrap_admin_from_env), or
  - by hand:  docker compose exec platform-spine python -m app.bootstrap

Rules, all deliberate:
  - Create-only. If the email already exists the account is left exactly as
    it is - this never resets a password and never promotes a customer or
    contractor to admin. Promotion is a manual database decision.
  - After the first successful start, REMOVE the password from the
    environment; it has no further purpose.
"""

import logging
import os

from sqlalchemy.orm import Session

from app import models
from app.security import hash_password

logger = logging.getLogger(__name__)
MIN_PASSWORD_LENGTH = 8  # same floor as RegisterRequest.password


def ensure_admin(db: Session, email: str, password: str) -> bool:
    """Create the admin if no user has this email. Returns True if created."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"admin password must be at least {MIN_PASSWORD_LENGTH} characters")
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        if existing.role != "admin":
            logger.warning(
                "bootstrap_admin.skipped email=%s exists with role=%s; not promoting",
                email,
                existing.role,
            )
        return False
    db.add(models.User(email=email, password_hash=hash_password(password), role="admin"))
    db.commit()
    logger.info("bootstrap_admin.created email=%s", email)
    return True


def bootstrap_admin_from_env() -> None:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    from app.database import SessionLocal  # late import: keeps tests off the prod engine

    db = SessionLocal()
    try:
        ensure_admin(db, email, password)
    finally:
        db.close()


if __name__ == "__main__":
    from app.logging_config import configure_logging

    configure_logging()
    bootstrap_admin_from_env()
