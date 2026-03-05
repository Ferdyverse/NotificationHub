from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.types import NormalizedEvent
from app.config import settings
from app.models import EventLog, Ingress, Route, Template
from app.render.templates import DEFAULT_TEMPLATE_BODY, render_template


def ensure_defaults(db: Session):
    if settings.database_url.startswith("sqlite:///./"):
        db_path = settings.database_url.replace("sqlite:///./", "", 1)
        if "/" in db_path:
            import os

            os.makedirs(os.path.dirname(db_path), exist_ok=True)
    try:
        template = db.scalar(select(Template).where(Template.is_default.is_(True)))
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is not initialized. Run 'alembic upgrade head' before starting the app."
        ) from exc
    if template is None:
        template = Template(
            name="Default",
            title_template=None,
            body=DEFAULT_TEMPLATE_BODY,
            show_raw=True,
            is_default=True,
        )
        db.add(template)
        db.commit()


def load_default_template(db: Session) -> Template:
    template = db.scalar(select(Template).where(Template.is_default.is_(True)))
    if template:
        return template
    return Template(
        name="Default",
        title_template=None,
        body=DEFAULT_TEMPLATE_BODY,
        show_raw=True,
        is_default=True,
    )


def extract_client_ip(request: Request) -> str | None:
    """Extract client IP from request, considering X-Forwarded-For header.

    Tries in order:
    1. X-Forwarded-For header (first IP if comma-separated)
    2. X-Real-IP header
    3. request.client.host
    """
    try:
        # Check X-Forwarded-For (used by proxies/load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP if comma-separated list
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        # Check X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        if request.client:
            return request.client.host
    except Exception:  # Catch any unexpected errors
        pass

    return None


def build_event_log(
    ingress: Ingress,
    event: NormalizedEvent,
    status: str,
    error: str | None,
    request_ip: str | None = None,
):
    return EventLog(
        ingress_id=ingress.id,
        source=event.source,
        event=event.event,
        severity=event.severity,
        title=event.title,
        message=event.message,
        tags=event.tags,
        entities=event.entities,
        raw=event.raw,
        request_ip=request_ip,
        delivery_status=status,
        delivery_error=error,
    )


def format_raw_payload(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        try:
            return json.dumps(raw, indent=2, ensure_ascii=False)
        except TypeError:
            return str(raw)
    return str(raw)


def build_template_context(event: EventLog | NormalizedEvent) -> dict[str, Any]:
    timestamp = getattr(event, "timestamp", None)
    if not timestamp and getattr(event, "created_at", None):
        timestamp = event.created_at.isoformat() + "Z"
    return {
        "source": event.source,
        "event": event.event,
        "severity": event.severity,
        "title": event.title,
        "message": event.message,
        "tags": event.tags,
        "entities": event.entities,
        "raw": getattr(event, "raw", None),
        "timestamp": timestamp,
    }


def render_discord_payload_json(
    template: Template, context: dict[str, Any], strict: bool = False
) -> str | None:
    if not template.discord_embed_template:
        return None
    rendered = render_template(template.discord_embed_template, context, strict=strict)
    if not rendered.strip():
        return None
    return rendered


def resolve_template_id(ingress: Ingress, route: Route) -> int | None:
    if ingress.default_template_id:
        return ingress.default_template_id
    return route.template_id


def render_notification_content(
    template: Template,
    context: dict[str, Any],
    raw_payload: Any | None,
    strict: bool = False,
) -> tuple[str | None, str, str | None]:
    rendered_body = render_template(template.body, context, strict=strict)
    rendered_title = None
    if template.title_template:
        rendered_title = render_template(
            template.title_template, context, strict=strict
        )
    if template.show_raw:
        raw = format_raw_payload(raw_payload)
        if raw:
            rendered_body = f"{rendered_body}\n\n```\n{raw}\n```"
    discord_payload_json = render_discord_payload_json(template, context, strict=strict)
    return rendered_title, rendered_body, discord_payload_json
