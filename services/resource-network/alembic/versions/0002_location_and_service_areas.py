"""resource-network: marketplace ownership model + location + service areas

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07

Multi-owner marketplace model (Zomato-for-drilling-rigs), not a single-
contractor-owns-its-own-fleet model. Three changes:

1. resources.contractor_id -> resources.owner_id: a Resource belongs to a
   resource_owner (a distinct authenticated role - see platform-spine's
   ROLES), not the contractor. A contractor books someone else's resource
   via a BookingRequest, never owns one directly. Clean replace, not a
   data migration - no real data exists yet to preserve (confirmed before
   writing this).
2. New booking_requests table: contractor requests -> owner accepts/
   rejects. Real Zomato-style flow, not a passive listing.
3. resources gains lat/lng (nullable), hourly_rate (MONEY/Numeric, same
   Bug 2 convention), vehicle_type - needed for the nearest-resource
   search and the quoted price.
4. New service_areas table: pilot-scope, contractor-editable water-depth
   estimates for a handful of Madurai district villages (docs/adr/0004 -
   NOT a real groundwater API integration, see ServiceArea model's
   docstring).
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(precision=12, scale=2)


def upgrade():
    with op.batch_alter_table("resources") as batch_op:
        batch_op.alter_column("contractor_id", new_column_name="owner_id")
        batch_op.add_column(sa.Column("lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lng", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("hourly_rate", MONEY, nullable=True))
        batch_op.add_column(sa.Column("vehicle_type", sa.String(), nullable=True))

    op.create_table(
        "booking_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("resource_id", sa.String(36), nullable=False, index=True),
        sa.Column("owner_id", sa.String(36), nullable=False, index=True),
        sa.Column("contractor_id", sa.String(36), nullable=False, index=True),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "service_areas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("district", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lng", sa.Float(), nullable=False),
        sa.Column("radius_km", sa.Float(), nullable=False),
        sa.Column("estimated_water_depth_ft", sa.Float(), nullable=False),
        sa.Column("confidence_band_ft", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="contractor_estimate"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("service_areas")
    op.drop_table("booking_requests")
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_column("vehicle_type")
        batch_op.drop_column("hourly_rate")
        batch_op.drop_column("lng")
        batch_op.drop_column("lat")
        batch_op.alter_column("owner_id", new_column_name="contractor_id")
