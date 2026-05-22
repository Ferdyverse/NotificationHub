from __future__ import annotations

from datetime import datetime, timezone

from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import SandboxedEnvironment

from app.adapters.types import STATUS_ICONS


def _format_datetime(value: str, fmt: str = "%d.%m.%Y %H:%M") -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime(fmt)
    except (ValueError, AttributeError):
        return str(value)


DEFAULT_TEMPLATE_BODY = """This template will only show the full JSON-payload, so you can pick the fields you want to display!"""


def build_env(strict: bool = False) -> SandboxedEnvironment:
    undefined_cls = StrictUndefined if strict else Undefined
    env = SandboxedEnvironment(undefined=undefined_cls)
    env.globals["status_icon"] = lambda value: STATUS_ICONS.get(value, "ℹ️")
    env.filters["split"] = lambda value, sep=None, maxsplit=-1: str(value).split(sep, maxsplit)
    env.filters["datetime"] = _format_datetime
    return env


def render_template(body: str, context: dict, strict: bool = False) -> str:
    env = build_env(strict=strict)
    template = env.from_string(body)
    return template.render(**context)
