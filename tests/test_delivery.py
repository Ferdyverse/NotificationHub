
import httpx

from app.delivery.dispatcher import deliver
from app.delivery.email import deliver_email


class DummyResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._json

    @property
    def is_success(self):
        return self.status_code < 400


def test_deliver_discord(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResponse(204)

    monkeypatch.setattr(httpx, "post", fake_post)
    result = deliver("discord", {"webhook_url": "https://discord.invalid"}, "Title", "Body")
    assert result.success is True


def test_deliver_matrix(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/login"):
            return DummyResponse(200, {"access_token": "abc"})
        return DummyResponse(200, {})

    monkeypatch.setattr(httpx, "post", fake_post)
    config = {
        "homeserver": "https://matrix.invalid",
        "room_id": "!room:server",
        "username": "user",
        "password": "pass",
    }
    result = deliver("matrix", config, "Title", "Body")
    assert result.success is True
    assert any(url.endswith("/login") for url in calls)


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
