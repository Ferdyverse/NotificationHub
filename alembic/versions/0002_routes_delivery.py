"""routes delivery config

Revision ID: 0002_routes_delivery
Revises: 0001_init
Create Date: 2026-03-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_routes_delivery"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("routes") as batch:
        batch.add_column(sa.Column("route_type", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("config", sa.JSON(), nullable=True))
        batch.alter_column(
            "apprise_target",
            existing_type=sa.String(length=500),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("routes") as batch:
        batch.alter_column(
            "apprise_target",
            existing_type=sa.String(length=500),
            nullable=False,
        )
        batch.drop_column("config")
        batch.drop_column("route_type")
