from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class NormalizedEvent:
    source: str
    event: str
    severity: str
    title: str
    message: str
    tags: list[str] | None = None
    entities: dict[str, Any] | None = None
    raw: Any | None = None
    timestamp: str | None = None

    def with_timestamp(self) -> "NormalizedEvent":
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        return self


STATUS_ICONS = {
    "success": "✅",
    "warning": "⚠️",
    "error": "❌",
    "info": "ℹ️",
}
