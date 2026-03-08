from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.delivery.base import DeliveryResult
from app.delivery.dispatcher import deliver
from app.models import EventLog, Ingress, Template
from app.security.auth import require_ui_basic_auth
from app.web_shared import (
    DELIVERY_STATUS_OPTIONS,
    EVENTS_PAGE_SIZE,
    EVENT_SEVERITY_OPTIONS,
    enforce_event_log_limit,
    load_default_template,
    maybe_persist_matrix_token,
    normalized_search_filters,
    render_notification_content,
    resolve_template_id,
    build_template_context,
    templates,
)

router = APIRouter()


@router.get(
    "/ui/events",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_events(
    request: Request,
    q: str | None = None,
    ingress_id: int | None = Query(default=None, ge=1),
    delivery_status: str | None = None,
    source: str | None = None,
    severity: str | None = None,
    event: str | None = None,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_session),
):
    filters, selected_filters = normalized_search_filters(
        q=q,
        ingress_id=ingress_id,
        delivery_status=delivery_status,
        source=source,
        severity=severity,
        event=event,
    )

    count_query = select(func.count()).select_from(EventLog)
    if filters:
        count_query = count_query.where(*filters)
    total = int(db.scalar(count_query) or 0)
    total_pages = max((total - 1) // EVENTS_PAGE_SIZE + 1, 1)
    if total > 0 and page > total_pages:
        page = total_pages

    offset = (page - 1) * EVENTS_PAGE_SIZE
    query = (
        select(EventLog)
        .options(selectinload(EventLog.ingress))
        .order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .offset(offset)
        .limit(EVENTS_PAGE_SIZE)
    )
    if filters:
        query = query.where(*filters)

    logs = db.scalars(query).all()
    ingresses = db.scalars(select(Ingress).order_by(Ingress.name.asc())).all()
    start_index = offset + 1 if total > 0 else 0
    end_index = offset + len(logs)
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "logs": logs,
            "ingresses": ingresses,
            "delivery_status_options": DELIVERY_STATUS_OPTIONS,
            "severity_options": EVENT_SEVERITY_OPTIONS,
            "filters": selected_filters,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "start_index": start_index,
            "end_index": end_index,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    )


@router.post(
    "/ui/events/{event_id}/resend",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_event_resend(
    event_id: int,
    request: Request,
    db: Session = Depends(get_session),
):
    log = db.get(EventLog, event_id)
    if not log:
        raise HTTPException(status_code=404, detail="Event not found")

    ingress = db.scalar(
        select(Ingress)
        .options(selectinload(Ingress.routes))
        .where(Ingress.id == log.ingress_id)
    )
    if not ingress:
        return HTMLResponse(
            '<div class="alert alert-error"><span class="alert-icon">❌</span> Ingress no longer exists.</div>'
        )

    routes_to_send = [r for r in ingress.routes if r and r.is_active]
    if not routes_to_send:
        return HTMLResponse(
            '<div class="alert alert-warning"><span class="alert-icon">⚠️</span> No active destinations for this ingress.</div>'
        )

    context = build_template_context(log)
    results: list[tuple[object, DeliveryResult]] = []
    for route in routes_to_send:
        template_id = resolve_template_id(ingress, route)
        template = db.get(Template, template_id) if template_id else None
        if template is None:
            template = load_default_template(db)
        try:
            rendered_title, rendered, discord_payload_json = render_notification_content(
                template, context, log.raw
            )
        except Exception as exc:  # noqa: BLE001
            results.append((route, DeliveryResult(False, "failed", f"Template render failed: {exc}")))
            continue

        result = deliver(
            route.route_type,
            route.config,
            rendered_title or "",
            rendered,
            extra={"discord_payload_json": discord_payload_json},
        )
        if result.meta:
            maybe_persist_matrix_token(route, result.meta)
            db.add(route)
            db.commit()
            db.refresh(route)
        results.append((route, result))

    success_count = sum(1 for _, r in results if r.success)
    if success_count == len(results):
        status = "delivered"
        error = None
    elif success_count == 0:
        status = "failed"
        error = "; ".join(
            [f"{route.name}: {r.error}" for route, r in results if r.error]
        )
    else:
        status = "partial"
        error = "; ".join(
            [f"{route.name}: {r.error}" for route, r in results if r.error]
        )

    new_log = EventLog(
        ingress_id=log.ingress_id,
        source=log.source,
        event=log.event,
        severity=log.severity,
        title=log.title,
        message=log.message,
        tags=log.tags,
        entities=log.entities,
        raw=log.raw,
        request_ip=None,
        delivery_status=status,
        delivery_error=error,
    )
    db.add(new_log)
    db.commit()
    enforce_event_log_limit(db)

    if success_count > 0:
        return HTMLResponse(
            f'<div class="alert alert-success"><span class="alert-icon">✅</span>'
            f" Resent to {success_count}/{len(results)} destination(s).</div>"
        )
    return HTMLResponse(
        f'<div class="alert alert-error"><span class="alert-icon">❌</span>'
        f" Resend failed: {error}</div>"
    )
