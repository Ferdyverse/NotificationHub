from types import SimpleNamespace

from app.main import resolve_template_id


def test_template_selection_uses_ingress_default_template():
    ingress = SimpleNamespace(default_template_id=20)
    route = SimpleNamespace(template_id=10)

    assert resolve_template_id(ingress, route) == 20


def test_template_selection_falls_back_to_route_template():
    ingress = SimpleNamespace(default_template_id=None)
    route = SimpleNamespace(template_id=10)

    assert resolve_template_id(ingress, route) == 10
