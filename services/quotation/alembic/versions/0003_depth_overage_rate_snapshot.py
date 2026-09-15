"""quotation: add depth_overage_rate_per_ft snapshot to quotations (BR-05)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14

Closes the TODO in platform-spine's job completion endpoint
(services/platform-spine/app/main.py) - BR-05 (SRS section 4) requires
depth overage to be priced at the contractor's configured per-foot rate,
but that rate was never actually reachable from the completion flow.
This snapshots PricingRule.depth_overage_rate_per_ft onto the quotation
row at generation/edit time, same pattern as every other pricing input
already stored there (estimated_depth_min_ft, confidence, etc.) - a
snapshot, not a live reference, so an approved quote keeps reflecting
the rate the customer actually saw (BR-06).

Nullable: existing quotation rows predate this column and have no rate
to backfill from (the PricingRule that generated them may have since
changed or been deleted) - NULL for old rows, populated for every new one.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(precision=12, scale=2)


def upgrade():
    with op.batch_alter_table("quotations") as batch_op:
        batch_op.add_column(sa.Column("depth_overage_rate_per_ft", MONEY, nullable=True))


def downgrade():
    with op.batch_alter_table("quotations") as batch_op:
        batch_op.drop_column("depth_overage_rate_per_ft")
