"""platform-spine: add job_completions table (FR-TRACK-03)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06

New table for actual depth/cost logging at job completion. Separate table
rather than adding nullable columns to jobs for two reasons:
1. BR-04: "only writable once" - a separate table with unique(job_id)
   enforces this at the DB level, not just in application code.
2. Keeps the jobs table's structure stable and migration-free for a new
   requirement that only applies to the terminal lifecycle stage.

Financials use Numeric(12,2) matching the MONEY convention in quotation
and payments-data (same Bug 2 fix applied consistently here).
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(precision=12, scale=2)


def upgrade():
    op.create_table(
        "job_completions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("actual_depth_ft", sa.Float, nullable=False),
        sa.Column("depth_overage_ft", sa.Float, nullable=False, server_default="0"),
        sa.Column("actual_cost", MONEY, nullable=False),
        sa.Column("quoted_total", MONEY, nullable=False),
        sa.Column("variance", MONEY, nullable=False),
        sa.Column("depth_overage_charge", MONEY, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("job_completions")
