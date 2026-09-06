import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Numeric, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

# INR money columns - same MONEY convention as quotation service (Bug 2 fix).
# Decimal stored as Numeric(12,2), serialized as a string on the wire.
MONEY = Numeric(precision=12, scale=2)

ROLES = ("customer", "contractor", "admin", "resource_owner")
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


class JobCompletion(Base):
    """Written once at job completion (FR-TRACK-03/04, BR-04, BR-05).
    Never updated - altering a completion record would destroy the audit
    trail (BR-04: "both are stored, never overwritten").
    """
    __tablename__ = "job_completions"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), nullable=False, unique=True, index=True)
    # Geometry
    actual_depth_ft = Column(Float, nullable=False)
    depth_overage_ft = Column(Float, nullable=False, default=0.0)
    # Financials - MONEY type (Numeric) not Float for the same reason as
    # quotation and payments-data: these values will be compared and
    # displayed as exact INR figures. Float on a money column is Bug 2.
    actual_cost = Column(MONEY, nullable=False)
    quoted_total = Column(MONEY, nullable=False)
    variance = Column(MONEY, nullable=False)
    depth_overage_charge = Column(MONEY, nullable=False, default=0)
    completed_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
