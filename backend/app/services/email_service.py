"""
Email Service

Handles sending outbound emails using standard SMTP.
We use asyncio.to_thread to run synchronous smtplib code
without blocking the main event loop.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.app.core.config import settings

log = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, text_content: str, html_content: str = None) -> bool:
    """
    Send an email via configured SMTP server.
    Returns True if successful, False otherwise.
    """
    if not settings.smtp_host or not settings.smtp_username:
        log.warning("smtp_not_configured", to=to_email, subject=subject)
        log.info(f"[MOCK EMAIL] To: {to_email} | Subject: {subject} | Content: {text_content}")
        return False

    def _sync_send():
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email or settings.smtp_username
        msg["To"] = to_email
        msg.set_content(text_content)
        
        if html_content:
            msg.add_alternative(html_content, subtype="html")

        try:
            # Connect to SMTP server
            if settings.smtp_port == 465:
                # Port 465 requires implicit SSL from the start
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)
            else:
                # Other ports (587, 25) use explicit TLS
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                server.starttls()
                
            server.set_debuglevel(0)
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            log.error("smtp_delivery_failed", error=str(e), to=to_email)
            return False

    log.info("sending_email", to=to_email, subject=subject)
    # Run the synchronous smtplib code in a thread pool so we don't block
    return await asyncio.to_thread(_sync_send)
