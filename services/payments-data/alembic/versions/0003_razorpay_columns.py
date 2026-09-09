"""payments-data: add Razorpay order/payment ID columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08

Two nullable columns for the real Razorpay integration (replaces the
admin-gated confirm/fail placeholders as the primary confirmation path -
see app/main.py's create_order and webhook endpoints):
- razorpay_order_id: set once POST /v1/payments/{id}/create-order is
  called.
- razorpay_payment_id: set once Razorpay's webhook reports an actual
  payment attempt (captured or failed) against that order.

Both nullable and both indexed - order_id is looked up when a webhook
event needs to find the corresponding local payment row (Razorpay's
webhook payload includes the order_id, not our internal payment UUID).
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("razorpay_order_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("razorpay_payment_id", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_payments_razorpay_order_id", ["razorpay_order_id"], unique=False
        )
        batch_op.create_index(
            "ix_payments_razorpay_payment_id", ["razorpay_payment_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_razorpay_payment_id")
        batch_op.drop_index("ix_payments_razorpay_order_id")
        batch_op.drop_column("razorpay_payment_id")
        batch_op.drop_column("razorpay_order_id")
