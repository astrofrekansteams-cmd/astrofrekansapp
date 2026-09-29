"""Outgoing email. One seam, provider chosen by configuration."""

from app.services.mail.mailer import (
    MailMessage,
    MailNotConfigured,
    get_mailer,
    set_mailer,
)

__all__ = ["MailMessage", "MailNotConfigured", "get_mailer", "set_mailer"]
