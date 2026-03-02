from __future__ import annotations

from typing import Iterable

from app.adapters.types import NormalizedEvent
from app.models import Rule


SUPPORTED_CONDITIONS = {
    "source_eq",
    "event_startswith",
    "severity_eq",
    "tags_contains",
    "entity_eq",
    "always",
}


def _match_condition(event: NormalizedEvent, cond: dict) -> bool:
    cond_type = cond.get("type")
    value = cond.get("value")
    if cond_type == "source_eq":
        return event.source == value
    if cond_type == "event_startswith":
        return event.event.startswith(str(value))
    if cond_type == "severity_eq":
        return event.severity == value
    if cond_type == "tags_contains":
        return bool(event.tags) and value in event.tags
    if cond_type == "entity_eq":
        key = cond.get("key")
        return bool(event.entities) and event.entities.get(key) == value
    if cond_type == "always":
        return True
    return False


def rule_matches(event: NormalizedEvent, rule: Rule) -> bool:
    conditions = rule.conditions or []
    if not conditions:
        return False
    return all(_match_condition(event, cond) for cond in conditions)


def select_route(event: NormalizedEvent, rules: Iterable[Rule]):
    for rule in sorted(rules, key=lambda r: r.order):
        if rule_matches(event, rule):
            return rule
    return None
