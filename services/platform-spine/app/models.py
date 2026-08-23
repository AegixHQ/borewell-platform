import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

ROLES = ("customer", "contractor", "admin")
JOB_STATUSES = (
    "lead", "site_location", "requirement", "estimation", "price_calculation",
    "quotation", "customer_approval", "booking", "resource_allocation",
    "drilling", "progress", "completion", "payment", "service_history",
)


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(*ROLES, name="user_role"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    customer_id = Column(String(36), nullable=False, index=True)
    contractor_id = Column(String(36), nullable=True, index=True)
    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(SAEnum(*JOB_STATUSES, name="job_status"), nullable=False, default="lead")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
