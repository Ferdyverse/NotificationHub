from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.delivery.base import DeliveryResult, with_retries


def deliver_email(config: dict, title: str, body: str) -> DeliveryResult:
    host = config.get("smtp_host")
    port = int(config.get("smtp_port") or 0)
    use_tls = bool(config.get("smtp_tls"))
    use_starttls = bool(config.get("smtp_starttls"))
    username = config.get("smtp_username")
    password = config.get("smtp_password")
    from_addr = config.get("from_addr")
    to_addrs = config.get("to_addrs")
    subject_prefix = config.get("subject_prefix")

    if not host or not port or not from_addr or not to_addrs:
        return DeliveryResult(False, "failed", "Missing email config fields")

    subject = f"{subject_prefix} {title}".strip() if subject_prefix else title
    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = to_addrs
    message["Subject"] = subject
    message.set_content(body)

    timeout = settings.outbound_timeout_seconds

    def _send():
        if use_tls:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        try:
            if use_starttls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(message)
        finally:
            server.quit()
        return DeliveryResult(True, "delivered")

    try:
        return with_retries(_send)
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult(False, "failed", str(exc))
