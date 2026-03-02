"""route template

Revision ID: 0006_route_template
Revises: 0005_template_show_raw
Create Date: 2026-03-01 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_route_template"
down_revision = "0005_template_show_raw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("routes") as batch:
        batch.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_routes_template", "templates", ["template_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("routes") as batch:
        batch.drop_constraint("fk_routes_template", type_="foreignkey")
        batch.drop_column("template_id")
