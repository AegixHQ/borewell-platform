"""platform-spine: walk-in jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15

A walk-in is a customer who came to the contractor in person and has no
account. jobs.walk_in marks those jobs (false for every existing row);
customer_name / customer_phone hold the details a users row would otherwise
carry. All three are additive; nothing existing changes.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column("walk_in", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("customer_name", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("customer_phone", sa.String(20), nullable=True))


def downgrade():
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("customer_phone")
        batch_op.drop_column("customer_name")
        batch_op.drop_column("walk_in")
