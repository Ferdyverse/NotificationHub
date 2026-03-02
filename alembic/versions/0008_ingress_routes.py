"""ingress routes fanout

Revision ID: 0008_ingress_routes
Revises: 0007_rule_template
Create Date: 2026-03-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_ingress_routes"
down_revision = "0007_rule_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "ingress_routes" not in inspector.get_table_names():
        op.create_table(
            "ingress_routes",
            sa.Column("ingress_id", sa.Integer(), sa.ForeignKey("ingresses.id"), primary_key=True),
            sa.Column("route_id", sa.Integer(), sa.ForeignKey("routes.id"), primary_key=True),
        )


def downgrade() -> None:
    op.drop_table("ingress_routes")
