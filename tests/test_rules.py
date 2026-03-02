from app.adapters.types import NormalizedEvent
from app.models import Route, Rule
from app.routing.rules import select_route


def test_rule_first_match_wins():
    route_a = Route(id=1, name="A", route_type="discord", config={"webhook_url": "a"})
    route_b = Route(id=2, name="B", route_type="discord", config={"webhook_url": "b"})
    rules = [
        Rule(name="first", order=1, route=route_a, conditions=[{"type": "source_eq", "value": "demo"}]),
        Rule(name="second", order=2, route=route_b, conditions=[{"type": "source_eq", "value": "demo"}]),
    ]
    event = NormalizedEvent(
        source="demo",
        event="demo.run",
        severity="info",
        title="Demo",
        message="Hello",
    )
    rule = select_route(event, rules)
    assert rule.route is route_a


def test_rule_fallback_none():
    rules = [
        Rule(
            name="only",
            order=1,
            route=Route(id=1, name="A", route_type="discord", config={"webhook_url": "a"}),
            conditions=[{"type": "source_eq", "value": "demo"}],
        )
    ]
    event = NormalizedEvent(
        source="other",
        event="demo.run",
        severity="info",
        title="Demo",
        message="Hello",
    )
    rule = select_route(event, rules)
    assert rule is None
