from __future__ import annotations

from jinja2.sandbox import SandboxedEnvironment

from app.adapters.types import STATUS_ICONS


DEFAULT_TEMPLATE_BODY = """This template will only show the full JSON-payload, so you can pick the fields you want to display!"""


def build_env(strict: bool = False) -> SandboxedEnvironment:
    env = SandboxedEnvironment()
    env.globals["status_icon"] = lambda value: STATUS_ICONS.get(value, "ℹ️")
    return env


def render_template(body: str, context: dict, strict: bool = False) -> str:
    env = build_env(strict=strict)
    template = env.from_string(body)
    return template.render(**context)
