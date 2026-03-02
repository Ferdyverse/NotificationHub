"""ingress default template

Revision ID: 0010_ingress_default_template
Revises: 0009_template_discord_embed
Create Date: 2026-03-02 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_ingress_default_template"
down_revision = "0009_template_discord_embed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ingresses") as batch:
        batch.add_column(sa.Column("default_template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ingresses_default_template_id_templates",
            "templates",
            ["default_template_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ingresses") as batch:
        batch.drop_constraint("fk_ingresses_default_template_id_templates", type_="foreignkey")
        batch.drop_column("default_template_id")
