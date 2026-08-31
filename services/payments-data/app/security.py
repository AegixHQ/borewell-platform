import os

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-in-production")
JWT_ALGORITHM = "HS256"


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
