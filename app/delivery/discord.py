from __future__ import annotations

import httpx

from app.config import settings
from app.delivery.base import DeliveryResult, bearer_headers, with_retries


def deliver_discord(config: dict, title: str, body: str) -> DeliveryResult:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return DeliveryResult(False, "failed", "Missing Discord webhook URL")

    timeout = settings.outbound_timeout_seconds
    headers = bearer_headers(config)
    payload = {"content": f"**{title}**\n{body}"}

    def _send():
        resp = httpx.post(webhook_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return DeliveryResult(True, "delivered")

    try:
        return with_retries(_send)
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult(False, "failed", str(exc))
