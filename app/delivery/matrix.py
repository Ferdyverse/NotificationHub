from __future__ import annotations

import logging
import time
from urllib.parse import quote

import httpx
import markdown

from app.config import settings
from app.delivery.base import DeliveryResult, with_retries

logger = logging.getLogger("formatter.matrix")

TOKEN_CACHE: dict[tuple[str, str], dict[str, float | str]] = {}
DEFAULT_TOKEN_TTL_SECONDS = 1800


def _cache_key(homeserver: str, username: str) -> tuple[str, str]:
    return (homeserver.rstrip("/"), username)


def _get_cached_token(homeserver: str, username: str) -> str | None:
    key = _cache_key(homeserver, username)
    entry = TOKEN_CACHE.get(key)
    if not entry:
        return None
    expires_at = entry.get("expires_at")
    token = entry.get("token")
    if not token:
        return None
    if expires_at and time.time() >= float(expires_at):
        TOKEN_CACHE.pop(key, None)
        return None
    return str(token)


def _store_token(homeserver: str, username: str, token: str, expires_in_ms: int | None):
    ttl = DEFAULT_TOKEN_TTL_SECONDS
    if expires_in_ms and expires_in_ms > 0:
        ttl = max(60, int(expires_in_ms / 1000))
    TOKEN_CACHE[_cache_key(homeserver, username)] = {
        "token": token,
        "expires_at": time.time() + ttl,
    }


def _join_url_candidates(homeserver: str, room_id: str) -> list[str]:
    base = homeserver.rstrip("/")
    raw = room_id
    encoded = quote(room_id, safe="")
    return [
        f"{base}/_matrix/client/v3/rooms/{encoded}/join",
        f"{base}/_matrix/client/r0/rooms/{encoded}/join",
        f"{base}/_matrix/client/v3/join/{raw}",
        f"{base}/_matrix/client/r0/join/{raw}",
        f"{base}/_matrix/client/v3/join/{encoded}",
        f"{base}/_matrix/client/r0/join/{encoded}",
    ]


def _send_room_message(
    homeserver: str,
    room_id: str,
    content: dict,
    headers: dict[str, str],
    timeout: int,
) -> httpx.Response:
    base = homeserver.rstrip("/")
    raw = room_id
    encoded = quote(room_id, safe="")
    send_url_candidates = [
        f"{base}/_matrix/client/v3/rooms/{encoded}/send/m.room.message",
        f"{base}/_matrix/client/r0/rooms/{encoded}/send/m.room.message",
        f"{base}/_matrix/client/v3/rooms/{raw}/send/m.room.message",
        f"{base}/_matrix/client/r0/rooms/{raw}/send/m.room.message",
    ]
    last_resp: httpx.Response | None = None
    for send_url in send_url_candidates:
        resp = httpx.post(send_url, json=content, headers=headers, timeout=timeout)
        last_resp = resp
        if resp.is_success:
            return resp
        if resp.status_code not in {404, 405}:
            return resp
    if last_resp is None:
        raise RuntimeError("No Matrix send endpoint candidates generated")
    return last_resp


def _try_auto_join_room(
    homeserver: str,
    room_id: str,
    headers: dict[str, str],
    timeout: int,
) -> str | None:
    for join_url in _join_url_candidates(homeserver, room_id):
        join_resp = httpx.post(join_url, json={}, headers=headers, timeout=timeout)
        if join_resp.is_success:
            try:
                payload = join_resp.json()
            except Exception:  # noqa: BLE001
                payload = {}
            joined_room_id = payload.get("room_id")
            if isinstance(joined_room_id, str) and joined_room_id:
                return joined_room_id
            return room_id
    return None


def deliver_matrix(config: dict, title: str, body: str) -> DeliveryResult:
    homeserver = config.get("homeserver")
    room_id = config.get("room_id")
    username = config.get("username")
    password = config.get("password")
    bearer_token = config.get("bearer_token")
    auto_join = bool(config.get("auto_join"))
    use_markdown = bool(config.get("markdown"))
    if not homeserver or not room_id or not username or not password:
        if not bearer_token:
            return DeliveryResult(False, "failed", "Missing Matrix config fields")

    timeout = settings.outbound_timeout_seconds

    access_token: str | None = None
    expires_in_ms: int | None = None
    issued_via_login = False

    def _send():
        nonlocal access_token, expires_in_ms, issued_via_login
        access_token = bearer_token
        if not access_token:
            cached = _get_cached_token(homeserver, username)
            if cached:
                access_token = cached
                logger.info("matrix_token_cache_hit", extra={"username": username})
            else:
                logger.info("matrix_token_cache_miss", extra={"username": username})
        if not access_token:
            login_payload = {
                "type": "m.login.password",
                "user": username,
                "password": password,
            }
            login_resp = httpx.post(
                f"{homeserver.rstrip('/')}/_matrix/client/r0/login",
                json=login_payload,
                timeout=timeout,
            )
            if login_resp.status_code == 429:
                retry_after = login_resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(int(retry_after))
            login_resp.raise_for_status()
            payload = login_resp.json()
            access_token = payload.get("access_token")
            expires_in_ms = payload.get("expires_in_ms")
            logger.info(
                "matrix_login_result",
                extra={
                    "has_access_token": bool(access_token),
                    "response_keys": list(payload.keys()),
                },
            )
            # token logging disabled after debugging
            if not access_token:
                raise RuntimeError("Matrix login missing access_token")
            issued_via_login = True
            _store_token(
                homeserver,
                username,
                str(access_token),
                expires_in_ms,
            )

        plain_body = f"{title}\n\n{body}"
        if use_markdown:
            html_body = markdown.markdown(plain_body, extensions=["extra"])
            content = {
                "msgtype": "m.text",
                "body": plain_body,
                "format": "org.matrix.custom.html",
                "formatted_body": html_body,
            }
        else:
            content = {
                "msgtype": "m.text",
                "body": plain_body,
            }
        headers = {"Authorization": f"Bearer {access_token}"}
        send_resp = _send_room_message(homeserver, room_id, content, headers, timeout)
        if send_resp.status_code in {403, 404} and auto_join:
            joined_room_id = _try_auto_join_room(homeserver, room_id, headers, timeout)
            if joined_room_id:
                send_resp = _send_room_message(
                    homeserver, joined_room_id, content, headers, timeout
                )
        if not send_resp.is_success:
            raise httpx.HTTPStatusError(
                f"Matrix send failed: {send_resp.status_code} {send_resp.text}",
                request=send_resp.request,
                response=send_resp,
            )
        result = DeliveryResult(True, "delivered")
        if issued_via_login and access_token and not bearer_token:
            result.meta = {
                "access_token": str(access_token),
                "expires_in_ms": expires_in_ms,
            }
        return result

    try:
        return with_retries(_send)
    except Exception as exc:  # noqa: BLE001
        result = DeliveryResult(False, "failed", str(exc))
        if issued_via_login and access_token and not bearer_token:
            result.meta = {
                "access_token": str(access_token),
                "expires_in_ms": expires_in_ms,
            }
        return result
