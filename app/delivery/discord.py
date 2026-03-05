from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.delivery.base import DeliveryResult, bearer_headers, with_retries

logger = logging.getLogger("notificationhub.discord")


def _parse_embed_color(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        if 0 <= value <= 0xFFFFFF:
            return value
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.startswith("#"):
            raw = raw[1:]
        if raw.lower().startswith("0x"):
            raw = raw[2:]
        try:
            parsed = int(raw, 16)
        except ValueError:
            return None
        if 0 <= parsed <= 0xFFFFFF:
            return parsed
    return None


def _build_discord_payload(config: dict, title: str, body: str) -> dict:
    content = f"**{title}**\n{body}" if title else body
    if not config.get("use_embed"):
        return {"content": content}

    embed: dict[str, object] = {"description": body[:4096]}
    if title:
        embed["title"] = title[:256]
    color = _parse_embed_color(config.get("embed_color"))
    if color is not None:
        embed["color"] = color
    return {"embeds": [embed]}


def _normalize_custom_payload(payload: object) -> dict:
    if isinstance(payload, list):
        return {"embeds": payload}
    if not isinstance(payload, dict):
        raise ValueError("Discord embed template must render a JSON object or array.")
    if any(
        key in payload
        for key in (
            "content",
            "embeds",
            "username",
            "avatar_url",
            "tts",
            "allowed_mentions",
            "components",
            "flags",
            "thread_name",
            "thread_id",
        )
    ):
        return payload
    return {"embeds": [payload]}


def _build_discord_payload_from_extra(extra: dict | None) -> dict | None:
    if not extra:
        return None
    raw_payload = extra.get("discord_payload_json")
    if raw_payload is None:
        return None
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        raise ValueError("Discord embed template produced an empty payload.")
    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Discord embed template is invalid JSON: {exc}") from exc
    return _normalize_custom_payload(parsed)


def deliver_discord(
    config: dict, title: str, body: str, extra: dict | None = None
) -> DeliveryResult:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return DeliveryResult(False, "failed", "Missing Discord webhook URL")

    timeout = settings.outbound_timeout_seconds
    headers = bearer_headers(config)
    try:
        payload = _build_discord_payload_from_extra(extra)
    except ValueError as exc:
        return DeliveryResult(False, "failed", str(exc))
    if payload is None:
        payload = _build_discord_payload(config, title, body)

    def _send():
        resp = httpx.post(webhook_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return DeliveryResult(True, "delivered")

    try:
        return with_retries(_send)
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(
            "discord_delivery_failed",
            extra={
                "webhook_url": webhook_url[:50] if webhook_url else None,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return DeliveryResult(False, "failed", str(exc))
