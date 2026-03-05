from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.web.state import BACKUP_FILENAME_PATTERN


def resolve_backup_dir() -> Path:
    path = Path(settings.backup_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def ensure_backup_dir_available() -> Path:
    backup_dir = resolve_backup_dir()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Backup directory is not writable: {backup_dir}. "
                "Set BACKUP_DIR to a writable path (for example /data/backups or /tmp)."
            ),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Backup directory is not accessible: {backup_dir} ({exc})",
        ) from exc
    return backup_dir


def build_backup_filename() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"notificationhub-{timestamp}.tar.gz"


def list_backup_files(backup_dir: Path) -> list[dict[str, Any]]:
    if not backup_dir.exists():
        return []

    backups: list[dict[str, Any]] = []
    for file_path in backup_dir.iterdir():
        if not file_path.is_file() or not BACKUP_FILENAME_PATTERN.match(file_path.name):
            continue
        stat = file_path.stat()
        backups.append(
            {
                "name": file_path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            }
        )
    backups.sort(key=lambda item: item["modified_at"], reverse=True)
    return backups
