"""drop unused ingress default route

Revision ID: 0013_drop_ingress_default_route
Revises: 0012_drop_rules
Create Date: 2026-03-02 00:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0013_drop_ingress_default_route"
down_revision = "0012_drop_rules"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "ingresses" not in inspector.get_table_names():
        return
    if not _has_column(inspector, "ingresses", "default_route_id"):
        return

    with op.batch_alter_table("ingresses") as batch:
        batch.drop_column("default_route_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "ingresses" not in inspector.get_table_names():
        return
    if _has_column(inspector, "ingresses", "default_route_id"):
        return

    with op.batch_alter_table("ingresses") as batch:
        batch.add_column(sa.Column("default_route_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ingresses_default_route_id_routes",
            "routes",
            ["default_route_id"],
            ["id"],
        )
