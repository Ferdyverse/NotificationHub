from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import EventLog, Ingress, Route
from app.security.auth import require_ui_basic_auth
from app.web_shared import templates

router = APIRouter()


@router.get(
    "/ui/dashboard",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_dashboard(request: Request, db: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    total_events = int(db.scalar(select(func.count()).select_from(EventLog)) or 0)
    events_24h = int(
        db.scalar(
            select(func.count()).select_from(EventLog).where(EventLog.created_at >= cutoff_24h)
        )
        or 0
    )
    events_7d = int(
        db.scalar(
            select(func.count()).select_from(EventLog).where(EventLog.created_at >= cutoff_7d)
        )
        or 0
    )

    status_rows = db.execute(
        select(EventLog.delivery_status, func.count()).group_by(EventLog.delivery_status)
    ).all()
    by_status = {row[0]: row[1] for row in status_rows}

    severity_rows = db.execute(
        select(EventLog.severity, func.count()).group_by(EventLog.severity)
    ).all()
    by_severity = {row[0]: row[1] for row in severity_rows}

    total_ingresses = int(db.scalar(select(func.count()).select_from(Ingress)) or 0)
    active_ingresses = int(
        db.scalar(
            select(func.count()).select_from(Ingress).where(Ingress.is_active.is_(True))
        )
        or 0
    )
    total_routes = int(db.scalar(select(func.count()).select_from(Route)) or 0)
    active_routes = int(
        db.scalar(select(func.count()).select_from(Route).where(Route.is_active.is_(True)))
        or 0
    )

    recent_events = db.scalars(
        select(EventLog)
        .options(selectinload(EventLog.ingress))
        .order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .limit(10)
    ).all()

    delivered = by_status.get("delivered", 0)
    success_rate = round(delivered / total_events * 100) if total_events > 0 else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_events": total_events,
            "events_24h": events_24h,
            "events_7d": events_7d,
            "by_status": by_status,
            "by_severity": by_severity,
            "total_ingresses": total_ingresses,
            "active_ingresses": active_ingresses,
            "total_routes": total_routes,
            "active_routes": active_routes,
            "recent_events": recent_events,
            "success_rate": success_rate,
        },
    )
