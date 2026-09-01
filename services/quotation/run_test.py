import os
import sys

# Ensure the app module is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from unittest.mock import patch

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

app.models.Base.metadata.create_all(bind=engine)

client = TestClient(fastapi_app)

def run_tests():
    with patch("app.redis_client.publish_event") as _mock_publish:
        # Test 1: Get default pricing rules
        res = client.get("/v1/pricing-rules")
        assert res.status_code == 200, res.text
        rules = res.json()
        assert rules["drilling_cost_per_ft"] == 12.0
        print("Default pricing rules fetched successfully")
        
        # Test 2: Update pricing rules
        res2 = client.put("/v1/pricing-rules", json={
            "drilling_cost_per_ft": 15.0,
            "casing_pipe_cost_per_ft": 10.0,
            "transport_base_fee": 60.0
        })
        assert res2.status_code == 200, res2.text
        assert res2.json()["drilling_cost_per_ft"] == 15.0
        print("Pricing rules updated successfully")
        
        # Test 3: Generate quotation
        job_id = str(uuid.uuid4())
        res3 = client.post("/v1/quotations", json={
            "job_id": job_id,
            "location": {"lat": 12.9716, "lng": 77.5946},
            "job_type": "residential"
        })
        assert res3.status_code == 200, res3.text
        quote = res3.json()
        assert "quotation_id" in quote
        
        avg_ft = 200.0 # 100-300
        expected_total = (avg_ft * 15.0) + (avg_ft * 10.0) + 60.0
        assert quote["total_estimate"] == expected_total
        print("Quotation generated successfully with total estimate", quote["total_estimate"])
        
        # Redis event assertion placeholder
        print("Test complete")
        
if __name__ == "__main__":
    run_tests()
    print("ALL TESTS PASSED")
