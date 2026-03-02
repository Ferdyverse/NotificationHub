
import httpx

from app.delivery.dispatcher import deliver
from app.delivery.email import deliver_email


class DummyResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = str(self._json)
        self.request = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._json

    @property
    def is_success(self):
        return self.status_code < 400


def _patch_matrix_http(monkeypatch, fake_request):
    monkeypatch.setattr(httpx, "post", fake_request)
    monkeypatch.setattr(httpx, "put", fake_request)


def test_deliver_discord(monkeypatch):
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return DummyResponse(204)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = deliver("discord", {"webhook_url": "https://discord.invalid"}, "Title", "Body")
    assert result.success is True
    assert sent["json"]["content"] == "**Title**\nBody"
    assert "embeds" not in sent["json"]


def test_deliver_discord_embed(monkeypatch):
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return DummyResponse(204)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = deliver(
        "discord",
        {
            "webhook_url": "https://discord.invalid",
            "use_embed": True,
            "embed_color": "#5865F2",
        },
        "Deploy Succeeded",
        "Service is healthy.",
    )
    assert result.success is True
    assert "content" not in sent["json"]
    assert sent["json"]["embeds"][0]["title"] == "Deploy Succeeded"
    assert sent["json"]["embeds"][0]["description"] == "Service is healthy."
    assert sent["json"]["embeds"][0]["color"] == 5793266


def test_deliver_discord_custom_payload_template(monkeypatch):
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return DummyResponse(204)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = deliver(
        "discord",
        {"webhook_url": "https://discord.invalid"},
        "Ignored Title",
        "Ignored Body",
        extra={
            "discord_payload_json": (
                '{"content":"Build done","embeds":[{"title":"Deploy","fields":[{"name":"env","value":"prod"}]}]}'
            )
        },
    )
    assert result.success is True
    assert sent["json"]["content"] == "Build done"
    assert sent["json"]["embeds"][0]["title"] == "Deploy"
    assert sent["json"]["embeds"][0]["fields"][0]["name"] == "env"


def test_deliver_discord_custom_payload_template_invalid_json():
    result = deliver(
        "discord",
        {"webhook_url": "https://discord.invalid"},
        "Ignored Title",
        "Ignored Body",
        extra={"discord_payload_json": "{invalid"},
    )
    assert result.success is False
    assert "invalid JSON" in (result.error or "")


def test_deliver_matrix(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/login"):
            return DummyResponse(200, {"access_token": "abc"})
        return DummyResponse(200, {})

    _patch_matrix_http(monkeypatch, fake_post)
    config = {
        "homeserver": "https://matrix.invalid",
        "room_id": "!room:server",
        "username": "user",
        "password": "pass",
    }
    result = deliver("matrix", config, "Title", "Body")
    assert result.success is True
    assert any(url.endswith("/login") for url in calls)


def test_deliver_matrix_auto_join_on_forbidden(monkeypatch):
    calls = []
    send_calls = {"count": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/login"):
            return DummyResponse(200, {"access_token": "abc"})
        if "/send/m.room.message" in url:
            send_calls["count"] += 1
            if send_calls["count"] == 1:
                return DummyResponse(403)
            return DummyResponse(200, {})
        if "/join" in url:
            return DummyResponse(200, {})
        return DummyResponse(200, {})

    _patch_matrix_http(monkeypatch, fake_post)
    config = {
        "homeserver": "https://matrix.invalid",
        "room_id": "!room:server",
        "username": "user",
        "password": "pass",
        "auto_join": True,
    }
    result = deliver("matrix", config, "Title", "Body")
    assert result.success is True
    assert any("/join" in url for url in calls)
    assert sum(1 for url in calls if "/send/m.room.message" in url) == 2


def test_deliver_matrix_auto_join_uses_joined_room_id(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/login"):
            return DummyResponse(200, {"access_token": "abc"})
        if "/send/m.room.message" in url and (
            "%23alias%3Aserver" in url or "#alias:server" in url
        ):
            return DummyResponse(404)
        if "/join/" in url:
            return DummyResponse(200, {"room_id": "!joined:server"})
        if "/send/m.room.message" in url and "%21joined%3Aserver" in url:
            return DummyResponse(200, {})
        return DummyResponse(400)

    _patch_matrix_http(monkeypatch, fake_post)
    config = {
        "homeserver": "https://matrix.invalid",
        "room_id": "#alias:server",
        "username": "user",
        "password": "pass",
        "auto_join": True,
    }
    result = deliver("matrix", config, "Title", "Body")
    assert result.success is True
    assert any("%23alias%3Aserver" in url for url in calls if "/send/m.room.message" in url)
    assert any("%21joined%3Aserver" in url for url in calls if "/send/m.room.message" in url)


def test_deliver_matrix_relogin_on_unauthorized_bearer(monkeypatch):
    calls = []
    seen_tokens = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/login"):
            return DummyResponse(200, {"access_token": "fresh-token"})
        if "/send/m.room.message" in url:
            auth = (headers or {}).get("Authorization", "")
            seen_tokens.append(auth)
            if auth == "Bearer stale-token":
                return DummyResponse(401, {"errcode": "M_UNKNOWN_TOKEN"})
            return DummyResponse(200, {})
        return DummyResponse(400)

    _patch_matrix_http(monkeypatch, fake_post)
    config = {
        "homeserver": "https://matrix.invalid",
        "room_id": "!room:server",
        "username": "user",
        "password": "pass",
        "bearer_token": "stale-token",
    }
    result = deliver("matrix", config, "Title", "Body")
    assert result.success is True
    assert any(url.endswith("/login") for url in calls)
    assert "Bearer stale-token" in seen_tokens
    assert "Bearer fresh-token" in seen_tokens


def test_deliver_email(monkeypatch):
    sent = {}

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port

        def starttls(self):
            sent["starttls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["to"] = message["To"]

        def quit(self):
            sent["quit"] = True

    monkeypatch.setattr("smtplib.SMTP", DummySMTP)

    config = {
        "smtp_host": "smtp.invalid",
        "smtp_port": 587,
        "smtp_starttls": True,
        "smtp_username": "user",
        "smtp_password": "pass",
        "from_addr": "from@example.com",
        "to_addrs": "to@example.com",
    }
    result = deliver_email(config, "Title", "Body")
    assert result.success is True
    assert sent.get("login") == ("user", "pass")
