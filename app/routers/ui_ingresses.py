from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import Ingress, Route, Template
from app.security.auth import hash_secret, require_ui_basic_auth
from app.web_shared import templates

router = APIRouter()


@router.get(
    "/ui/ingresses",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses(request: Request, db: Session = Depends(get_session)):
    ingresses = db.scalars(select(Ingress).order_by(Ingress.created_at.desc())).all()
    routes = db.scalars(select(Route).where(Route.is_active.is_(True))).all()
    template_list = db.scalars(
        select(Template).order_by(Template.created_at.desc())
    ).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "ingresses.html",
        {
            "request": request,
            "ingresses": ingresses,
            "routes": routes,
            "templates": template_list,
            "flash": flash,
        },
    )


@router.post(
    "/ui/ingresses",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_create(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    route_ids: list[int] = Form([]),
    default_template_id: str | None = Form(None),
    db: Session = Depends(get_session),
):
    secret = secrets.token_urlsafe(24)
    ingress = Ingress(
        name=name,
        slug=slug,
        secret_hash=hash_secret(secret),
        secret_value=secret,
        default_template_id=int(default_template_id) if default_template_id else None,
    )
    if route_ids:
        routes = db.scalars(select(Route).where(Route.id.in_(route_ids))).all()
        ingress.routes = routes
    db.add(ingress)
    db.commit()
    request.session["flash"] = "Ingress created. Copy the secret now."
    return templates.TemplateResponse(
        "secret.html",
        {"request": request, "secret": secret, "label": f"Ingress {slug}"},
    )


@router.post(
    "/ui/ingresses/{ingress_id}/toggle",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_toggle(
    request: Request, ingress_id: int, db: Session = Depends(get_session)
):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    ingress.is_active = not ingress.is_active
    db.commit()
    request.session["flash"] = "Ingress updated."
    return RedirectResponse("/ui/ingresses", status_code=303)


@router.get(
    "/ui/ingresses/{ingress_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_edit(
    request: Request, ingress_id: int, db: Session = Depends(get_session)
):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    routes = db.scalars(select(Route).where(Route.is_active.is_(True))).all()
    template_list = db.scalars(
        select(Template).order_by(Template.created_at.desc())
    ).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "ingress_edit.html",
        {
            "request": request,
            "base_url": settings.base_url.rstrip("/") + "/",
            "ingress": ingress,
            "routes": routes,
            "templates": template_list,
            "error": None,
            "flash": flash,
        },
    )


@router.post(
    "/ui/ingresses/{ingress_id}/rotate",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_rotate(
    request: Request, ingress_id: int, db: Session = Depends(get_session)
):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    secret = secrets.token_urlsafe(24)
    ingress.secret_hash = hash_secret(secret)
    ingress.secret_value = secret
    db.commit()
    request.session["flash"] = "Ingress secret rotated. Copy the secret now."
    return templates.TemplateResponse(
        "secret.html",
        {"request": request, "secret": secret, "label": f"Ingress {ingress.slug}"},
    )


@router.post(
    "/ui/ingresses/{ingress_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_update(
    request: Request,
    ingress_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    route_ids: list[int] = Form([]),
    default_template_id: str | None = Form(None),
    db: Session = Depends(get_session),
):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    ingress.name = name
    ingress.slug = slug
    ingress.default_template_id = (
        int(default_template_id) if default_template_id else None
    )
    routes = (
        db.scalars(select(Route).where(Route.id.in_(route_ids))).all()
        if route_ids
        else []
    )
    ingress.routes = routes
    db.commit()
    request.session["flash"] = "Ingress saved."
    return RedirectResponse(f"/ui/ingresses/{ingress.id}", status_code=303)


@router.post(
    "/ui/ingresses/{ingress_id}/delete",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_delete(
    request: Request, ingress_id: int, db: Session = Depends(get_session)
):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    db.delete(ingress)
    db.commit()
    request.session["flash"] = "Ingress deleted."
    return RedirectResponse("/ui/ingresses", status_code=303)
