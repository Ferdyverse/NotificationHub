from app.adapters.types import NormalizedEvent


def adapt(payload: str) -> NormalizedEvent:
    return NormalizedEvent(
        source="generic",
        event="generic.text",
        severity="info",
        title="Generic Text",
        message=str(payload),
        raw=payload,
    ).with_timestamp()
