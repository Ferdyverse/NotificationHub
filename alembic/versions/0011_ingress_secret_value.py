"""ingress secret value for signature validation

Revision ID: 0011_ingress_secret_value
Revises: 0010_ingress_default_template
Create Date: 2026-03-02 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_ingress_secret_value"
down_revision = "0010_ingress_default_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ingresses") as batch:
        batch.add_column(sa.Column("secret_value", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ingresses") as batch:
        batch.drop_column("secret_value")
