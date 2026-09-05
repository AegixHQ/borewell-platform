import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.database import Base

JOB_TYPES = ("residential", "agricultural", "commercial")
QUOTATION_STATUSES = ("draft", "sent", "approved", "rejected")

# All INR amounts use this (Bug 2 fix: Float loses precision on repeated
# arithmetic - see app/pricing/engine.py's docstring). Feet/percentage
# columns stay Float - not currency, not summed the way money is.
MONEY = Numeric(precision=12, scale=2)


def new_uuid() -> str:
    return str(uuid.uuid4())


class PricingRule(Base):
    """One row per (contractor, job_type) - the contractor's configured
    base rates, resource assumptions, and commercial rules (RFC 0001 FR-K14).
    Upserted, never duplicated - see main.py's upsert_pricing_rule."""

    __tablename__ = "pricing_rules"

    id = Column(String(36), primary_key=True, default=new_uuid)
    contractor_id = Column(String(36), nullable=False, index=True)
    job_type = Column(String, nullable=False)

    base_rate_per_ft = Column(MONEY, nullable=False)
    casing_rate_per_ft = Column(MONEY, nullable=False)
    labour_flat_fee = Column(MONEY, nullable=False)
    transport_flat_fee = Column(MONEY, nullable=False)
    equipment_flat_fee = Column(MONEY, nullable=False)
    installation_flat_fee = Column(MONEY, nullable=False)
    margin_percent = Column(Float, nullable=False)  # a ratio, not currency
    minimum_job_charge = Column(MONEY, nullable=False)

    # MVP estimation inputs - flat assumption, not a real geological estimate
    # (RFC 0001 section 6). depth_overage_rate_per_ft is stored here now even
    # though only payments-data will use it at job completion, because it's
    # part of the contractor's pricing configuration, not a job-time decision.
    assumed_depth_ft = Column(Float, nullable=False)
    depth_confidence_band_ft = Column(Float, nullable=False)
    depth_overage_rate_per_ft = Column(MONEY, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # App-level upsert logic (main.py) already treats this as unique;
        # this makes it true even under a concurrent-write race, which the
        # application logic alone cannot.
        UniqueConstraint("contractor_id", "job_type", name="uq_pricing_rules_contractor_job_type"),
    )


class Quotation(Base):
    """Append-only versioning (FR-QUOTE-05): an edit never mutates an
    existing row, it inserts a new one with version + 1. This makes
    'the customer only ever sees the latest version' a simple MAX(version)
    query, and makes BR-06 (can't silently change an approved price) true
    by construction rather than a rule someone has to remember to check.

    customer_id is populated from platform-spine's real job record at
    generation time (app/jobs/job_client.py), not trusted from the caller -
    this is what closes the IDOR gap (F-01): every read/approve/reject
    checks a customer against this column, not against whatever ID a
    request happened to supply.

    line_items stays a JSON blob with float amounts inside (JSON has no
    native decimal type). Each amount was independently computed via exact
    Decimal arithmetic before being rounded and cast to float for storage
    here, so there's no compounding error within a single quotation.
    subtotal, margin_amount, and total - the values actually compared,
    summed, or checked against a minimum - are real Numeric columns."""

    __tablename__ = "quotations"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    contractor_id = Column(String(36), nullable=False, index=True)
    customer_id = Column(String(36), nullable=False, index=True)
    job_type = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="draft")

    line_items = Column(JSON, nullable=False)
    subtotal = Column(MONEY, nullable=False)
    margin_amount = Column(MONEY, nullable=False)
    total = Column(MONEY, nullable=False)
    minimum_charge_applied = Column(Boolean, nullable=False, default=False)

    estimated_depth_min_ft = Column(Float, nullable=False)
    estimated_depth_max_ft = Column(Float, nullable=False)
    confidence = Column(String, nullable=False, default="low")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # get_latest_quotation_for_job's ORDER BY version DESC without this
        # scans every row for a job_id to find the max.
        Index("ix_quotations_job_id_version", "job_id", "version"),
    )
