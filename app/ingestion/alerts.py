from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


def send_ingestion_email(subject: str, body: str) -> bool:
    if not all([settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.email_from, settings.email_to]):
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.email_from, [settings.email_to], msg.as_string())
    return True
