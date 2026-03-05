from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EventLog
from app.web.state import DELIVERY_STATUS_OPTIONS, EVENT_SEVERITY_OPTIONS


def enforce_event_log_limit(db: Session):
    """Enforce max event log size by deleting oldest events.

    Uses bulk SQL DELETE for better performance instead of ORM delete loop.
    """
    max_events = settings.max_events
    if max_events <= 0:
        return
    total = db.scalar(select(func.count()).select_from(EventLog))
    if total and total > max_events:
        excess = total - max_events
        # Use SQL subquery to delete oldest events in bulk
        # This is much more efficient than fetching and deleting in a loop
        subquery = select(EventLog.id).order_by(EventLog.created_at).limit(excess)
        stmt = delete(EventLog).where(EventLog.id.in_(subquery))
        db.execute(stmt)
        db.commit()


def normalized_search_filters(
    q: str | None,
    ingress_id: int | None,
    delivery_status: str | None,
    source: str | None,
    severity: str | None,
    event: str | None,
) -> tuple[list[Any], dict[str, str]]:
    def _normalize(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    q = _normalize(q)
    delivery_status = _normalize(delivery_status)
    source = _normalize(source)
    severity = _normalize(severity)
    event = _normalize(event)

    if delivery_status and delivery_status not in DELIVERY_STATUS_OPTIONS:
        raise HTTPException(status_code=422, detail="Invalid delivery_status filter")
    if severity and severity not in EVENT_SEVERITY_OPTIONS:
        raise HTTPException(status_code=422, detail="Invalid severity filter")

    filters: list[Any] = []
    if ingress_id is not None:
        filters.append(EventLog.ingress_id == ingress_id)
    if delivery_status:
        filters.append(EventLog.delivery_status == delivery_status)
    if source:
        filters.append(EventLog.source.ilike(f"%{source}%"))
    if severity:
        filters.append(EventLog.severity == severity)
    if event:
        filters.append(EventLog.event.ilike(f"%{event}%"))
    if q:
        search_pattern = f"%{q}%"
        filters.append(
            or_(
                EventLog.title.ilike(search_pattern),
                EventLog.message.ilike(search_pattern),
                EventLog.source.ilike(search_pattern),
                EventLog.event.ilike(search_pattern),
                cast(EventLog.raw, String).ilike(search_pattern),
            )
        )

    selected_filters = {
        "q": q or "",
        "ingress_id": str(ingress_id) if ingress_id is not None else "",
        "delivery_status": delivery_status or "",
        "source": source or "",
        "severity": severity or "",
        "event": event or "",
    }
    return filters, selected_filters
