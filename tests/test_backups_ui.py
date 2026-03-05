from io import BytesIO
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi import UploadFile
from starlette.requests import Request

from app.main import (
    ui_backups,
    ui_backups_create,
    ui_backups_download,
    ui_backups_restore,
    ui_backups_upload,
)


def _request(path: str = "/ui/backups") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


@pytest.mark.anyio
async def test_ui_backup_create_and_download(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))

    def _fake_create_backup(database_url: str, output_path):
        output_path.write_bytes(b"backup-data")
        return output_path

    monkeypatch.setattr("app.routers.ui_backups.create_backup", _fake_create_backup)

    response = await ui_backups_create(filename=None)
    assert response.status_code == 303

    location = response.headers["location"]
    assert location.startswith("/ui/backups?created=")
    created_name = parse_qs(urlparse(location).query)["created"][0]

    archive_path = tmp_path / created_name
    assert archive_path.exists()
    assert archive_path.stat().st_size > 0

    listing_response = await ui_backups(request=_request(), created=created_name)
    backup_names = [item["name"] for item in listing_response.context["backups"]]
    assert created_name in backup_names
    assert listing_response.context["created"] == created_name

    download_response = await ui_backups_download(filename=created_name)
    assert download_response.path == archive_path
    assert download_response.status_code == 200


@pytest.mark.anyio
async def test_ui_backup_create_rejects_invalid_filename(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        await ui_backups_create(filename="../not-allowed.tar.gz")

    assert exc.value.status_code == 422
    assert "Filename must end with .tar.gz" in str(exc.value.detail)


@pytest.mark.anyio
async def test_ui_backup_restore_success(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))
    archive_name = "notificationhub-20260303-100000.tar.gz"
    archive_path = tmp_path / archive_name
    archive_path.write_bytes(b"archive")

    calls = {"dispose": 0, "restore": 0}

    def _fake_dispose():
        calls["dispose"] += 1

    def _fake_restore(database_url: str, backup_path, force: bool = False):
        calls["restore"] += 1
        assert backup_path == archive_path
        assert force is True
        return tmp_path / "app.db"

    monkeypatch.setattr("app.routers.ui_backups.engine.dispose", _fake_dispose)
    monkeypatch.setattr("app.routers.ui_backups.restore_backup", _fake_restore)

    response = await ui_backups_restore(filename=archive_name)
    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/backups?restored={archive_name}"
    assert calls["restore"] == 1
    assert calls["dispose"] == 2


@pytest.mark.anyio
async def test_ui_backup_restore_missing_file_returns_404(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        await ui_backups_restore(filename="notificationhub-20260303-100000.tar.gz")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Backup file not found"


@pytest.mark.anyio
async def test_ui_backup_upload_success(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))
    filename = "notificationhub-20260303-120000.tar.gz"
    upload = UploadFile(filename=filename, file=BytesIO(b"archive-content"))

    response = await ui_backups_upload(upload=upload)
    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/backups?uploaded={filename}"

    backup_path = tmp_path / filename
    assert backup_path.exists()
    assert backup_path.read_bytes() == b"archive-content"

    listing_response = await ui_backups(request=_request(), uploaded=filename)
    assert listing_response.context["uploaded"] == filename


@pytest.mark.anyio
async def test_ui_backup_upload_rejects_invalid_filename(monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", str(tmp_path))
    upload = UploadFile(filename="backup.txt", file=BytesIO(b"archive-content"))

    with pytest.raises(HTTPException) as exc:
        await ui_backups_upload(upload=upload)

    assert exc.value.status_code == 422
    assert "Filename must end with .tar.gz" in str(exc.value.detail)


@pytest.mark.anyio
async def test_ui_backup_create_handles_permission_error(monkeypatch):
    monkeypatch.setattr("app.routers.ui_backups.settings.backup_dir", "/data")

    def _raise_permission():
        raise HTTPException(
            status_code=500,
            detail=(
                "Backup directory is not writable: /data. "
                "Set BACKUP_DIR to a writable path (for example /data/backups or /tmp)."
            ),
        )

    monkeypatch.setattr(
        "app.routers.ui_backups.ensure_backup_dir_available", _raise_permission
    )

    with pytest.raises(HTTPException) as exc:
        await ui_backups_create(filename="notificationhub-20260303-120000.tar.gz")

    assert exc.value.status_code == 500
    assert "Backup directory is not writable: /data" in str(exc.value.detail)
