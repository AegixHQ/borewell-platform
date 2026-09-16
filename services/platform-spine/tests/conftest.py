import os

# Must be set before any `from app.*` import below - app.security reads
# JWT_SECRET at module import time and refuses to start without it (F-03).
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-and-local-tests-only")

import pytest
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def client():
    # StaticPool keeps a single shared connection alive for the lifetime of
    # this in-memory SQLite DB - without it, each new connection from the
    # pool would get its own empty database and data would vanish between
    # requests within the same test.
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
        # Exposed so tests that need a real DB session OUTSIDE the HTTP
        # layer (e.g. calling an event consumer's handler function
        # directly - see test_payment_consumer.py) can open one bound to
        # this SAME in-memory engine, not the production app.database
        # engine (a real Postgres URL by default) - without this, such a
        # test would silently read/write an empty, unrelated database.
        c.test_session_local = testing_session_local
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
