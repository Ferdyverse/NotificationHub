import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app.main import ingest
from app.models import EventLog, Ingress, Route, Template
from app.security.auth import hash_secret


def _build_request(body: bytes, headers: dict[str, str]) -> Request:
    header_items = [
        (name.lower().encode("utf-8"), value.encode("utf-8"))
        for name, value in headers.items()
    ]

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/ingest/test-ingress",
        "query_string": b"",
        "headers": header_items,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


@pytest.mark.anyio
async def test_ingest_template_render_error_is_handled(db_session, monkeypatch):
    ingress = Ingress(
        name="Test Ingress",
        slug="test-ingress",
        secret_hash=hash_secret("s3cr3t"),
        secret_value="s3cr3t",
        is_active=True,
    )
    route = Route(
        name="Route A",
        route_type="discord",
        config={"webhook_url": "https://discord.invalid"},
        is_active=True,
    )
    template = Template(
        name="Broken Template",
        body="{{ message.entities.repo }}",
        is_default=False,
        show_raw=False,
    )
    db_session.add_all([ingress, route, template])
    db_session.commit()

    route.template_id = template.id
    ingress.routes.append(route)
    db_session.add_all([route, ingress])
    db_session.commit()

    called = {"count": 0}

    def _fake_deliver(*args, **kwargs):  # noqa: ANN002, ANN003
        called["count"] += 1
        raise AssertionError("deliver() must not be called when rendering fails")

    monkeypatch.setattr("app.routers.ingress_webhooks.deliver", _fake_deliver)

    payload = json.dumps(
        {
            "source": "generic",
            "event": "demo.event",
            "severity": "info",
            "title": "Demo Event",
            "message": "Hello",
        }
    ).encode("utf-8")
    request = _build_request(
        body=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer s3cr3t",
        },
    )

    with pytest.raises(HTTPException) as exc:
        await ingest("test-ingress", request, db=db_session)

    assert exc.value.status_code == 502
    assert "Template render failed:" in str(exc.value.detail)
    assert called["count"] == 0

    latest_log = db_session.scalar(select(EventLog).order_by(EventLog.id.desc()))
    assert latest_log is not None
    assert latest_log.delivery_status == "failed"
    assert latest_log.delivery_error is not None
    assert "Template render failed:" in latest_log.delivery_error
