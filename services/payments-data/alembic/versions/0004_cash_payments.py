"""payments-data: payment method and cash confirmation

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14

Adds cash payments (customer pays the contractor in person; a contractor
confirms receipt). `method` is a plain string defaulting to "online", so every
existing row stays a normal online payment. No enum change: the payment
status set is unchanged - a cash payment is "pending" until confirmed.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column("method", sa.String(10), nullable=False, server_default="online")
        )
        batch_op.add_column(sa.Column("cash_confirmed_by", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("cash_confirmed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("cash_confirmed_at")
        batch_op.drop_column("cash_confirmed_by")
        batch_op.drop_column("method")
