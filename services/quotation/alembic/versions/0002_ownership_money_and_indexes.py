"""quotation: customer_id (F-01), Numeric money columns (Bug 2), composite
index, pricing_rules unique constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05

Four fixes applied together since this repo branch only had migration
0001 before this point:

1. Add customer_id to quotations - populated from platform-spine's real
   job record at generation time, not trusted from the caller (F-01: this
   is what makes the ownership check in app/main.py's
   _require_quotation_access possible at all).

2. Float -> Numeric(12,2) on all INR monetary columns in pricing_rules and
   quotations (Bug 2: float arithmetic compounds across repeated
   operations and is wrong for currency).

3. Composite index on quotations(job_id, version) so
   get_latest_quotation_for_job's ORDER BY isn't a full-table scan.

4. UniqueConstraint on pricing_rules(contractor_id, job_type) so the DB
   enforces the upsert invariant the app logic assumes but cannot protect
   under concurrent writes.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(precision=12, scale=2)

PRICING_RULE_MONEY_COLS = [
    "base_rate_per_ft",
    "casing_rate_per_ft",
    "labour_flat_fee",
    "transport_flat_fee",
    "equipment_flat_fee",
    "installation_flat_fee",
    "minimum_job_charge",
    "depth_overage_rate_per_ft",
]

QUOTATION_MONEY_COLS = ["subtotal", "margin_amount", "total"]


def upgrade():
    # ── quotations: customer_id ──────────────────────────────────────────
    op.add_column(
        "quotations",
        sa.Column("customer_id", sa.String(length=36), nullable=False, server_default=""),
    )
    op.create_index("ix_quotations_customer_id", "quotations", ["customer_id"])
    with op.batch_alter_table("quotations") as batch_op:
        batch_op.alter_column("customer_id", server_default=None)

    # ── pricing_rules: Float → Numeric + unique constraint ──────────────
    with op.batch_alter_table("pricing_rules") as batch_op:
        for col in PRICING_RULE_MONEY_COLS:
            batch_op.alter_column(col, type_=MONEY, existing_nullable=False)
        batch_op.create_unique_constraint(
            "uq_pricing_rules_contractor_job_type", ["contractor_id", "job_type"]
        )

    # ── quotations: Float → Numeric + composite index ───────────────────
    with op.batch_alter_table("quotations") as batch_op:
        for col in QUOTATION_MONEY_COLS:
            batch_op.alter_column(col, type_=MONEY, existing_nullable=False)

    op.create_index("ix_quotations_job_id_version", "quotations", ["job_id", "version"])


def downgrade():
    op.drop_index("ix_quotations_job_id_version", table_name="quotations")
    with op.batch_alter_table("quotations") as batch_op:
        for col in QUOTATION_MONEY_COLS:
            batch_op.alter_column(col, type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("pricing_rules") as batch_op:
        batch_op.drop_constraint("uq_pricing_rules_contractor_job_type", type_="unique")
        for col in PRICING_RULE_MONEY_COLS:
            batch_op.alter_column(col, type_=sa.Float(), existing_nullable=False)
    op.drop_index("ix_quotations_customer_id", table_name="quotations")
    op.drop_column("quotations", "customer_id")
