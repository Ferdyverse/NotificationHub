import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.main import ui_events
from app.models import EventLog, Ingress


def _request(path: str = "/ui/events") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def _create_ingress(db_session, slug: str) -> Ingress:
    ingress = Ingress(
        name=f"Ingress {slug}",
        slug=slug,
        secret_hash="hashed-secret",
        secret_value="plain-secret",
        is_active=True,
    )
    db_session.add(ingress)
    db_session.commit()
    db_session.refresh(ingress)
    return ingress


@pytest.mark.anyio
async def test_ui_events_pagination(db_session):
    ingress = _create_ingress(db_session, "ingress-pagination")

    for i in range(55):
        db_session.add(
            EventLog(
                ingress_id=ingress.id,
                source="generic",
                event="generic.json",
                severity="info",
                title=f"TITLE-{i:03d}",
                message=f"Message {i}",
                tags=None,
                entities=None,
                raw={"idx": i},
                delivery_status="delivered",
                delivery_error=None,
            )
        )
    db_session.commit()

    first_page = await ui_events(
        request=_request(),
        ingress_id=None,
        page=1,
        db=db_session,
    )
    first_logs = first_page.context["logs"]
    assert first_page.context["total"] == 55
    assert first_page.context["total_pages"] == 2
    assert len(first_logs) == 50
    assert first_logs[0].title == "TITLE-054"
    assert first_logs[-1].title == "TITLE-005"

    second_page = await ui_events(
        request=_request(),
        ingress_id=None,
        page=2,
        db=db_session,
    )
    second_logs = second_page.context["logs"]
    assert len(second_logs) == 5
    assert second_logs[0].title == "TITLE-004"
    assert second_logs[-1].title == "TITLE-000"


@pytest.mark.anyio
async def test_ui_events_combined_filters(db_session):
    ingress = _create_ingress(db_session, "ingress-filter")

    db_session.add(
        EventLog(
            ingress_id=ingress.id,
            source="github",
            event="github.push",
            severity="error",
            title="GH Error Deploy",
            message="Deployment failed",
            tags=["github:push"],
            entities={"repo": "notificationhub"},
            raw={"status": "failed"},
            delivery_status="failed",
            delivery_error="network timeout",
        )
    )
    db_session.add(
        EventLog(
            ingress_id=ingress.id,
            source="generic",
            event="generic.text",
            severity="info",
            title="GEN Info",
            message="Background task started",
            tags=["generic:text"],
            entities={"task": "sync"},
            raw={"status": "started"},
            delivery_status="delivered",
            delivery_error=None,
        )
    )
    db_session.commit()

    response = await ui_events(
        request=_request(),
        ingress_id=None,
        source="github",
        severity="error",
        event="push",
        q="Deploy",
        page=1,
        db=db_session,
    )
    logs = response.context["logs"]
    assert response.context["total"] == 1
    assert len(logs) == 1
    assert logs[0].title == "GH Error Deploy"


@pytest.mark.anyio
async def test_ui_events_invalid_severity_filter_returns_422(db_session):
    with pytest.raises(HTTPException) as exc:
        await ui_events(
            request=_request(),
            ingress_id=None,
            severity="critical",
            db=db_session,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Invalid severity filter"
