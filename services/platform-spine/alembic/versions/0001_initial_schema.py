"""initial schema - users and jobs

Revision ID: 0001
Revises:
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("customer", "contractor", "admin", name="user_role"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("customer_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("contractor_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("location_lat", sa.Float(), nullable=False),
        sa.Column("location_lng", sa.Float(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "lead", "site_location", "requirement", "estimation", "price_calculation",
                "quotation", "customer_approval", "booking", "resource_allocation",
                "drilling", "progress", "completion", "payment", "service_history",
                name="job_status",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("jobs")
    op.drop_table("users")
