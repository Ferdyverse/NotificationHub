from __future__ import annotations

from app.config import settings
from app.web.backup import (
    build_backup_filename,
    ensure_backup_dir_available,
    list_backup_files,
    resolve_backup_dir,
)
from app.web.event_filters import enforce_event_log_limit, normalized_search_filters
from app.web.ingest_auth import _authorize_ingress_request
from app.web.ingest_processing import adapt_request_payload, build_dedupe_key
from app.web.route_config import (
    build_route_config,
    maybe_persist_matrix_token,
    validate_route_config,
)
from app.web.state import (
    BACKUP_FILENAME_PATTERN,
    DELIVERY_STATUS_OPTIONS,
    EVENTS_PAGE_SIZE,
    EVENT_SEVERITY_OPTIONS,
    logger,
    log_info,
    runtime_dedupe,
    runtime_rate,
    templates,
)
from app.web.template_helpers import (
    build_event_log,
    build_template_context,
    ensure_defaults,
    load_default_template,
    render_notification_content,
    resolve_template_id,
)

__all__ = [
    "settings",
    "templates",
    "runtime_dedupe",
    "runtime_rate",
    "logger",
    "EVENTS_PAGE_SIZE",
    "EVENT_SEVERITY_OPTIONS",
    "DELIVERY_STATUS_OPTIONS",
    "BACKUP_FILENAME_PATTERN",
    "log_info",
    "resolve_backup_dir",
    "ensure_backup_dir_available",
    "build_backup_filename",
    "list_backup_files",
    "maybe_persist_matrix_token",
    "build_route_config",
    "validate_route_config",
    "ensure_defaults",
    "load_default_template",
    "build_event_log",
    "build_template_context",
    "resolve_template_id",
    "render_notification_content",
    "_authorize_ingress_request",
    "adapt_request_payload",
    "build_dedupe_key",
    "enforce_event_log_limit",
    "normalized_search_filters",
]
