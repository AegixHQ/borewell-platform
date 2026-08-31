import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

RESOURCE_TYPES = ("rig", "equipment", "labour")
# 5-state model per the original vision doc section 7 and this service's own
# AGENTS.md - deliberate, not a placeholder. No automated matching drives
# these transitions in MVP; the contractor sets them manually.
RESOURCE_STATUSES = ("available", "reserved", "assigned", "in_use", "returned")


def new_uuid() -> str:
    return str(uuid.uuid4())


class Resource(Base):
    __tablename__ = "resources"

    id = Column(String(36), primary_key=True, default=new_uuid)
    contractor_id = Column(String(36), nullable=False, index=True)
    resource_type = Column(SAEnum(*RESOURCE_TYPES, name="resource_type"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(
        SAEnum(*RESOURCE_STATUSES, name="resource_status"), nullable=False, default="available"
    )
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
