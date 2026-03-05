from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import SessionLocal, engine
from app.delivery.dispatcher import deliver
from app.routers import ingest_router, ui_management_router, ui_operations_router
from app.routers.ingest import favicon, health, ingest, root
from app.routers.ui_operations import (
    ui_backups,
    ui_backups_create,
    ui_backups_download,
    ui_backups_restore,
    ui_backups_upload,
    ui_events,
)
from app.tools.backup import create_backup, restore_backup
from app.web_shared import (
    _authorize_ingress_request,
    ensure_backup_dir_available,
    ensure_defaults,
    resolve_template_id,
)


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

app.include_router(ingest_router)
app.include_router(ui_management_router)
app.include_router(ui_operations_router)

__all__ = [
    "app",
    "root",
    "ingest",
    "favicon",
    "health",
    "ui_events",
    "ui_backups",
    "ui_backups_create",
    "ui_backups_upload",
    "ui_backups_download",
    "ui_backups_restore",
    "_authorize_ingress_request",
    "resolve_template_id",
    "settings",
    "engine",
    "deliver",
    "create_backup",
    "restore_backup",
    "ensure_backup_dir_available",
]
