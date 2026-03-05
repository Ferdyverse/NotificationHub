from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.models import Route
from app.web.state import logger


def maybe_persist_matrix_token(route: Route, result_meta: dict | None):
    if route.route_type != "matrix" or not result_meta:
        return
    token = result_meta.get("access_token")
    if not token:
        return
    if route.config is None:
        route.config = {}
    route.config["bearer_token"] = token
    expires_in_ms = result_meta.get("expires_in_ms")
    if expires_in_ms:
        route.config["token_expires_at"] = time.time() + (int(expires_in_ms) / 1000)
    flag_modified(route, "config")
    logger.info("matrix_token_persist_pending", extra={"route_id": route.id})


def build_route_config(
    route_type: str,
    matrix_homeserver: str | None,
    matrix_room_id: str | None,
    matrix_username: str | None,
    matrix_password: str | None,
    matrix_markdown: str | None,
    matrix_auto_join: str | None,
    matrix_bearer_token: str | None,
    discord_webhook_url: str | None,
    discord_bearer_token: str | None,
    discord_use_embed: str | None,
    discord_embed_color: str | None,
    email_smtp_host: str | None,
    email_smtp_port: str | None,
    email_smtp_tls: str | None,
    email_smtp_starttls: str | None,
    email_smtp_username: str | None,
    email_smtp_password: str | None,
    email_from_addr: str | None,
    email_to_addrs: str | None,
    email_subject_prefix: str | None,
) -> dict[str, Any]:
    if route_type == "matrix":
        return {
            "homeserver": matrix_homeserver,
            "room_id": matrix_room_id,
            "username": matrix_username,
            "password": matrix_password,
            "markdown": bool(matrix_markdown),
            "auto_join": bool(matrix_auto_join),
            "bearer_token": matrix_bearer_token,
        }
    if route_type == "discord":
        return {
            "webhook_url": discord_webhook_url,
            "bearer_token": discord_bearer_token,
            "use_embed": bool(discord_use_embed),
            "embed_color": discord_embed_color,
        }
    if route_type == "email":
        return {
            "smtp_host": email_smtp_host,
            "smtp_port": email_smtp_port,
            "smtp_tls": bool(email_smtp_tls),
            "smtp_starttls": bool(email_smtp_starttls),
            "smtp_username": email_smtp_username,
            "smtp_password": email_smtp_password,
            "from_addr": email_from_addr,
            "to_addrs": email_to_addrs,
            "subject_prefix": email_subject_prefix,
        }
    return {}


def validate_route_config(route_type: str, config: dict[str, Any]) -> str | None:
    if route_type == "matrix":
        if not config.get("homeserver") or not config.get("room_id"):
            return "Matrix requires homeserver and room ID."
        if not config.get("bearer_token"):
            if not config.get("username") or not config.get("password"):
                return "Matrix requires username/password or bearer token."
    elif route_type == "discord":
        if not config.get("webhook_url"):
            return "Discord requires a webhook URL."
    elif route_type == "email":
        if not config.get("smtp_host") or not config.get("smtp_port"):
            return "Email requires SMTP host and port."
        if not config.get("from_addr") or not config.get("to_addrs"):
            return "Email requires from/to addresses."
    else:
        return "Unsupported route type."
    return None
