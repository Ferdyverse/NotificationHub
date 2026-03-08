from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import RuntimeConfig
from app.security.auth import require_ui_basic_auth
from app.web.state import runtime_dedupe, runtime_rate
from app.web_shared import templates

router = APIRouter()

# Keys that are editable via the UI, grouped with metadata.
SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
    "base_url": {
        "label": "Base URL",
        "type": "text",
        "group": "General",
        "description": "Public-facing URL of this instance (used in links).",
    },
    "max_events": {
        "label": "Max stored events",
        "type": "int",
        "min": 0,
        "group": "Event Log",
        "description": "Oldest events are pruned when this limit is exceeded. 0 = unlimited.",
    },
    "max_raw_payload_chars": {
        "label": "Max raw payload size (chars)",
        "type": "int",
        "min": 0,
        "group": "Event Log",
        "description": "Raw payloads larger than this are truncated before storage.",
    },
    "default_dedupe_seconds": {
        "label": "Dedup window (seconds)",
        "type": "int",
        "min": 0,
        "group": "Deduplication",
        "description": "Identical events arriving within this window are silently dropped.",
    },
    "default_rate_limit_per_min": {
        "label": "Rate limit (events / min)",
        "type": "int",
        "min": 1,
        "group": "Rate Limiting",
        "description": "Maximum events accepted per ingress per minute.",
    },
    "outbound_timeout_seconds": {
        "label": "Outbound timeout (seconds)",
        "type": "int",
        "min": 1,
        "group": "Delivery",
        "description": "Connect + read timeout for each outbound HTTP/SMTP request.",
    },
    "outbound_retry_attempts": {
        "label": "Retry attempts",
        "type": "int",
        "min": 1,
        "max": 10,
        "group": "Delivery",
        "description": "Number of delivery attempts before marking a route as failed.",
    },
    "outbound_retry_backoff_seconds": {
        "label": "Retry backoff base (seconds)",
        "type": "float",
        "min": 0.1,
        "group": "Delivery",
        "description": "Base delay for exponential back-off between retry attempts.",
    },
}

# Keys shown as read-only environment info (sensitive or infra-level).
READONLY_SETTINGS = [
    ("database_url", "Database URL"),
    ("backup_dir", "Backup directory"),
    ("session_secret", "Session secret"),
    ("ui_basic_auth_user", "UI auth user"),
]

GROUPS_ORDER = ["General", "Event Log", "Deduplication", "Rate Limiting", "Delivery"]


def _current_values() -> dict[str, str]:
    return {key: str(getattr(settings, key)) for key in SETTINGS_SCHEMA}


def _apply_and_persist(db: Session, updates: dict[str, str]) -> list[str]:
    """Validate, persist, and apply settings. Returns list of error messages."""
    errors: list[str] = []
    to_save: dict[str, str] = {}

    for key, meta in SETTINGS_SCHEMA.items():
        raw = updates.get(key, "").strip()
        if raw == "":
            errors.append(f"{meta['label']}: value is required.")
            continue
        try:
            if meta["type"] == "int":
                val = int(raw)
                if "min" in meta and val < meta["min"]:
                    errors.append(f"{meta['label']}: must be ≥ {meta['min']}.")
                    continue
                if "max" in meta and val > meta["max"]:
                    errors.append(f"{meta['label']}: must be ≤ {meta['max']}.")
                    continue
            elif meta["type"] == "float":
                val = float(raw)
                if "min" in meta and val < meta["min"]:
                    errors.append(f"{meta['label']}: must be ≥ {meta['min']}.")
                    continue
            to_save[key] = raw
        except ValueError:
            errors.append(f"{meta['label']}: invalid value '{raw}'.")

    if errors:
        return errors

    now = datetime.now(timezone.utc)
    for key, raw in to_save.items():
        row = db.get(RuntimeConfig, key)
        if row:
            row.value = raw
            row.updated_at = now
        else:
            db.add(RuntimeConfig(key=key, value=raw, updated_at=now))

    db.commit()

    # Apply to live settings object
    for key, raw in to_save.items():
        current = getattr(settings, key)
        if isinstance(current, int):
            setattr(settings, key, int(raw))
        elif isinstance(current, float):
            setattr(settings, key, float(raw))
        else:
            setattr(settings, key, raw)

    # Sync runtime caches
    runtime_dedupe.window_seconds = settings.default_dedupe_seconds
    runtime_rate.limit_per_min = settings.default_rate_limit_per_min

    return []


@router.get(
    "/ui/settings",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_settings(request: Request, db: Session = Depends(get_session)):
    stored: dict[str, str] = {}
    for row in db.scalars(select(RuntimeConfig)).all():
        stored[row.key] = row.value

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "schema": SETTINGS_SCHEMA,
            "groups_order": GROUPS_ORDER,
            "current": _current_values(),
            "stored": stored,
            "readonly": READONLY_SETTINGS,
            "errors": [],
            "saved": False,
        },
    )


@router.post(
    "/ui/settings",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_settings_save(request: Request, db: Session = Depends(get_session)):
    form = await request.form()
    updates = {key: str(form.get(key, "")) for key in SETTINGS_SCHEMA}

    errors = _apply_and_persist(db, updates)

    stored: dict[str, str] = {}
    for row in db.scalars(select(RuntimeConfig)).all():
        stored[row.key] = row.value

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "schema": SETTINGS_SCHEMA,
            "groups_order": GROUPS_ORDER,
            "current": _current_values(),
            "stored": stored,
            "readonly": READONLY_SETTINGS,
            "errors": errors,
            "saved": not errors,
        },
    )
