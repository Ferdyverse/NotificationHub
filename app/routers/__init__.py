from app.routers.ingest import router as ingest_router
from app.routers.ui_management import router as ui_management_router
from app.routers.ui_operations import router as ui_operations_router

__all__ = [
    "ingest_router",
    "ui_management_router",
    "ui_operations_router",
]
