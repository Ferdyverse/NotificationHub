from __future__ import annotations

import time
from dataclasses import dataclass

from app.config import settings


@dataclass
class DeliveryResult:
    success: bool
    status: str
    error: str | None = None
    meta: dict | None = None


def with_retries(fn):
    attempts = settings.outbound_retry_attempts
    backoff = settings.outbound_retry_backoff_seconds
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(backoff * (2**attempt))
    raise last_exc


def bearer_headers(config: dict | None) -> dict[str, str]:
    if not config:
        return {}
    token = config.get("bearer_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
