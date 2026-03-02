"""template discord embed

Revision ID: 0009_template_discord_embed
Revises: 0008_ingress_routes
Create Date: 2026-03-02 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_template_discord_embed"
down_revision = "0008_ingress_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.add_column(sa.Column("discord_embed_template", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("templates") as batch:
        batch.drop_column("discord_embed_template")
