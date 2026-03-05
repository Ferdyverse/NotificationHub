from __future__ import annotations

from fastapi import APIRouter

from app.routers.ui_ingresses import (
    router as ui_ingresses_router,
    ui_ingresses,
    ui_ingresses_create,
    ui_ingresses_delete,
    ui_ingresses_edit,
    ui_ingresses_rotate,
    ui_ingresses_toggle,
    ui_ingresses_update,
)
from app.routers.ui_routes import (
    router as ui_routes_router,
    ui_routes,
    ui_routes_create,
    ui_routes_delete,
    ui_routes_edit,
    ui_routes_toggle,
    ui_routes_update,
)
from app.routers.ui_templates import (
    router as ui_templates_router,
    ui_templates,
    ui_templates_create,
    ui_templates_delete,
    ui_templates_edit,
    ui_templates_preview,
    ui_templates_sample,
    ui_templates_test_send,
    ui_templates_update,
)

router = APIRouter()
router.include_router(ui_ingresses_router)
router.include_router(ui_routes_router)
router.include_router(ui_templates_router)

__all__ = [
    "router",
    "ui_ingresses",
    "ui_ingresses_create",
    "ui_ingresses_toggle",
    "ui_ingresses_edit",
    "ui_ingresses_rotate",
    "ui_ingresses_update",
    "ui_ingresses_delete",
    "ui_routes",
    "ui_routes_edit",
    "ui_routes_create",
    "ui_routes_update",
    "ui_routes_toggle",
    "ui_routes_delete",
    "ui_templates",
    "ui_templates_create",
    "ui_templates_edit",
    "ui_templates_update",
    "ui_templates_preview",
    "ui_templates_test_send",
    "ui_templates_delete",
    "ui_templates_sample",
]
