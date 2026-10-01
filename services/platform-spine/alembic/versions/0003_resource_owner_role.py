"""platform-spine: add resource_owner to the user_role enum

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

app/models.py has listed four roles since the marketplace pivot
(ROLES = ("customer", "contractor", "admin", "resource_owner"), and
docs/adr/0004 makes resource_owner a first-class registerable role), but no
migration ever added the value to the Postgres enum created in 0001, which
only has customer/contractor/admin.

The gap does not show up in the service tests (SQLite renders SAEnum as a
VARCHAR + CHECK built from the model, so the model's own list is used), but
on a real Postgres database POST /v1/auth/register with role
"resource_owner" fails with:

    psycopg2.errors.InvalidTextRepresentation:
    invalid input value for enum user_role: "resource_owner"

Found while wiring the rig-owner screens in apps/web-app against a local
stack - no rig owner could register at all.

ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
PostgreSQL versions before 12, and Alembic wraps migrations in one, so the
connection is committed first and the ALTER issued with autocommit. IF NOT
EXISTS keeps this safe to re-run on a database where the value was added by
hand.

Downgrade is intentionally a no-op: PostgreSQL cannot remove a value from
an enum without rewriting the type and every column that uses it, and
dropping a role that live rows may reference would lose data.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'resource_owner'"))


def downgrade():
    # See module docstring - deliberately not reversible.
    pass
