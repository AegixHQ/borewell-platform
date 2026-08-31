"""initial schema - pricing_rules and quotations"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("contractor_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("base_rate_per_ft", sa.Float(), nullable=False),
        sa.Column("casing_rate_per_ft", sa.Float(), nullable=False),
        sa.Column("labour_flat_fee", sa.Float(), nullable=False),
        sa.Column("transport_flat_fee", sa.Float(), nullable=False),
        sa.Column("equipment_flat_fee", sa.Float(), nullable=False),
        sa.Column("installation_flat_fee", sa.Float(), nullable=False),
        sa.Column("margin_percent", sa.Float(), nullable=False),
        sa.Column("minimum_job_charge", sa.Float(), nullable=False),
        sa.Column("assumed_depth_ft", sa.Float(), nullable=False),
        sa.Column("depth_confidence_band_ft", sa.Float(), nullable=False),
        sa.Column("depth_overage_rate_per_ft", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "quotations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("contractor_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("line_items", sa.JSON(), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.Column("margin_amount", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("minimum_charge_applied", sa.Boolean(), nullable=False),
        sa.Column("estimated_depth_min_ft", sa.Float(), nullable=False),
        sa.Column("estimated_depth_max_ft", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("quotations")
    op.drop_table("pricing_rules")
