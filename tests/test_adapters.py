from app.adapters import forgejo, generic_json, generic_text, github


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


def test_github_workflow_run_adapter():
    payload = {
        "action": "completed",
        "workflow_run": {
            "name": "Docker build",
            "run_number": 4,
            "status": "completed",
            "conclusion": "success",
            "head_branch": "main",
            "html_url": "https://github.com/Ferdyverse/NotificationHub/actions/runs/22566226199",
        },
        "repository": {"full_name": "Ferdyverse/NotificationHub"},
        "sender": {"login": "Ferdyverse"},
    }
    event = github.adapt(payload, "workflow_run")
    assert event.source == "github"
    assert event.event == "github.workflow_run"
    assert event.severity == "success"
    assert "Docker build #4" in event.title
    assert "Conclusion: success" in event.message
    assert event.entities is not None
    assert event.entities.get("repo") == "Ferdyverse/NotificationHub"
    assert event.entities.get("workflow_conclusion") == "success"


def test_github_adapter_fallback_event():
    payload = {
        "action": "created",
        "repository": {"full_name": "Ferdyverse/NotificationHub"},
        "sender": {"login": "Ferdyverse"},
    }
    event = github.adapt(payload, "discussion")
    assert event.source == "github"
    assert event.event == "github.discussion"
    assert event.severity == "info"
    assert "GitHub discussion" in event.title


def test_forgejo_push_adapter():
    payload = {
        "ref": "refs/heads/main",
        "compare_url": "https://forgejo.example/compare/abc...def",
        "commits": [{"id": "abc"}, {"id": "def"}],
        "repository": {"full_name": "Ferdyverse/NotificationHub"},
        "pusher": {"login": "Ferdyverse"},
    }
    event = forgejo.adapt(payload, "push", source="forgejo")
    assert event.source == "forgejo"
    assert event.event == "forgejo.push"
    assert event.severity == "info"
    assert "Push to main" in event.title
    assert "Commits: 2" in event.message
