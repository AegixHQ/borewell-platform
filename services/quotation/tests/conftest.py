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
JWT_SECRET_FOR_TESTS = "dev-only-secret-change-in-production"
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")


def make_token(user_id: str, role: str) -> str:
    """Real tokens carry a real UUID as `sub` (platform-spine issues user.id,
    which is a UUID - see services/platform-spine/app/models.py). Test
    labels like "contractor-1" are deterministically mapped to a stable UUID
    so tests stay readable without weakening the response schema's UUID
    typing to accommodate a test-only shortcut."""
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
