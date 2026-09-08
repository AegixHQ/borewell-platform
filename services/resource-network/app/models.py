import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Numeric, String
from sqlalchemy import Enum as SAEnum

from app.database import Base

RESOURCE_TYPES = ("rig", "equipment", "labour")
# 5-state model: this is the resource's PHYSICAL state, distinct from any
# booking request's status (see BookingRequest below). Only an accepted
# booking request moves a resource from "available" to "reserved" - the
# resource itself doesn't track who requested it, the booking table does.
RESOURCE_STATUSES = ("available", "reserved", "assigned", "in_use", "returned")

BOOKING_STATUSES = ("pending", "accepted", "rejected", "cancelled")

# Same MONEY convention as quotation/payments-data/platform-spine (Bug 2 fix).
MONEY = Numeric(precision=12, scale=2)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Resource(Base):
    __tablename__ = "resources"

    id = Column(String(36), primary_key=True, default=new_uuid)
    # owner_id: the resource_owner (rig/equipment/labour owner) who
    # registered this resource. Marketplace model (like the ride-share/
    # food-delivery pattern this platform follows) - NOT the contractor.
    # A contractor requests to book someone else's resource; they never
    # own it. See docs/adr/0004 for the earlier (superseded) single-
    # contractor-owns-its-own-fleet model this replaces.
    owner_id = Column(String(36), nullable=False, index=True)
    resource_type = Column(SAEnum(*RESOURCE_TYPES, name="resource_type"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(
        SAEnum(*RESOURCE_STATUSES, name="resource_status"), nullable=False, default="available"
    )
    notes = Column(String, nullable=True)
    # Nullable: a resource created without a location simply isn't
    # searchable via POST /v1/resources/match (excluded, not error/null-
    # distance) - see that endpoint and its contract doc.
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    hourly_rate = Column(MONEY, nullable=True)
    vehicle_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BookingRequest(Base):
    """A contractor's request to book a specific resource_owner's resource
    for a job. Zomato-style flow: contractor requests -> owner accepts or
    rejects -> only on accept does the resource move to 'reserved'.

    owner_id is denormalized from the resource at request time (not just
    joined via resource_id) so an owner's booking-request list is a single
    indexed query, and so the ownership at request time is preserved even
    if a resource were ever reassigned (not currently possible, but this
    avoids relying on a join staying consistent for something the DoD
    treats as an access-control boundary).
    """
    __tablename__ = "booking_requests"

    id = Column(String(36), primary_key=True, default=new_uuid)
    resource_id = Column(String(36), nullable=False, index=True)
    owner_id = Column(String(36), nullable=False, index=True)
    contractor_id = Column(String(36), nullable=False, index=True)
    job_id = Column(String(36), nullable=True)
    status = Column(
        SAEnum(*BOOKING_STATUSES, name="booking_status"), nullable=False, default="pending"
    )
    message = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime, nullable=True)


class ServiceArea(Base):
    """Pilot-scope water-depth reference data (Madurai district villages).
    See docs/adr/0004: estimated_water_depth_ft is contractor/admin-edited,
    not sourced from a real groundwater API in MVP - a deliberate seam for
    a real data provider to plug into later without touching quotation
    service's calling code.
    """
    __tablename__ = "service_areas"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String, nullable=False)
    district = Column(String, nullable=False)
    state = Column(String, nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    estimated_water_depth_ft = Column(Float, nullable=False)
    confidence_band_ft = Column(Float, nullable=False)
    source = Column(String, nullable=False, default="contractor_estimate")
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
