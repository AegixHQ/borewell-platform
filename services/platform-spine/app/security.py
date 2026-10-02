import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

# F-03: no insecure fallback - service refuses to start without this.
# Tests set it via os.environ.setdefault() in conftest.py before importing.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


BCRYPT_MAX_BYTES = 72  # bcrypt ignores (4.x) or rejects (5.x) anything beyond this


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        # No stored hash can match (registration refuses such passwords), and
        # bcrypt 5.x raises ValueError on them - which used to surface as an
        # unauthenticated 500 on /v1/auth/login.
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


# Checked against when a login names an email that has no account, so that
# path costs the same bcrypt work as a real one (see main.login).
DUMMY_PASSWORD_HASH = hash_password("timing-equalisation-placeholder")


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    # Raises jwt.PyJWTError (caught by the caller) on invalid/expired token.
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        # A validly-signed token missing any of these is malformed: reject it here
        # rather than letting a KeyError surface later as a 500, and never
        # accept a token that cannot expire.
        options={"require": ["exp", "sub", "role"]},
    )
