import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

PAYMENT_STATUSES = ("pending", "completed", "failed")

# Same Bug 2 fix as quotation service's MONEY type (app/models.py there):
# Float loses precision on repeated arithmetic and, worse, on the exact
# equality check in main.py against the quotation's total_estimate (SRS
# section 6: "reject mismatches" - not "reject if the difference exceeds
# some epsilon"). This column was the one place that fix hadn't landed yet.
MONEY = Numeric(precision=12, scale=2)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Payment(Base):
    """idempotency_key has a real unique constraint - FR-PAY-03 is enforced
    by the database, not just application logic, so a race between two
    identical concurrent requests still can't produce two payment rows."""

    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    quotation_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    amount = Column(MONEY, nullable=False)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    status = Column(
        SAEnum(*PAYMENT_STATUSES, name="payment_status"), nullable=False, default="pending"
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
