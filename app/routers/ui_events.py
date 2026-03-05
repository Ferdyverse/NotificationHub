from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import EventLog, Ingress
from app.security.auth import require_ui_basic_auth
from app.web_shared import (
    DELIVERY_STATUS_OPTIONS,
    EVENTS_PAGE_SIZE,
    EVENT_SEVERITY_OPTIONS,
    normalized_search_filters,
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
