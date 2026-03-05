from __future__ import annotations

import logging
import re

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.runtime import DedupeCache, RateLimiter

templates = Jinja2Templates(directory="app/templates")

runtime_dedupe = DedupeCache(settings.default_dedupe_seconds)
runtime_rate = RateLimiter(settings.default_rate_limit_per_min)

logger = logging.getLogger("formatter")

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


def log_info(message: str, **fields):
    logger.info("%s %s", message, fields)
