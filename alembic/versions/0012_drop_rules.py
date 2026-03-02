"""drop legacy rules table

Revision ID: 0012_drop_rules
Revises: 0011_ingress_secret_value
Create Date: 2026-03-02 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012_drop_rules"
down_revision = "0011_ingress_secret_value"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "rules" in inspector.get_table_names():
        op.drop_table("rules")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "rules" not in inspector.get_table_names():
        op.create_table(
            "rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("ingress_id", sa.Integer(), nullable=True),
            sa.Column("route_id", sa.Integer(), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=True),
            sa.Column("conditions", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["ingress_id"], ["ingresses.id"]),
            sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
            sa.ForeignKeyConstraint(["template_id"], ["templates.id"]),
        )
