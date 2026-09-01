import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid

import app.models
from app.database import get_db
from app.main import app as fastapi_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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

app.models.Base.metadata.create_all(bind=engine)

client = TestClient(fastapi_app)

def run_tests():
    # Test 1: Create resource
    res = client.post("/v1/resources", json={
        "type": "rig",
        "status": "available"
    })
    assert res.status_code == 201, res.text
    r = res.json()
    assert r["type"] == "rig"
    assert "resource_id" in r
    
    # Test 2: List resources
    res2 = client.get("/v1/resources?status=available")
    assert res2.status_code == 200, res2.text
    resource_list = res2.json()
    assert len(resource_list) == 1
    assert resource_list[0]["type"] == "rig"
    
    # Test 3: Match resources
    job_id = str(uuid.uuid4())
    res3 = client.post("/v1/resources/match", json={
        "job_id": job_id,
        "requirements": ["rig"]
    })
    assert res3.status_code == 200, res3.text
    m = res3.json()
    assert len(m) == 1
    assert m[0]["provider"] == "Dummy Provider"

if __name__ == "__main__":
    run_tests()
    print("ALL TESTS PASSED")
