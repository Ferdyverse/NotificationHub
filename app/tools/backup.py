from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings

BACKUP_SCHEMA_VERSION = 1
BACKUP_DB_FILENAME = "app.db"
BACKUP_META_FILENAME = "metadata.json"


def resolve_sqlite_db_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// URLs are supported for backup/restore")

    raw = database_url[len(prefix) :].split("?", 1)[0]
    if not raw or raw == ":memory:":
        raise ValueError("A file-based SQLite database is required")

    db_path = Path(raw)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    return db_path.resolve()


def _snapshot_sqlite(db_path: Path, snapshot_path: Path) -> None:
    source = sqlite3.connect(str(db_path))
    try:
        target = sqlite3.connect(str(snapshot_path))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(database_url: str, output_path: Path) -> Path:
    db_path = resolve_sqlite_db_path(database_url)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="nhub-backup-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        snapshot_path = tmp_root / BACKUP_DB_FILENAME
        metadata_path = tmp_root / BACKUP_META_FILENAME

        _snapshot_sqlite(db_path, snapshot_path)

        metadata: dict[str, Any] = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "database_filename": BACKUP_DB_FILENAME,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        with tarfile.open(output_path, "w:gz") as archive:
            archive.add(snapshot_path, arcname=BACKUP_DB_FILENAME)
            archive.add(metadata_path, arcname=BACKUP_META_FILENAME)

    return output_path


def restore_backup(database_url: str, backup_path: Path, force: bool = False) -> Path:
    db_path = resolve_sqlite_db_path(database_url)
    backup_path = backup_path.resolve()

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and not force:
        raise FileExistsError(
            f"Target database already exists: {db_path}. Use --force to overwrite."
        )

    with tempfile.TemporaryDirectory(prefix="nhub-restore-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        with tarfile.open(backup_path, "r:gz") as archive:
            archive.extractall(path=tmp_root, filter="data")

        metadata_path = tmp_root / BACKUP_META_FILENAME
        extracted_db_path = tmp_root / BACKUP_DB_FILENAME
        if not metadata_path.exists() or not extracted_db_path.exists():
            raise ValueError(
                "Invalid backup archive: metadata.json or app.db is missing"
            )

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("schema_version") != BACKUP_SCHEMA_VERSION:
            raise ValueError("Unsupported backup schema version")

        tmp_target = db_path.with_suffix(db_path.suffix + ".tmp")
        shutil.copy2(extracted_db_path, tmp_target)
        tmp_target.replace(db_path)

    return db_path


def _default_backup_path() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path("backups") / f"notificationhub-{timestamp}.tar.gz"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and restore NotificationHub SQLite backups."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a backup archive")
    create_parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="Database URL (default: DATABASE_URL from env/config)",
    )
    create_parser.add_argument(
        "--output",
        default=str(_default_backup_path()),
        help="Backup archive path (.tar.gz)",
    )

    restore_parser = subparsers.add_parser("restore", help="Restore a backup archive")
    restore_parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="Database URL (default: DATABASE_URL from env/config)",
    )
    restore_parser.add_argument(
        "--input", required=True, help="Backup archive path (.tar.gz)"
    )
    restore_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing target database file",
    )

    args = parser.parse_args()
    if args.command == "create":
        backup_file = create_backup(args.database_url, Path(args.output))
        print(f"Backup created: {backup_file}")
        return 0
    if args.command == "restore":
        restored_db = restore_backup(
            args.database_url, Path(args.input), force=args.force
        )
        print(f"Backup restored to: {restored_db}")
        return 0
    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
