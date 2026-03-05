from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.types import NormalizedEvent
from app.db import get_session
from app.delivery.dispatcher import deliver
from app.models import EventLog, Ingress, Route, Template
from app.security.auth import require_ui_basic_auth
from app.web_shared import (
    build_event_log,
    build_template_context,
    enforce_event_log_limit,
    maybe_persist_matrix_token,
    render_notification_content,
    templates,
)

router = APIRouter()


@router.get(
    "/ui/templates",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates(request: Request, db: Session = Depends(get_session)):
    items = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "templates.html", {"request": request, "templates": items, "flash": flash}
    )


@router.post(
    "/ui/templates",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_create(
    request: Request,
    name: str = Form(...),
    title_template: str = Form(""),
    body: str = Form(...),
    discord_embed_template: str = Form(""),
    show_raw: bool | None = Form(False),
    is_default: bool | None = Form(False),
    db: Session = Depends(get_session),
):
    if is_default:
        db.query(Template).update({Template.is_default: False})
    template = Template(
        name=name,
        title_template=title_template or None,
        body=body,
        discord_embed_template=discord_embed_template or None,
        show_raw=bool(show_raw),
        is_default=bool(is_default),
    )
    db.add(template)
    db.commit()
    request.session["flash"] = "Template saved."
    return RedirectResponse(f"/ui/templates/{template.id}", status_code=303)


@router.get(
    "/ui/templates/{template_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_edit(
    request: Request, template_id: int, db: Session = Depends(get_session)
):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404)
    routes = db.scalars(select(Route)).all()
    ingresses = db.scalars(select(Ingress)).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "template_edit.html",
        {
            "request": request,
            "template": template,
            "routes": routes,
            "ingresses": ingresses,
            "error": None,
            "default_title": "",
            "flash": flash,
        },
    )


@router.post(
    "/ui/templates/{template_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_update(
    request: Request,
    template_id: int,
    name: str = Form(...),
    title_template: str = Form(""),
    body: str = Form(...),
    discord_embed_template: str = Form(""),
    show_raw: bool | None = Form(False),
    is_default: bool | None = Form(False),
    db: Session = Depends(get_session),
):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404)
    if is_default:
        db.query(Template).update({Template.is_default: False})
    template.name = name
    template.title_template = title_template or None
    template.body = body
    template.discord_embed_template = discord_embed_template or None
    template.show_raw = bool(show_raw)
    template.is_default = bool(is_default)
    db.commit()
    request.session["flash"] = "Template saved."
    return RedirectResponse(f"/ui/templates/{template.id}", status_code=303)


@router.get(
    "/ui/templates/{template_id}/preview",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_preview(
    request: Request, template_id: int, db: Session = Depends(get_session)
):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404)
    event = db.scalar(select(EventLog).order_by(EventLog.created_at.desc()))
    if event:
        context = build_template_context(event)
    else:
        context = {
            "source": "generic",
            "event": "sample.event",
            "severity": "info",
            "title": "Sample Event",
            "message": "This is a preview sample.",
            "tags": ["demo"],
            "entities": {"service": "demo"},
            "timestamp": "2024-01-01T00:00:00Z",
        }
    rendered = None
    rendered_title = None
    rendered_discord_payload_json = None
    error = None
    try:
        rendered_title, rendered, rendered_discord_payload_json = (
            render_notification_content(
                template, context, event.raw if event else None, strict=False
            )
        )
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    return templates.TemplateResponse(
        "template_preview.html",
        {
            "request": request,
            "template": template,
            "rendered": rendered,
            "rendered_title": rendered_title,
            "rendered_discord_payload_json": rendered_discord_payload_json,
            "error": error,
        },
    )


@router.post(
    "/ui/templates/{template_id}/test-send",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_test_send(
    request: Request,
    template_id: int,
    route_id: int = Form(...),
    db: Session = Depends(get_session),
):
    template = db.get(Template, template_id)
    route = db.get(Route, route_id)
    if not template or not route:
        raise HTTPException(status_code=404)
    event = db.scalar(select(EventLog).order_by(EventLog.created_at.desc()))
    if not event:
        routes = db.scalars(select(Route)).all()
        ingresses = db.scalars(select(Ingress)).all()
        return templates.TemplateResponse(
            "template_edit.html",
            {
                "request": request,
                "template": template,
                "routes": routes,
                "ingresses": ingresses,
                "error": "No events available for preview. Send a webhook first.",
                "default_title": "",
                "flash": None,
            },
            status_code=422,
        )
    context = build_template_context(event)
    rendered_title, rendered, discord_payload_json = render_notification_content(
        template, context, event.raw
    )
    extra = {
        "discord_payload_json": discord_payload_json,
    }
    result = deliver(
        route.route_type, route.config, rendered_title or "", rendered, extra=extra
    )
    if not result.success:
        routes = db.scalars(select(Route)).all()
        ingresses = db.scalars(select(Ingress)).all()
        return templates.TemplateResponse(
            "template_edit.html",
            {
                "request": request,
                "template": template,
                "routes": routes,
                "ingresses": ingresses,
                "error": result.error or "Delivery failed",
                "default_title": "",
                "flash": None,
            },
            status_code=502,
        )
    if result.meta:
        maybe_persist_matrix_token(route, result.meta)
        db.commit()
    return RedirectResponse(f"/ui/templates/{template.id}", status_code=303)


@router.post(
    "/ui/templates/{template_id}/duplicate",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_duplicate(
    request: Request, template_id: int, db: Session = Depends(get_session)
):
    tmpl = db.get(Template, template_id)
    if not tmpl:
        raise HTTPException(status_code=404)
    copy = Template(
        name=f"{tmpl.name} (Copy)",
        title_template=tmpl.title_template,
        body=tmpl.body,
        discord_embed_template=tmpl.discord_embed_template,
        show_raw=tmpl.show_raw,
        is_default=False,
    )
    db.add(copy)
    db.commit()
    request.session["flash"] = f"Duplicate of '{tmpl.name}' created."
    return RedirectResponse("/ui/templates", status_code=303)


@router.post(
    "/ui/templates/{template_id}/delete",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_delete(
    request: Request, template_id: int, db: Session = Depends(get_session)
):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404)
    if template.is_default:
        request.session["flash"] = "Cannot delete default template."
        return RedirectResponse("/ui/templates", status_code=303)
    db.delete(template)
    db.commit()
    request.session["flash"] = "Template deleted."
    return RedirectResponse("/ui/templates", status_code=303)


@router.post(
    "/ui/templates/{template_id}/sample",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_sample(
    request: Request,
    template_id: int,
    ingress_id: int = Form(...),
    db: Session = Depends(get_session),
):
    template = db.get(Template, template_id)
    ingress = db.get(Ingress, ingress_id)
    if not template or not ingress:
        raise HTTPException(status_code=404)

    sample_event = NormalizedEvent(
        source="generic",
        event="sample.event",
        severity="info",
        title="Sample Event",
        message="This is a sample event created from the UI.",
        tags=["sample", "ui"],
        entities={"service": "formatter-hub"},
        raw={"sample": True},
    ).with_timestamp()

    db.add(build_event_log(ingress, sample_event, "sample", None))
    db.commit()
    enforce_event_log_limit(db)
    return RedirectResponse(f"/ui/templates/{template.id}", status_code=303)
