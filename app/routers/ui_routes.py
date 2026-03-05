from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Route, Template
from app.security.auth import require_ui_basic_auth
from app.web_shared import build_route_config, templates, validate_route_config

router = APIRouter()


@router.get(
    "/ui/routes",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes(request: Request, db: Session = Depends(get_session)):
    routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
    template_list = db.scalars(
        select(Template).order_by(Template.created_at.desc())
    ).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "routes.html",
        {
            "request": request,
            "routes": routes,
            "templates": template_list,
            "error": None,
            "flash": flash,
        },
    )


@router.get(
    "/ui/routes/{route_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_edit(
    request: Request, route_id: int, db: Session = Depends(get_session)
):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404)
    template_list = db.scalars(
        select(Template).order_by(Template.created_at.desc())
    ).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "route_edit.html",
        {
            "request": request,
            "route": route,
            "templates": template_list,
            "error": None,
            "flash": flash,
        },
    )


@router.post(
    "/ui/routes",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_create(
    request: Request,
    name: str = Form(...),
    route_type: str = Form(...),
    template_id: str | None = Form(None),
    matrix_homeserver: str | None = Form(None),
    matrix_room_id: str | None = Form(None),
    matrix_username: str | None = Form(None),
    matrix_password: str | None = Form(None),
    matrix_markdown: str | None = Form(None),
    matrix_auto_join: str | None = Form(None),
    matrix_bearer_token: str | None = Form(None),
    discord_webhook_url: str | None = Form(None),
    discord_bearer_token: str | None = Form(None),
    discord_use_embed: str | None = Form(None),
    discord_embed_color: str | None = Form(None),
    email_smtp_host: str | None = Form(None),
    email_smtp_port: str | None = Form(None),
    email_smtp_tls: str | None = Form(None),
    email_smtp_starttls: str | None = Form(None),
    email_smtp_username: str | None = Form(None),
    email_smtp_password: str | None = Form(None),
    email_from_addr: str | None = Form(None),
    email_to_addrs: str | None = Form(None),
    email_subject_prefix: str | None = Form(None),
    telegram_bot_token: str | None = Form(None),
    telegram_chat_id: str | None = Form(None),
    telegram_parse_mode: str | None = Form(None),
    telegram_disable_web_page_preview: str | None = Form(None),
    db: Session = Depends(get_session),
):
    config = build_route_config(
        route_type,
        matrix_homeserver,
        matrix_room_id,
        matrix_username,
        matrix_password,
        matrix_markdown,
        matrix_auto_join,
        matrix_bearer_token,
        discord_webhook_url,
        discord_bearer_token,
        discord_use_embed,
        discord_embed_color,
        email_smtp_host,
        email_smtp_port,
        email_smtp_tls,
        email_smtp_starttls,
        email_smtp_username,
        email_smtp_password,
        email_from_addr,
        email_to_addrs,
        email_subject_prefix,
        telegram_bot_token,
        telegram_chat_id,
        telegram_parse_mode,
        telegram_disable_web_page_preview,
    )
    error = validate_route_config(route_type, config)
    if error:
        routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
        template_list = db.scalars(
            select(Template).order_by(Template.created_at.desc())
        ).all()
        return templates.TemplateResponse(
            "routes.html",
            {
                "request": request,
                "routes": routes,
                "templates": template_list,
                "error": error,
            },
            status_code=422,
        )
    route = Route(
        name=name,
        route_type=route_type,
        config=config,
        template_id=int(template_id) if template_id else None,
    )
    db.add(route)
    db.commit()
    request.session["flash"] = "Route saved."
    return RedirectResponse("/ui/routes", status_code=303)


@router.post(
    "/ui/routes/{route_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_update(
    request: Request,
    route_id: int,
    name: str = Form(...),
    route_type: str = Form(...),
    template_id: str | None = Form(None),
    matrix_homeserver: str | None = Form(None),
    matrix_room_id: str | None = Form(None),
    matrix_username: str | None = Form(None),
    matrix_password: str | None = Form(None),
    matrix_markdown: str | None = Form(None),
    matrix_auto_join: str | None = Form(None),
    matrix_bearer_token: str | None = Form(None),
    discord_webhook_url: str | None = Form(None),
    discord_bearer_token: str | None = Form(None),
    discord_use_embed: str | None = Form(None),
    discord_embed_color: str | None = Form(None),
    email_smtp_host: str | None = Form(None),
    email_smtp_port: str | None = Form(None),
    email_smtp_tls: str | None = Form(None),
    email_smtp_starttls: str | None = Form(None),
    email_smtp_username: str | None = Form(None),
    email_smtp_password: str | None = Form(None),
    email_from_addr: str | None = Form(None),
    email_to_addrs: str | None = Form(None),
    email_subject_prefix: str | None = Form(None),
    telegram_bot_token: str | None = Form(None),
    telegram_chat_id: str | None = Form(None),
    telegram_parse_mode: str | None = Form(None),
    telegram_disable_web_page_preview: str | None = Form(None),
    db: Session = Depends(get_session),
):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404)
    config = build_route_config(
        route_type,
        matrix_homeserver,
        matrix_room_id,
        matrix_username,
        matrix_password,
        matrix_markdown,
        matrix_auto_join,
        matrix_bearer_token,
        discord_webhook_url,
        discord_bearer_token,
        discord_use_embed,
        discord_embed_color,
        email_smtp_host,
        email_smtp_port,
        email_smtp_tls,
        email_smtp_starttls,
        email_smtp_username,
        email_smtp_password,
        email_from_addr,
        email_to_addrs,
        email_subject_prefix,
        telegram_bot_token,
        telegram_chat_id,
        telegram_parse_mode,
        telegram_disable_web_page_preview,
    )
    error = validate_route_config(route_type, config)
    if error:
        template_list = db.scalars(
            select(Template).order_by(Template.created_at.desc())
        ).all()
        return templates.TemplateResponse(
            "route_edit.html",
            {
                "request": request,
                "route": route,
                "templates": template_list,
                "error": error,
            },
            status_code=422,
        )
    route.name = name
    route.route_type = route_type
    route.config = config
    route.template_id = int(template_id) if template_id else None
    db.commit()
    request.session["flash"] = "Route saved."
    return RedirectResponse(f"/ui/routes/{route.id}", status_code=303)


@router.post(
    "/ui/routes/{route_id}/toggle",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_toggle(route_id: int, db: Session = Depends(get_session)):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404)
    route.is_active = not route.is_active
    db.commit()
    return RedirectResponse("/ui/routes", status_code=303)


@router.post(
    "/ui/routes/{route_id}/delete",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_delete(route_id: int, db: Session = Depends(get_session)):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404)
    db.delete(route)
    db.commit()
    return RedirectResponse("/ui/routes", status_code=303)
