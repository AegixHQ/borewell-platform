"""initial schema - payments"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("quotation_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("customer_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True, index=True),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "failed", name="payment_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("payments")
