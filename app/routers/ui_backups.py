from __future__ import annotations

import shutil
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.db import engine
from app.security.auth import require_ui_basic_auth
from app.tools.backup import create_backup, restore_backup
from app.web_shared import (
    BACKUP_FILENAME_PATTERN,
    build_backup_filename,
    ensure_backup_dir_available,
    list_backup_files,
    resolve_backup_dir,
    settings,
    templates,
)

router = APIRouter()


@router.get(
    "/ui/backups",
    response_class=HTMLResponse,
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_backups(
    request: Request,
    created: str | None = None,
    uploaded: str | None = None,
    restored: str | None = None,
):
    backup_dir = resolve_backup_dir()
    try:
        backups = list_backup_files(backup_dir)
    except PermissionError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Backup directory is not readable: {backup_dir}. "
                "Set BACKUP_DIR to a readable path."
            ),
        ) from exc
    created_name = (
        created if created and BACKUP_FILENAME_PATTERN.match(created) else None
    )
    uploaded_name = (
        uploaded if uploaded and BACKUP_FILENAME_PATTERN.match(uploaded) else None
    )
    restored_name = (
        restored if restored and BACKUP_FILENAME_PATTERN.match(restored) else None
    )
    return templates.TemplateResponse(
        "backups.html",
        {
            "request": request,
            "backups": backups,
            "created": created_name,
            "uploaded": uploaded_name,
            "restored": restored_name,
            "backup_dir": str(backup_dir),
        },
    )


@router.post(
    "/ui/backups/create",
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_backups_create(
    filename: str | None = Form(default=None),
):
    name = filename.strip() if filename else ""
    if not name:
        name = build_backup_filename()
    if not BACKUP_FILENAME_PATTERN.match(name):
        raise HTTPException(
            status_code=422,
            detail="Filename must end with .tar.gz and only use letters, numbers, dot, dash or underscore.",
        )

    backup_dir = ensure_backup_dir_available()
    backup_path = (backup_dir / name).resolve()
    if not backup_path.is_relative_to(backup_dir):
        raise HTTPException(status_code=400, detail="Invalid backup target path")
    if backup_path.exists():
        raise HTTPException(status_code=409, detail="Backup file already exists")

    try:
        create_backup(settings.database_url, backup_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RedirectResponse(f"/ui/backups?created={name}", status_code=303)


@router.post(
    "/ui/backups/upload",
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_backups_upload(
    upload: UploadFile = File(...),
):
    raw_name = (upload.filename or "").strip()
    if not raw_name:
        raise HTTPException(status_code=422, detail="Please select a backup file")
    if Path(raw_name).name != raw_name:
        raise HTTPException(status_code=422, detail="Invalid backup filename")
    if not BACKUP_FILENAME_PATTERN.match(raw_name):
        raise HTTPException(
            status_code=422,
            detail="Filename must end with .tar.gz and only use letters, numbers, dot, dash or underscore.",
        )

    backup_dir = ensure_backup_dir_available()
    backup_path = (backup_dir / raw_name).resolve()
    if not backup_path.is_relative_to(backup_dir):
        raise HTTPException(status_code=400, detail="Invalid backup target path")
    if backup_path.exists():
        raise HTTPException(status_code=409, detail="Backup file already exists")

    try:
        with backup_path.open("wb") as target:
            shutil.copyfileobj(upload.file, target)
    finally:
        upload.file.close()

    if backup_path.stat().st_size <= 0:
        backup_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded backup file is empty")

    return RedirectResponse(f"/ui/backups?uploaded={raw_name}", status_code=303)


@router.get(
    "/ui/backups/{filename}",
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_backups_download(filename: str):
    if not BACKUP_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=404, detail="Backup file not found")

    backup_dir = resolve_backup_dir()
    backup_path = (backup_dir / filename).resolve()
    if not backup_path.is_relative_to(backup_dir) or not backup_path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(
        path=backup_path,
        media_type="application/gzip",
        filename=backup_path.name,
    )


@router.post(
    "/ui/backups/{filename}/restore",
    dependencies=[Depends(require_ui_basic_auth)],
)
async def ui_backups_restore(filename: str):
    if not BACKUP_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=404, detail="Backup file not found")

    backup_dir = resolve_backup_dir()
    backup_path = (backup_dir / filename).resolve()
    if not backup_path.is_relative_to(backup_dir) or not backup_path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")

    engine.dispose()
    try:
        restore_backup(settings.database_url, backup_path, force=True)
    except (FileNotFoundError, ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Backup restored but schema migration failed: {exc}",
        ) from exc
    finally:
        engine.dispose()

    return RedirectResponse(f"/ui/backups?restored={filename}", status_code=303)
