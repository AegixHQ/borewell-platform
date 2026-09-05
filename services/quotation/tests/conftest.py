import os

# Must be set before any `from app.*` import below - app.security reads
# JWT_SECRET at module import time and refuses to start without it (F-03).
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-and-local-tests-only")

import uuid

import jwt
import pytest
from app.database import Base, get_db
from app.main import app, get_job_fetcher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"
JWT_SECRET_FOR_TESTS = os.environ["JWT_SECRET"]
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")


def make_token(user_id: str, role: str) -> str:
    """Real tokens carry a real UUID as `sub` (platform-spine issues user.id,
    which is a UUID). Test labels like "contractor-1" are deterministically
    mapped to a stable UUID so tests stay readable without weakening the
    response schema's UUID typing."""
    stable_uuid = str(uuid.uuid5(_NAMESPACE, user_id))
    return jwt.encode({"sub": stable_uuid, "role": role}, JWT_SECRET_FOR_TESTS, algorithm="HS256")


def user_uuid(label: str) -> str:
    """Same stable-UUID mapping make_token uses internally, exposed so
    tests can assert a fake job's customer_id against a real token's
    identity without re-deriving it by hand."""
    return str(uuid.uuid5(_NAMESPACE, label))


DEFAULT_CUSTOMER_LABEL = "default-test-customer"


def fake_job_fetcher(customer_id=None):
    """Stand-in for the real app.jobs.job_client.fetch_job call (F-01 fix) -
    lets tests control which customer 'owns' the job a quotation gets
    generated for, without a live platform-spine or httpx mocking."""
    resolved_customer_id = customer_id or user_uuid(DEFAULT_CUSTOMER_LABEL)

    def _fetch(job_id: str, auth_header: str) -> dict:
        return {"job_id": job_id, "customer_id": resolved_customer_id, "status": "lead"}

    return _fetch


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
    app.dependency_overrides[get_job_fetcher] = lambda: fake_job_fetcher()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client_factory():
    """For tests that need to control which customer 'owns' the job, or
    need the job fetch to fail (not-found / service-unavailable)."""
    engines = []

    def _make(customer_id=None, job_fetcher=None):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        engines.append(engine)
        testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        def override_get_db():
            db = testing_session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_job_fetcher] = (
            job_fetcher if job_fetcher is not None else (lambda: fake_job_fetcher(customer_id))
        )
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
    for engine in engines:
        Base.metadata.drop_all(bind=engine)
