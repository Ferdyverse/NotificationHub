from __future__ import annotations

import json
from typing import Any

from app.adapters.types import NormalizedEvent


def adapt(payload: Any) -> NormalizedEvent:
    if isinstance(payload, dict):
        source = str(payload.get("source") or "generic")
        event = str(payload.get("event") or "generic.json")
        severity = str(payload.get("severity") or "info")
        title = str(payload.get("title") or "")
        message = payload.get("message")
        if message is None:
            message = json.dumps(payload, indent=2, ensure_ascii=False)
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else None
        entities = (
            payload.get("entities") if isinstance(payload.get("entities"), dict) else None
        )
        return NormalizedEvent(
            source=source,
            event=event,
            severity=severity,
            title=title,
            message=str(message),
            tags=tags,
            entities=entities,
            raw=payload,
        ).with_timestamp()

    return NormalizedEvent(
        source="generic",
        event="generic.json",
        severity="info",
        title="Generic JSON",
        message=str(payload),
        raw=payload,
    ).with_timestamp()
