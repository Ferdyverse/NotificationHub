"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-03-01 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("apprise_target", sa.String(length=500), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "ingresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("default_route_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["default_route_id"], ["routes.id"]),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("ingress_id", sa.Integer(), nullable=True),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ingress_id"], ["ingresses.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
    )
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingress_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("event", sa.String(length=200), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["ingress_id"], ["ingresses.id"]),
    )


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("rules")
    op.drop_table("ingresses")
    op.drop_table("templates")
    op.drop_table("routes")
