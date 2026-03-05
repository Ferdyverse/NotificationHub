from __future__ import annotations

from fastapi import APIRouter

from app.routers.ui_backups import (
    router as ui_backups_router,
    ui_backups,
    ui_backups_create,
    ui_backups_download,
    ui_backups_restore,
    ui_backups_upload,
)
from app.routers.ui_events import router as ui_events_router, ui_events

router = APIRouter()
router.include_router(ui_events_router)
router.include_router(ui_backups_router)

__all__ = [
    "router",
    "ui_events",
    "ui_backups",
    "ui_backups_create",
    "ui_backups_upload",
    "ui_backups_download",
    "ui_backups_restore",
]
