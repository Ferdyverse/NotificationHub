"""add event log indexes for ui filtering

Revision ID: 0014_event_log_indexes
Revises: 0013_drop_ingress_default_route
Create Date: 2026-03-03 00:00:00

"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0014_event_log_indexes"
down_revision = "0013_drop_ingress_default_route"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "event_logs" not in inspector.get_table_names():
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("event_logs")}
    if "ix_event_logs_created_at" not in existing_indexes:
        op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"])
    if "ix_event_logs_ingress_id" not in existing_indexes:
        op.create_index("ix_event_logs_ingress_id", "event_logs", ["ingress_id"])
    if "ix_event_logs_delivery_status" not in existing_indexes:
        op.create_index(
            "ix_event_logs_delivery_status", "event_logs", ["delivery_status"]
        )
    if "ix_event_logs_source" not in existing_indexes:
        op.create_index("ix_event_logs_source", "event_logs", ["source"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "event_logs" not in inspector.get_table_names():
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("event_logs")}
    if "ix_event_logs_source" in existing_indexes:
        op.drop_index("ix_event_logs_source", table_name="event_logs")
    if "ix_event_logs_delivery_status" in existing_indexes:
        op.drop_index("ix_event_logs_delivery_status", table_name="event_logs")
    if "ix_event_logs_ingress_id" in existing_indexes:
        op.drop_index("ix_event_logs_ingress_id", table_name="event_logs")
    if "ix_event_logs_created_at" in existing_indexes:
        op.drop_index("ix_event_logs_created_at", table_name="event_logs")
