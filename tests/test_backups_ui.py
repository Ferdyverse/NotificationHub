from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.main import ui_backups, ui_backups_create, ui_backups_download


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
    monkeypatch.setattr("app.main.settings.backup_dir", str(tmp_path))

    def _fake_create_backup(database_url: str, output_path):
        output_path.write_bytes(b"backup-data")
        return output_path

    monkeypatch.setattr("app.main.create_backup", _fake_create_backup)

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
    monkeypatch.setattr("app.main.settings.backup_dir", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        await ui_backups_create(filename="../not-allowed.tar.gz")

    assert exc.value.status_code == 422
    assert "Filename must end with .tar.gz" in str(exc.value.detail)
