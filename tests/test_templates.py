import pytest

from app.render.templates import render_template


def test_template_render_happy_path():
    body = "Hello {{ title }}"
    rendered = render_template(body, {"title": "World"}, strict=True)
    assert rendered == "Hello World"


def test_title_template_render():
    body = "{{ severity|upper }}: {{ title }}"
    rendered = render_template(
        body, {"title": "Hello", "severity": "info"}, strict=True
    )
    assert rendered == "INFO: Hello"


def test_template_render_missing_var_raises():
    body = "Hello {{ missing }}"
    with pytest.raises(Exception):
        render_template(body, {"title": "World"}, strict=True)
