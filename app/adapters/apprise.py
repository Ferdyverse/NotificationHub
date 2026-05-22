from __future__ import annotations

from typing import Any

from app.adapters.types import NormalizedEvent

_TYPE_MAP = {
    "failure": "error",
    "warning": "warning",
    "success": "success",
    "info": "info",
}


def is_apprise_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return payload.get("version") == "1.0" and "type" in payload and "message" in payload


def adapt(payload: dict[str, Any]) -> NormalizedEvent:
    severity = _TYPE_MAP.get(str(payload.get("type", "info")).lower(), "info")
    title = str(payload.get("title") or "Apprise Notification")
    message = str(payload.get("message") or "")
    return NormalizedEvent(
        source="apprise",
        event="apprise.notify",
        severity=severity,
        title=title,
        message=message,
        raw=payload,
    ).with_timestamp()
