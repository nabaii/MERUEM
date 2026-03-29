"""
SMTP email notifications.  Gracefully no-ops when SMTP is not configured.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user)


def send_email(to: str, subject: str, body_html: str) -> None:
    """
    Send a transactional email via SMTP.
    Silently skips if SMTP credentials are not configured.
    """
    if not _smtp_configured():
        logger.debug("SMTP not configured — skipping email to %s", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))

    try:
        if settings.smtp_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(settings.smtp_from, [to], msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(settings.smtp_from, [to], msg.as_string())
        logger.info("Email sent to %s — %s", to, subject)
    except Exception as exc:
        logger.warning("Failed to send email to %s: %s", to, exc)


def send_export_ready(to: str, campaign_name: str, export_id: str) -> None:
    subject = f"[Meruem] Your export for '{campaign_name}' is ready"
    body = f"""
    <p>Hi,</p>
    <p>Your audience export for campaign <strong>{campaign_name}</strong> is ready.</p>
    <p>Export ID: <code>{export_id}</code></p>
    <p>Log in to your dashboard to download it.</p>
    <p>— The Meruem Team</p>
    """
    send_email(to, subject, body)


def send_export_failed(to: str, campaign_name: str, error: str) -> None:
    subject = f"[Meruem] Export failed for '{campaign_name}'"
    body = f"""
    <p>Hi,</p>
    <p>Unfortunately your export for <strong>{campaign_name}</strong> failed.</p>
    <p>Error: <code>{error}</code></p>
    <p>Please try again or contact support.</p>
    <p>— The Meruem Team</p>
    """
    send_email(to, subject, body)
