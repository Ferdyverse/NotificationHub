from __future__ import annotations

from fastapi import APIRouter

from app.routers.ingress_webhooks import ingest, router as ingress_webhooks_router
from app.routers.system import favicon, health, root, router as system_router

router = APIRouter()
router.include_router(system_router)
router.include_router(ingress_webhooks_router)

__all__ = ["router", "root", "ingest", "favicon", "health"]
