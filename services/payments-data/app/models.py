import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

PAYMENT_STATUSES = ("pending", "completed", "failed")
# How the customer settles. "cash" means they pay the contractor in person;
# the payment stays "pending" until a contractor confirms the cash arrived.
PAYMENT_METHODS = ("online", "cash")

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
    # The contractor who quoted the job, copied from the quotation when the
    # payment is opened: it is what lets a contractor see and settle only their
    # own jobs' payments. Null on rows created before this column existed -
    # those are resolved through the quotation service on first use.
    contractor_id = Column(String(36), nullable=True, index=True)
    amount = Column(MONEY, nullable=False)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    status = Column(
        SAEnum(*PAYMENT_STATUSES, name="payment_status"), nullable=False, default="pending"
    )
    # Razorpay integration. Both nullable: a payment starts with neither
    # set (created, no order yet), gets razorpay_order_id once
    # create-order is called, and razorpay_payment_id once Razorpay's
    # webhook reports an actual payment attempt against that order (a
    # customer can create an order and abandon checkout without ever
    # producing a razorpay_payment_id - that's a real, valid state, not
    # a bug).
    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    # "online" (Razorpay) or "cash". Plain string, not a DB enum: adding a
    # method later must not need an ALTER TYPE migration.
    method = Column(String(10), nullable=False, default="online", server_default="online")
    # Who confirmed the cash arrived, and when. Both null until then.
    cash_confirmed_by = Column(String(36), nullable=True)
    cash_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
