import os
import sys

# Ensure the app module is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid

import app.models
from app.database import get_db
from app.main import app as fastapi_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use sqlite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = override_get_db

print("Registered tables in app.models.Base:", app.models.Base.metadata.tables.keys())
app.models.Base.metadata.create_all(bind=engine)

client = TestClient(fastapi_app)

def run_tests():
    # Test 1: create job
    customer_id = str(uuid.uuid4())
    res = client.post("/v1/jobs", json={
        "customer_id": customer_id,
        "location": {"lat": 12.9716, "lng": 77.5946}
    })
    assert res.status_code == 201, f"Expected 201, got {res.status_code}. Response: {res.text}"
    job_id = res.json()["job_id"]
    print("Job created:", job_id)
    
    # Test 2: valid transition
    res2 = client.patch(f"/v1/jobs/{job_id}/status", json={"status": "site_location"})
    assert res2.status_code == 200, (
        f"Expected 200, got {res2.status_code}. Response: {res2.text}"
    )
    assert res2.json()["status"] == "site_location"
    print("Job updated to site_location")
    
    # Test 3: invalid transition
    res3 = client.patch(f"/v1/jobs/{job_id}/status", json={"status": "drilling"})
    assert res3.status_code == 400, (
        f"Expected 400, got {res3.status_code}. Response: {res3.text}"
    )
    print("Invalid transition caught successfully")
        
if __name__ == "__main__":
    run_tests()
    print("ALL TESTS PASSED")
