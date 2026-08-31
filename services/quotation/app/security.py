import os

import jwt

# Verification-only - this service never issues tokens, only platform-spine
# does (RFC 0001 section 5). Must share the same JWT_SECRET value.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-in-production")
JWT_ALGORITHM = "HS256"


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
