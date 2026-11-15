"""platform-spine: users.google_sub for Google sign-in

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14

Nullable and unique: Google's stable account ID, set the first time a user
signs in with Google. Existing users are unaffected (null).
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("google_sub", sa.String(), nullable=True))
        batch_op.create_index("ix_users_google_sub", ["google_sub"], unique=True)


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_google_sub")
        batch_op.drop_column("google_sub")
