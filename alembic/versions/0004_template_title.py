"""template title

Revision ID: 0004_template_title
Revises: 0003_routes_apprise_nullable
Create Date: 2026-03-01 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_template_title"
down_revision = "0003_routes_apprise_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.add_column(
            sa.Column("title_template", sa.String(length=200), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.drop_column("title_template")
