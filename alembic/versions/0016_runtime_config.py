"""Add runtime_config table for UI-editable settings.

Revision ID: 0016_runtime_config
Revises: 0015_event_log_request_ip
Create Date: 2026-03-08 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0016_runtime_config"
down_revision = "0015_event_log_request_ip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_config")
