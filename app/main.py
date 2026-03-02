from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import String, cast, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.adapters import generic_json, generic_text, github
from app.adapters.types import NormalizedEvent
from app.config import settings
from app.db import SessionLocal, get_session
from app.delivery.dispatcher import deliver
from app.models import EventLog, Ingress, Route, Template
from app.render.templates import DEFAULT_TEMPLATE_BODY, render_template
from app.runtime import DedupeCache, RateLimiter
from app.security.auth import hash_secret, require_ui_basic_auth, verify_secret
from app.utils import cap_payload


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        ensure_defaults(db)
        yield
    finally:
        db.close()


app = FastAPI(title="NotificationHub", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

templates = Jinja2Templates(directory="app/templates")

runtime_dedupe = DedupeCache(settings.default_dedupe_seconds)
runtime_rate = RateLimiter(settings.default_rate_limit_per_min)

logger = logging.getLogger("formatter")


def log_info(message: str, **fields):
    logger.info("%s %s", message, fields)


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


def build_event_log(
    ingress: Ingress,
    event: NormalizedEvent,
    status: str,
    error: str | None,
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


def render_discord_payload_json(template: Template, context: dict[str, Any]) -> str | None:
    if not template.discord_embed_template:
        return None
    rendered = render_template(template.discord_embed_template, context)
    if not rendered.strip():
        return None
    return rendered


def resolve_template_id(ingress: Ingress, route: Route) -> int | None:
    if ingress.default_template_id:
        return ingress.default_template_id
    return route.template_id


def _extract_signature(header_value: str | None, expected_algo: str) -> str | None:
    if not header_value:
        return None
    parts = header_value.split("=", 1)
    if len(parts) != 2:
        return None
    algo, digest = parts[0].strip().lower(), parts[1].strip()
    if algo != expected_algo or not digest:
        return None
    return digest


def _verify_hmac_signature(body: bytes, secret: str | None, digest: str, algorithm: str) -> bool:
    if not secret:
        return False
    if algorithm == "sha256":
        hasher = hashlib.sha256
    elif algorithm == "sha1":
        hasher = hashlib.sha1
    else:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hasher).hexdigest()
    return hmac.compare_digest(expected, digest)


def _authorize_ingress_request(ingress: Ingress, request: Request, raw_body: bytes) -> tuple[bool, bool]:
    any_auth_present = False
    any_auth_valid = False

    auth_header = request.headers.get("Authorization")
    bearer_token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()
    if not bearer_token:
        bearer_token = request.query_params.get("token")
    if bearer_token:
        any_auth_present = True
        if verify_secret(bearer_token, ingress.secret_hash):
            any_auth_valid = True

    gitlab_token = request.headers.get("X-Gitlab-Token")
    if gitlab_token:
        any_auth_present = True
        if verify_secret(gitlab_token, ingress.secret_hash):
            any_auth_valid = True

    github_sig_256 = _extract_signature(request.headers.get("X-Hub-Signature-256"), "sha256")
    if github_sig_256:
        any_auth_present = True
        if _verify_hmac_signature(raw_body, ingress.secret_value, github_sig_256, "sha256"):
            any_auth_valid = True

    github_sig_sha1 = _extract_signature(request.headers.get("X-Hub-Signature"), "sha1")
    if github_sig_sha1:
        any_auth_present = True
        if _verify_hmac_signature(raw_body, ingress.secret_value, github_sig_sha1, "sha1"):
            any_auth_valid = True

    return any_auth_present, any_auth_valid


def enforce_event_log_limit(db: Session):
    max_events = settings.max_events
    if max_events <= 0:
        return
    total = db.scalar(select(func.count()).select_from(EventLog))
    if total and total > max_events:
        excess = total - max_events
        rows = db.scalars(select(EventLog).order_by(EventLog.created_at).limit(excess)).all()
        for row in rows:
            db.delete(row)
        db.commit()

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/ui/ingresses")


@app.post("/ingest/{slug}")
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
                "X-Gitlab-Token, or GitHub signature header."
            ),
        )
    if not auth_valid:
        raise HTTPException(status_code=403, detail="Invalid token or signature")

    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            payload = json.loads(raw_body)
            github_event = request.headers.get("X-GitHub-Event")
            if github_event:
                event = github.adapt(payload, github_event)
            else:
                event = generic_json.adapt(payload)
        else:
            payload = raw_body.decode("utf-8", errors="replace")
            event = generic_text.adapt(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}") from exc

    event.raw = cap_payload(event.raw, settings.max_raw_payload_chars)

    dedupe_key = DedupeCache.build_key(
        str(ingress.id), event.source, event.event, event.title, event.message
    )
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

    routes_to_send = list(ingress.routes)
    if ingress.default_route and ingress.default_route not in routes_to_send:
        routes_to_send.append(ingress.default_route)
    routes_to_send = [r for r in routes_to_send if r and r.is_active]
    if not routes_to_send:
        db.add(build_event_log(ingress, event, "failed", "No active route"))
        db.commit()
        enforce_event_log_limit(db)
        log_info("event_no_route", ingress_id=ingress.id, source=event.source)
        raise HTTPException(status_code=422, detail="No active route")
    log_info("route_selected", ingress_id=ingress.id, via="fanout", routes=[r.id for r in routes_to_send])

    context = build_template_context(event)
    results = []
    for route in routes_to_send:
        template_id = resolve_template_id(ingress, route)
        template = db.get(Template, template_id) if template_id else None
        if template is None:
            template = load_default_template(db)
        rendered = render_template(template.body, context)
        rendered_title = None
        if template.title_template:
            rendered_title = render_template(template.title_template, context)
        if template.show_raw:
            raw = format_raw_payload(event.raw)
            if raw:
                rendered = f"{rendered}\n\n```\n{raw}\n```"
        extra = {
            "discord_payload_json": render_discord_payload_json(template, context),
        }
        result = deliver(route.route_type, route.config, rendered_title or "", rendered, extra=extra)
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
        error = "; ".join([f"{route.id}:{res.error}" for route, res in results if res.error])
    else:
        status = "partial"
        error = "; ".join([f"{route.id}:{res.error}" for route, res in results if res.error])
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


