import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String

from app.database import Base

JOB_TYPES = ("residential", "agricultural", "commercial")
QUOTATION_STATUSES = ("draft", "sent", "approved", "rejected")


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

    base_rate_per_ft = Column(Float, nullable=False)
    casing_rate_per_ft = Column(Float, nullable=False)
    labour_flat_fee = Column(Float, nullable=False)
    transport_flat_fee = Column(Float, nullable=False)
    equipment_flat_fee = Column(Float, nullable=False)
    installation_flat_fee = Column(Float, nullable=False)
    margin_percent = Column(Float, nullable=False)
    minimum_job_charge = Column(Float, nullable=False)

    # MVP estimation inputs - flat assumption, not a real geological estimate
    # (RFC 0001 section 6). depth_overage_rate_per_ft is stored here now even
    # though only payments-data will use it at job completion, because it's
    # part of the contractor's pricing configuration, not a job-time decision.
    assumed_depth_ft = Column(Float, nullable=False)
    depth_confidence_band_ft = Column(Float, nullable=False)
    depth_overage_rate_per_ft = Column(Float, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Quotation(Base):
    """Append-only versioning (FR-QUOTE-05): an edit never mutates an
    existing row, it inserts a new one with version + 1. This makes
    'the customer only ever sees the latest version' a simple MAX(version)
    query, and makes BR-06 (can't silently change an approved price) true
    by construction rather than a rule someone has to remember to check."""

    __tablename__ = "quotations"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    contractor_id = Column(String(36), nullable=False, index=True)
    job_type = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="draft")

    line_items = Column(JSON, nullable=False)
    subtotal = Column(Float, nullable=False)
    margin_amount = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    minimum_charge_applied = Column(Boolean, nullable=False, default=False)

    estimated_depth_min_ft = Column(Float, nullable=False)
    estimated_depth_max_ft = Column(Float, nullable=False)
    confidence = Column(String, nullable=False, default="low")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
