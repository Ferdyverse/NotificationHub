from __future__ import annotations

import hashlib
import hmac

from fastapi import Request

from app.models import Ingress
from app.security.auth import verify_secret


def _extract_signature(header_value: str | None, expected_algo: str) -> str | None:
    if not header_value:
        return None
    parts = header_value.split("=", 1)
    if len(parts) != 2:
        return None
    algo, digest = parts[0].strip().lower(), parts[1].strip()
    if algo != expected_algo or not digest:
        return None
    return digest


def _verify_hmac_signature(
    body: bytes, secret: str | None, digest: str, algorithm: str
) -> bool:
    if not secret:
        return False
    if algorithm == "sha256":
        hasher = hashlib.sha256
    elif algorithm == "sha1":
        hasher = hashlib.sha1
    else:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hasher).hexdigest()
    return hmac.compare_digest(expected, digest)


def _normalize_plain_signature(header_value: str | None) -> str | None:
    if not header_value:
        return None
    value = header_value.strip()
    if not value:
        return None
    if "=" in value:
        algo, digest = value.split("=", 1)
        if algo.strip().lower() == "sha256" and digest.strip():
            return digest.strip()
    return value


def _authorize_ingress_request(
    ingress: Ingress, request: Request, raw_body: bytes
) -> tuple[bool, bool]:
    any_auth_present = False
    any_auth_valid = False

    auth_header = request.headers.get("Authorization")
    bearer_token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()
    if not bearer_token:
        bearer_token = request.query_params.get("token")
    if bearer_token:
        any_auth_present = True
        if verify_secret(bearer_token, ingress.secret_hash):
            any_auth_valid = True

    gitlab_token = request.headers.get("X-Gitlab-Token")
    if gitlab_token:
        any_auth_present = True
        if verify_secret(gitlab_token, ingress.secret_hash):
            any_auth_valid = True

    github_sig_256 = _extract_signature(
        request.headers.get("X-Hub-Signature-256"), "sha256"
    )
    if github_sig_256:
        any_auth_present = True
        if _verify_hmac_signature(
            raw_body, ingress.secret_value, github_sig_256, "sha256"
        ):
            any_auth_valid = True

    github_sig_sha1 = _extract_signature(request.headers.get("X-Hub-Signature"), "sha1")
    if github_sig_sha1:
        any_auth_present = True
        if _verify_hmac_signature(
            raw_body, ingress.secret_value, github_sig_sha1, "sha1"
        ):
            any_auth_valid = True

    gitea_sig = _normalize_plain_signature(request.headers.get("X-Gitea-Signature"))
    forgejo_sig = _normalize_plain_signature(request.headers.get("X-Forgejo-Signature"))
    for signature in (gitea_sig, forgejo_sig):
        if signature:
            any_auth_present = True
            if _verify_hmac_signature(
                raw_body, ingress.secret_value, signature, "sha256"
            ):
                any_auth_valid = True

    return any_auth_present, any_auth_valid
