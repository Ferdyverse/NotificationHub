import hashlib
import hmac
from types import SimpleNamespace

from starlette.datastructures import QueryParams

from app.main import _authorize_ingress_request
from app.security.auth import hash_secret


def _req(headers: dict[str, str] | None = None, query: str = ""):
    return SimpleNamespace(headers=headers or {}, query_params=QueryParams(query))


def _ingress(secret: str, with_secret_value: bool = True):
    return SimpleNamespace(
        secret_hash=hash_secret(secret),
        secret_value=secret if with_secret_value else None,
    )


def test_auth_missing():
    present, valid = _authorize_ingress_request(_ingress("s3cr3t"), _req(), b"{}")
    assert present is False
    assert valid is False


def test_auth_bearer():
    present, valid = _authorize_ingress_request(
        _ingress("s3cr3t"),
        _req(headers={"Authorization": "Bearer s3cr3t"}),
        b'{"hello":"world"}',
    )
    assert present is True
    assert valid is True


def test_auth_query_token():
    present, valid = _authorize_ingress_request(
        _ingress("s3cr3t"),
        _req(query="token=s3cr3t"),
        b'{"hello":"world"}',
    )
    assert present is True
    assert valid is True


def test_auth_gitlab_token():
    present, valid = _authorize_ingress_request(
        _ingress("s3cr3t"),
        _req(headers={"X-Gitlab-Token": "s3cr3t"}),
        b'{"hello":"world"}',
    )
    assert present is True
    assert valid is True


def test_auth_github_signature_256():
    secret = "githubsecret"
    body = b'{"hello":"github"}'
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    present, valid = _authorize_ingress_request(
        _ingress(secret),
        _req(headers={"X-Hub-Signature-256": f"sha256={digest}"}),
        body,
    )
    assert present is True
    assert valid is True


def test_auth_github_signature_fails_without_secret_value():
    secret = "githubsecret"
    body = b'{"hello":"github"}'
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    present, valid = _authorize_ingress_request(
        _ingress(secret, with_secret_value=False),
        _req(headers={"X-Hub-Signature-256": f"sha256={digest}"}),
        body,
    )
    assert present is True
    assert valid is False
