import os

# Must be set before any `from app.*` import below - app.security reads
# JWT_SECRET at module import time and refuses to start without it (F-03).
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-and-local-tests-only")

import uuid

import jwt
import pytest
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"
# Read from the env var set by the bootstrap above, so the token signing
# secret and the service verification secret are always identical.
JWT_SECRET_FOR_TESTS = os.environ["JWT_SECRET"]
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")


def make_token(user_id: str, role: str) -> str:
    stable_uuid = str(uuid.uuid5(_NAMESPACE, user_id))
    return jwt.encode({"sub": stable_uuid, "role": role}, JWT_SECRET_FOR_TESTS, algorithm="HS256")


@pytest.fixture()
def client():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
