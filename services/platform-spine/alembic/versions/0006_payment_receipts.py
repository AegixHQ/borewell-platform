"""platform-spine: payment_receipts table

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21

Persists that payment.completed was received for a job, so a payment that
completes before the job reaches "completion" is not lost (Redis pub/sub does
not replay). unique(job_id) makes redelivery a no-op at the database level.
Additive only: no existing table changes. Rows exist only for payments
announced after this migration; earlier payments are not backfilled.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("received_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("payment_receipts")
