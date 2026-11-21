"""payments-data: remember which contractor a payment belongs to

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21

A contractor must only see and settle the payments of jobs they quoted, and
the payments table did not say who that was. Nullable: rows created before
this migration stay null and are matched against the quotation on first use
(see _require_payment_contractor in app/main.py) - there is no way to infer
the contractor from this database alone, so nothing is guessed here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("contractor_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_payments_contractor_id", ["contractor_id"])


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_contractor_id")
        batch_op.drop_column("contractor_id")
