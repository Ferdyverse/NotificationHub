from app.security.auth import hash_secret
from app.models import Ingress, Route


def test_ingress_auth_requires_token(client, db_session, monkeypatch):
    route = Route(name="default", route_type="discord", config={"webhook_url": "https://example.com"})
    db_session.add(route)
    db_session.commit()

    secret = "supersecret"
    ingress = Ingress(
        name="Test",
        slug="test",
        secret_hash=hash_secret(secret),
    )
    db_session.add(ingress)
    ingress.routes = [route]
    db_session.commit()

    class DummyResult:
        success = True
        error = None

    def fake_deliver(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr("app.main.deliver", fake_deliver)

    resp = client.post("/ingest/test", json={"hello": "world"})
    assert resp.status_code == 401

    resp = client.post(
        "/ingest/test",
        json={"hello": "world"},
        headers={"X-Formatter-Token": "wrong"},
    )
    assert resp.status_code == 403

    resp = client.post(
        "/ingest/test",
        json={"hello": "world"},
        headers={"X-Formatter-Token": secret},
    )
    assert resp.status_code == 204
