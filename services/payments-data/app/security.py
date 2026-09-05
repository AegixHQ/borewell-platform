import os

import jwt

# F-03: no insecure fallback - service refuses to start without this.
# Tests set it via os.environ.setdefault() in conftest.py before importing.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
