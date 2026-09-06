"""payments-data: Numeric money column (Bug 2, same fix as quotation service)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06

payments.amount was still Float when everywhere else in the platform
(quotation service's pricing_rules/quotations, see that service's own 0002
migration) had already moved to Numeric(12,2). This is the one column where
it mattered most: main.py compares payload.amount against the quotation
service's total_estimate for EXACT equality (SRS section 6 - "reject
mismatches", not "reject if the difference exceeds some epsilon"). A Float
column here meant that comparison was float-vs-float on the DB/storage
side even after the app-layer Decimal fix, since SQLAlchemy round-trips a
Float column through Python float on read.

Float -> Numeric(12,2) on the one INR monetary column in payments.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(precision=12, scale=2)


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column("amount", type_=MONEY, existing_nullable=False)


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column("amount", type_=sa.Float(), existing_nullable=False)
