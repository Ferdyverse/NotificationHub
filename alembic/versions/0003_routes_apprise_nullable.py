"""make apprise_target nullable

Revision ID: 0003_routes_apprise_nullable
Revises: 0002_routes_delivery
Create Date: 2026-03-01 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_routes_apprise_nullable"
down_revision = "0002_routes_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("routes") as batch:
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