@app.get("/ui/ingresses", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
async def ui_ingresses(request: Request, db: Session = Depends(get_session)):
    ingresses = db.scalars(select(Ingress).order_by(Ingress.created_at.desc())).all()
    routes = db.scalars(select(Route).where(Route.is_active.is_(True))).all()
    template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
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


@app.post("/ui/ingresses", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
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


@app.post(
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


@app.get(
    "/ui/ingresses/{ingress_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_edit(request: Request, ingress_id: int, db: Session = Depends(get_session)):
    ingress = db.get(Ingress, ingress_id)
    if not ingress:
        raise HTTPException(status_code=404)
    routes = db.scalars(select(Route).where(Route.is_active.is_(True))).all()
    template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "ingress_edit.html",
        {
            "request": request,
            "ingress": ingress,
            "routes": routes,
            "templates": template_list,
            "error": None,
            "flash": flash,
        },
    )


@app.post(
    "/ui/ingresses/{ingress_id}/rotate",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_ingresses_rotate(request: Request, ingress_id: int, db: Session = Depends(get_session)):
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


@app.post(
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
    ingress.default_template_id = int(default_template_id) if default_template_id else None
    routes = db.scalars(select(Route).where(Route.id.in_(route_ids))).all() if route_ids else []
    ingress.routes = routes
    db.commit()
    request.session["flash"] = "Ingress saved."
    return RedirectResponse(f"/ui/ingresses/{ingress.id}", status_code=303)


@app.post(
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


@app.get("/ui/routes", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
async def ui_routes(request: Request, db: Session = Depends(get_session)):
    routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
    template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
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


@app.get(
    "/ui/routes/{route_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_routes_edit(request: Request, route_id: int, db: Session = Depends(get_session)):
    route = db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404)
    template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "route_edit.html",
        {"request": request, "route": route, "templates": template_list, "error": None, "flash": flash},
    )


@app.post("/ui/routes", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
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
    )
    error = validate_route_config(route_type, config)
    if error:
        routes = db.scalars(select(Route).order_by(Route.created_at.desc())).all()
        template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
        return templates.TemplateResponse(
            "routes.html",
            {"request": request, "routes": routes, "templates": template_list, "error": error},
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


@app.post(
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
    )
    error = validate_route_config(route_type, config)
    if error:
        template_list = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
        return templates.TemplateResponse(
            "route_edit.html",
            {"request": request, "route": route, "templates": template_list, "error": error},
            status_code=422,
        )
    route.name = name
    route.route_type = route_type
    route.config = config
    route.template_id = int(template_id) if template_id else None
    db.commit()
    request.session["flash"] = "Route saved."
    return RedirectResponse(f"/ui/routes/{route.id}", status_code=303)


@app.post(
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


@app.post(
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


@app.get("/ui/templates", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
async def ui_templates(request: Request, db: Session = Depends(get_session)):
    items = db.scalars(select(Template).order_by(Template.created_at.desc())).all()
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        "templates.html", {"request": request, "templates": items, "flash": flash}
    )


@app.post("/ui/templates", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
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


@app.get(
    "/ui/templates/{template_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_edit(request: Request, template_id: int, db: Session = Depends(get_session)):
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


@app.post(
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


@app.get(
    "/ui/templates/{template_id}/preview",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_preview(request: Request, template_id: int, db: Session = Depends(get_session)):
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
        rendered = render_template(template.body, context, strict=False)
        if template.title_template:
            rendered_title = render_template(template.title_template, context, strict=False)
        rendered_discord_payload_json = render_discord_payload_json(template, context)
        if template.show_raw:
            raw = format_raw_payload(event.raw) if event else None
            if raw:
                rendered = f"{rendered}\n\n```\n{raw}\n```"
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


@app.post(
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
    rendered = render_template(template.body, context)
    rendered_title = None
    if template.title_template:
        rendered_title = render_template(template.title_template, context)
    if template.show_raw:
        raw = format_raw_payload(event.raw)
        if raw:
            rendered = f"{rendered}\n\n```\n{raw}\n```"
    extra = {
        "discord_payload_json": render_discord_payload_json(template, context),
    }
    result = deliver(route.route_type, route.config, rendered_title or "", rendered, extra=extra)
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


@app.post(
    "/ui/templates/{template_id}/delete",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_templates_delete(request: Request, template_id: int, db: Session = Depends(get_session)):
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


@app.post(
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


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ui/events", response_class=HTMLResponse, dependencies=[Depends(require_ui_basic_auth)])
async def ui_events(
    request: Request,
    q: str | None = None,
    ingress_id: str | None = None,
    delivery_status: str | None = None,
    db: Session = Depends(get_session),
):
    query = select(EventLog).order_by(EventLog.created_at.desc())
    if ingress_id:
        query = query.where(EventLog.ingress_id == int(ingress_id))
    if delivery_status:
        query = query.where(EventLog.delivery_status == delivery_status)
    if q:
        query = query.where(cast(EventLog.raw, String).ilike(f"%{q}%"))
    logs = db.scalars(query.limit(200)).all()
    ingresses = db.scalars(select(Ingress)).all()
    return templates.TemplateResponse(
        "events.html",
        {"request": request, "logs": logs, "ingresses": ingresses},
    )
