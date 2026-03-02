"""template show raw

Revision ID: 0005_template_show_raw
Revises: 0004_template_title
Create Date: 2026-03-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_template_show_raw"
down_revision = "0004_template_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.add_column(sa.Column("show_raw", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.drop_column("show_raw")
