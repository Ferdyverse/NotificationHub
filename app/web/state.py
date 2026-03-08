from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.runtime import DedupeCache, RateLimiter

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["current_year"] = lambda: datetime.now(timezone.utc).year
templates.env.globals["settings_get"] = lambda key: getattr(settings, key, None)

runtime_dedupe = DedupeCache(settings.default_dedupe_seconds)
runtime_rate = RateLimiter(settings.default_rate_limit_per_min)

logger = logging.getLogger("notificationhub")

EVENTS_PAGE_SIZE = 50
EVENT_SEVERITY_OPTIONS = ("success", "info", "warning", "error")
DELIVERY_STATUS_OPTIONS = (
    "delivered",
    "partial",
    "failed",
    "rate_limited",
    "deduped",
    "sample",
)
BACKUP_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+\.tar\.gz$")


def log_info(message: str, **fields: Any) -> None:
    """Log structured information with JSON-serializable fields.

    Supports easy parsing by JSON log aggregators (ELK, Datadog, etc).
    Fields are logged as JSON in the extra parameter.
    """
    try:
        # Ensure all fields are JSON-serializable
        json_safe_fields = {}
        for key, value in fields.items():
            try:
                json.dumps(value)
                json_safe_fields[key] = value
            except (TypeError, ValueError):
                # Fallback to string representation if not JSON-serializable
                json_safe_fields[key] = str(value)

        logger.info(message, extra=json_safe_fields)
    except Exception:
        # Fallback to simple logging if anything fails
        logger.info(f"{message} {fields}")
