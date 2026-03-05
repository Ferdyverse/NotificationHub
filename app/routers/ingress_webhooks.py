from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.delivery.base import DeliveryResult
from app.delivery.dispatcher import deliver
from app.models import Ingress, Route, Template
from app.web_shared import (
    _authorize_ingress_request,
    adapt_request_payload,
    build_dedupe_key,
    build_event_log,
    build_template_context,
    enforce_event_log_limit,
    load_default_template,
    log_info,
    maybe_persist_matrix_token,
    render_notification_content,
    resolve_template_id,
    runtime_dedupe,
    runtime_rate,
)

router = APIRouter()


@router.post("/ingest/{slug}")
async def ingest(slug: str, request: Request, db: Session = Depends(get_session)):
    ingress = db.scalar(select(Ingress).where(Ingress.slug == slug))
    if ingress is None or not ingress.is_active:
        raise HTTPException(status_code=404, detail="Ingress not found")

    raw_body = await request.body()
    auth_present, auth_valid = _authorize_ingress_request(ingress, request, raw_body)
    if not auth_present:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing authentication. Provide Authorization bearer token, ?token, "
                "X-Gitlab-Token, or GitHub/Gitea/Forgejo signature header."
            ),
        )
    if not auth_valid:
        raise HTTPException(status_code=403, detail="Invalid token or signature")

    content_type = request.headers.get("content-type", "")
    event = adapt_request_payload(raw_body, content_type, request)

    dedupe_key = build_dedupe_key(ingress, event, request)
    if runtime_dedupe.seen_recently(dedupe_key):
        db.add(build_event_log(ingress, event, "deduped", None))
        db.commit()
        enforce_event_log_limit(db)
        log_info(
            "event_deduped",
            ingress_id=ingress.id,
            source=event.source,
            event=event.event,
        )
        return Response(status_code=204)

    rate_key = f"ingress:{ingress.id}"
    if not runtime_rate.allow(rate_key):
        db.add(build_event_log(ingress, event, "rate_limited", "rate limit exceeded"))
        db.commit()
        enforce_event_log_limit(db)
        log_info("event_rate_limited", ingress_id=ingress.id)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    routes_to_send = [r for r in ingress.routes if r and r.is_active]
    if not routes_to_send:
        db.add(build_event_log(ingress, event, "failed", "No active route"))
        db.commit()
        enforce_event_log_limit(db)
        log_info("event_no_route", ingress_id=ingress.id, source=event.source)
        raise HTTPException(status_code=422, detail="No active route")
    log_info(
        "route_selected",
        ingress_id=ingress.id,
        via="fanout",
        routes=[r.id for r in routes_to_send],
    )

    context = build_template_context(event)
    results: list[tuple[Route, DeliveryResult]] = []
    for route in routes_to_send:
        template_id = resolve_template_id(ingress, route)
        template = db.get(Template, template_id) if template_id else None
        if template is None:
            template = load_default_template(db)
        try:
            rendered_title, rendered, discord_payload_json = (
                render_notification_content(template, context, event.raw)
            )
        except Exception as exc:  # noqa: BLE001
            error_message = f"Template render failed: {exc}"
            log_info(
                "template_render_failed",
                ingress_id=ingress.id,
                route_id=route.id,
                template_id=template.id if template.id else None,
                error=str(exc),
            )
            results.append((route, DeliveryResult(False, "failed", error_message)))
            continue

        extra = {
            "discord_payload_json": discord_payload_json,
        }
        result = deliver(
            route.route_type, route.config, rendered_title or "", rendered, extra=extra
        )
        if result.meta:
            maybe_persist_matrix_token(route, result.meta)
            db.add(route)
            db.commit()
            db.refresh(route)
        results.append((route, result))

    success_count = sum(1 for _, result in results if result.success)
    if success_count == len(results):
        status = "delivered"
        error = None
    elif success_count == 0:
        status = "failed"
        error = "; ".join(
            [f"{route.id}:{result.error}" for route, result in results if result.error]
        )
    else:
        status = "partial"
        error = "; ".join(
            [f"{route.id}:{result.error}" for route, result in results if result.error]
        )

    db.add(build_event_log(ingress, event, status, error))
    db.commit()
    enforce_event_log_limit(db)

    if success_count > 0:
        log_info("event_delivered", ingress_id=ingress.id)
        return Response(status_code=204)

    log_info(
        "event_delivery_failed",
        ingress_id=ingress.id,
        error=error,
    )
    raise HTTPException(status_code=502, detail=error or "Delivery failed")
