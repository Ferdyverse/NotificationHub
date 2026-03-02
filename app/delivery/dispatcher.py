from __future__ import annotations

from app.delivery.base import DeliveryResult
from app.delivery.discord import deliver_discord
from app.delivery.email import deliver_email
from app.delivery.matrix import deliver_matrix


def deliver(route_type: str | None, config: dict | None, title: str, body: str) -> DeliveryResult:
    if not route_type:
        return DeliveryResult(False, "failed", "Route type is missing")
    config = config or {}
    if route_type == "matrix":
        return deliver_matrix(config, title, body)
    if route_type == "discord":
        return deliver_discord(config, title, body)
    if route_type == "email":
        return deliver_email(config, title, body)
    return DeliveryResult(False, "failed", f"Unsupported route type: {route_type}")
