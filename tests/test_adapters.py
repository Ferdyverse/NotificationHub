from app.adapters import generic_json, generic_text


def test_generic_json_adapter():
    payload = {"source": "demo", "event": "demo.run", "message": "hello"}
    event = generic_json.adapt(payload)
    assert event.source == "demo"
    assert event.event == "demo.run"
    assert event.message == "hello"


def test_generic_text_adapter():
    event = generic_text.adapt("hello")
    assert event.source == "generic"
    assert event.event == "generic.text"
    assert event.message == "hello"
