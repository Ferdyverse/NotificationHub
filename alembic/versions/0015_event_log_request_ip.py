"""Add request_ip column to event_logs table for audit logging.

Revision ID: 0015_event_log_request_ip
Revises: 0014_event_log_indexes
Create Date: 2026-03-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0015_event_log_request_ip"
down_revision = "0014_event_log_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_logs",
        sa.Column("request_ip", sa.String(45), nullable=True),
    )
    op.create_index(
        "ix_event_logs_request_ip",
        "event_logs",
        ["request_ip"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_logs_request_ip", table_name="event_logs")
    op.drop_column("event_logs", "request_ip")
