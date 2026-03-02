import sqlite3
from pathlib import Path

import pytest

from app.tools.backup import create_backup, resolve_sqlite_db_path, restore_backup


def _seed_db(db_path: Path, value: str):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sample (id INTEGER PRIMARY KEY, value TEXT)"
        )
        conn.execute("DELETE FROM sample")
        conn.execute("INSERT INTO sample(value) VALUES (?)", (value,))
        conn.commit()
    finally:
        conn.close()


def _read_value(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT value FROM sample LIMIT 1").fetchone()
        return str(row[0])
    finally:
        conn.close()


def test_resolve_sqlite_db_path_rejects_non_sqlite():
    with pytest.raises(ValueError):
        resolve_sqlite_db_path("postgresql://localhost/db")


def test_create_and_restore_backup_roundtrip(tmp_path: Path):
    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "backup.tar.gz"
    database_url = f"sqlite:///{db_path}"

    _seed_db(db_path, "prod-data")
    create_backup(database_url, backup_path)

    _seed_db(db_path, "local-change")
    restore_backup(database_url, backup_path, force=True)

    assert backup_path.exists()
    assert _read_value(db_path) == "prod-data"


def test_restore_requires_force_when_target_exists(tmp_path: Path):
    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "backup.tar.gz"
    database_url = f"sqlite:///{db_path}"

    _seed_db(db_path, "prod-data")
    create_backup(database_url, backup_path)

    with pytest.raises(FileExistsError):
        restore_backup(database_url, backup_path)
