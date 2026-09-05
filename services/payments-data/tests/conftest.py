import os

# Must be set before any `from app.*` import below - app.security reads
# JWT_SECRET at module import time and refuses to start without it (F-03).
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-and-local-tests-only")

import uuid

import jwt
import pytest
from app.database import Base, get_db
from app.main import app, get_quotation_fetcher
from app.payments.quotation_client import QuotationAccessDenied, QuotationNotFound
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"
JWT_SECRET_FOR_TESTS = os.environ["JWT_SECRET"]
_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")
# Fixed, not random - so a payment payload's job_id can be made to match
# (or deliberately NOT match) what the fake quotation fetcher reports.
DEFAULT_JOB_ID = str(uuid.uuid4())


def make_token(user_id: str, role: str) -> str:
    stable_uuid = str(uuid.uuid5(_NAMESPACE, user_id))
    return jwt.encode({"sub": stable_uuid, "role": role}, JWT_SECRET_FOR_TESTS, algorithm="HS256")


def fake_quotation_fetcher(status="approved", total_estimate=95450.0, job_id=None):
    """Stand-in for the real quotation_client.fetch_quotation call, so
    tests exercise the amount/approval/ownership-checking logic in main.py
    without needing a live quotation service or mocking httpx internals."""
    resolved_job_id = job_id or DEFAULT_JOB_ID

    def _fetch(quotation_id: str, auth_header: str) -> dict:
        return {
            "quotation_id": quotation_id,
            "job_id": resolved_job_id,
            "status": status,
            "total_estimate": total_estimate,
        }

    return _fetch


def not_found_fetcher():
    def _fetch(quotation_id, auth_header):
        raise QuotationNotFound("quotation not found")

    return _fetch


def access_denied_fetcher():
    def _fetch(quotation_id, auth_header):
        raise QuotationAccessDenied("caller does not own this quotation")

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
    app.dependency_overrides[get_quotation_fetcher] = lambda: fake_quotation_fetcher()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client_factory():
    """For tests that need control over what the quotation service
    'returns' - a different status/total/job_id, or a raised error."""
    engines = []

    def _make(status="approved", total_estimate=95450.0, job_id=None, fetcher=None):
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
        app.dependency_overrides[get_quotation_fetcher] = fetcher or (
            lambda: fake_quotation_fetcher(
                status=status, total_estimate=total_estimate, job_id=job_id
            )
        )
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
    for engine in engines:
        Base.metadata.drop_all(bind=engine)
