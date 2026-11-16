"""quotation: walk-in flag and on-behalf decision record

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15

quotations.walk_in: copied from the job (platform-spine jobs.walk_in) when the
quotation is generated; for a walk-in customer (no account) the contractor
approves or rejects on their behalf. quotations.decided_by records who made
that decision. Both additive: existing rows are walk_in=false, decided_by=null.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("quotations") as batch_op:
        batch_op.add_column(
            sa.Column("walk_in", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("decided_by", sa.String(36), nullable=True))


def downgrade():
    with op.batch_alter_table("quotations") as batch_op:
        batch_op.drop_column("decided_by")
        batch_op.drop_column("walk_in")
