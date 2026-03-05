from __future__ import annotations

import json

from fastapi import HTTPException, Request

from app.adapters.types import NormalizedEvent
from app.config import settings
from app.models import Ingress
from app.runtime import DedupeCache
from app.utils import cap_payload


def adapt_request_payload(raw_body: bytes, content_type: str, request: Request):
    try:
        if "application/json" in content_type:
            payload = json.loads(raw_body)
            from app.adapters import forgejo, generic_json, github

            forgejo_event = request.headers.get("X-Forgejo-Event")
            gitea_event = request.headers.get("X-Gitea-Event")
            github_event = request.headers.get("X-GitHub-Event")
            if forgejo_event or gitea_event:
                source = "forgejo" if forgejo_event else "gitea"
                event = forgejo.adapt(
                    payload, forgejo_event or gitea_event, source=source
                )
            elif github_event:
                event = github.adapt(payload, github_event)
            else:
                event = generic_json.adapt(payload)
        else:
            from app.adapters import generic_text

            payload = raw_body.decode("utf-8", errors="replace")
            event = generic_text.adapt(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}") from exc

    event.raw = cap_payload(event.raw, settings.max_raw_payload_chars)
    return event


def build_dedupe_key(ingress: Ingress, event: NormalizedEvent, request: Request) -> str:
    delivery_id = None
    if event.source == "github":
        delivery_id = request.headers.get("X-GitHub-Delivery")
    elif event.source in {"forgejo", "gitea"}:
        delivery_id = request.headers.get("X-Forgejo-Delivery") or request.headers.get(
            "X-Gitea-Delivery"
        )
    elif event.source == "gitlab":
        delivery_id = request.headers.get("X-Gitlab-Event-UUID")

    if delivery_id:
        return DedupeCache.build_key(str(ingress.id), event.source, delivery_id)
    return DedupeCache.build_key(
        str(ingress.id), event.source, event.event, event.title, event.message
    )
