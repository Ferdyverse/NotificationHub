from __future__ import annotations

import json
from typing import Any


def cap_payload(payload: Any, max_chars: int) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        encoded = json.dumps(payload, ensure_ascii=False)
        if len(encoded) <= max_chars:
            return payload
        return encoded[:max_chars]
    if isinstance(payload, str):
        return payload[:max_chars]
    return str(payload)[:max_chars]
