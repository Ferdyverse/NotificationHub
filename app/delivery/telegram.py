from __future__ import annotations

import html
import logging
import re

import httpx

from app.config import settings
from app.delivery.base import DeliveryResult, with_retries

logger = logging.getLogger("notificationhub.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"

# All chars that must be escaped in MarkdownV2 (outside of formatting entities)
_MDV2_SPECIAL = re.compile(r'([_*\[\]()~`>#+\-=|{}.!\\])')
# Markdown heading lines: # … through ###### …
_MD_HEADING = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)


def _escape_mdv2(text: str) -> str:
    return _MDV2_SPECIAL.sub(r'\\\1', text)


def _headings_to_bold_mdv2(text: str) -> str:
    """Convert Markdown headings to MarkdownV2 bold before escaping."""
    def _replace(m: re.Match) -> str:
        return f"*{_escape_mdv2(m.group(1))}*"
    # Split off headings first so their content gets escaped but not re-bolded
    parts = []
    last = 0
    for m in _MD_HEADING.finditer(text):
        parts.append(_escape_mdv2(text[last:m.start()]))
        parts.append(_replace(m))
        last = m.end()
    parts.append(_escape_mdv2(text[last:]))
    return "".join(parts)


def _headings_to_bold_html(text: str) -> str:
    """Convert Markdown headings to HTML <b> before escaping."""
    def _replace(m: re.Match) -> str:
        return f"<b>{html.escape(m.group(1))}</b>"
    parts = []
    last = 0
    for m in _MD_HEADING.finditer(text):
        parts.append(html.escape(text[last:m.start()]))
        parts.append(_replace(m))
        last = m.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def _build_text(title: str, body: str, parse_mode: str | None) -> str:
    if parse_mode == "HTML":
        t = html.escape(title) if title else ""
        b = _headings_to_bold_html(body)
        return f"<b>{t}</b>\n{b}" if t else b
    if parse_mode == "MarkdownV2":
        t = _escape_mdv2(title) if title else ""
        b = _headings_to_bold_mdv2(body)
        return f"*{t}*\n{b}" if t else b
    # No parse_mode: use HTML just to bold the title, body stays plain
    if title:
        return f"<b>{html.escape(title)}</b>\n{html.escape(body)}"
    return body


def deliver_telegram(config: dict, title: str, body: str) -> DeliveryResult:
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        return DeliveryResult(False, "failed", "Missing Telegram bot_token or chat_id")

    parse_mode = config.get("parse_mode") or None
    disable_preview = bool(config.get("disable_web_page_preview"))

    text = _build_text(title, body, parse_mode)

    effective_parse_mode = parse_mode or ("HTML" if title else None)
    payload: dict = {"chat_id": chat_id, "text": text}
    if effective_parse_mode:
        payload["parse_mode"] = effective_parse_mode
    if disable_preview:
        payload["disable_web_page_preview"] = True

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    timeout = settings.outbound_timeout_seconds

    def _send():
        resp = httpx.post(url, json=payload, timeout=timeout)
        if not resp.is_success:
            try:
                tg_error = resp.json().get("description", resp.text)
            except Exception:
                tg_error = resp.text
            logger.error(
                "telegram_api_error",
                extra={"status_code": resp.status_code, "description": tg_error, "chat_id": str(chat_id)[:50]},
            )
            resp.raise_for_status()
        return DeliveryResult(True, "delivered")

    try:
        result = with_retries(_send)
        return result if result is not None else DeliveryResult(False, "failed", "No result from delivery")
    except httpx.HTTPError as exc:
        return DeliveryResult(False, "failed", str(exc))
