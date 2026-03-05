from __future__ import annotations

import logging
import smtplib
import time
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("notificationhub.delivery")


@dataclass
class DeliveryResult:
    success: bool
    status: str
    error: str | None = None
    meta: dict | None = None


def with_retries(fn):
    """Retry with exponential backoff for delivery operations.

    Handles specific exceptions from HTTP and SMTP operations.
    """
    attempts = settings.outbound_retry_attempts
    backoff = settings.outbound_retry_backoff_seconds
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn()
        except (httpx.HTTPError, smtplib.SMTPException) as exc:
            last_exc = exc
            if attempt < attempts - 1:
                delay = backoff * (2**attempt)
                logger.debug(
                    "delivery_retry",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": attempts,
                        "delay_seconds": delay,
                        "error_type": type(exc).__name__,
                    },
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "delivery_failed_after_retries",
                    extra={
                        "attempts": attempts,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
        except Exception as exc:  # Unexpected errors
            last_exc = exc
            logger.error(
                "delivery_unexpected_error",
                extra={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            if attempt < attempts - 1:
                delay = backoff * (2**attempt)
                time.sleep(delay)
    if last_exc is not None:
        raise last_exc

def bearer_headers(config: dict | None) -> dict[str, str]:
    if not config:
        return {}
    token = config.get("bearer_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
