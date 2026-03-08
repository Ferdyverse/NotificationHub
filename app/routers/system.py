from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/")
async def root():
    return RedirectResponse("/ui/dashboard")


@router.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@router.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
    return Response(status_code=204)


@router.get("/health")
async def health():
    return {"status": "ok"}
