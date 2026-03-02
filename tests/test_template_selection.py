from types import SimpleNamespace

from app.main import resolve_template_id


def test_template_selection_prefers_rule_template():
    matched_rule = SimpleNamespace(template_id=30)
    ingress = SimpleNamespace(default_template_id=20)
    route = SimpleNamespace(template_id=10)

    assert resolve_template_id(matched_rule, ingress, route) == 30


def test_template_selection_uses_ingress_default_without_rule_template():
    matched_rule = SimpleNamespace(template_id=None)
    ingress = SimpleNamespace(default_template_id=20)
    route = SimpleNamespace(template_id=10)

    assert resolve_template_id(matched_rule, ingress, route) == 20


def test_template_selection_falls_back_to_route_template():
    matched_rule = None
    ingress = SimpleNamespace(default_template_id=None)
    route = SimpleNamespace(template_id=10)

    assert resolve_template_id(matched_rule, ingress, route) == 10
