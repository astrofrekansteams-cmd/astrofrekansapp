"""Mail providers behind one small interface.

`MAIL_PROVIDER` picks one:

* `disabled` (default) - nothing can be sent, and callers are told so. The
  password-reset route then answers 503 `password_reset_unavailable` for every
  address alike, instead of claiming a link was sent that never will be.
* `smtp` - any SMTP relay (a transactional mail service's SMTP endpoint, or a
  company server). No vendor SDK: which service to use is a business
  decision, and SMTP is what every one of them speaks. The configuration is
  validated (`smtp_config_problems`); an invalid one is "not configured", and
  in production refuses to boot (`Settings.assert_production_ready`).
* `log` - writes the message to the local log. Local development only; refused
  in production, because a log is not a mailbox.
* `memory` - keeps messages in a list. Tests only; refused in production.

Delivery through SMTP:

* **Timeout** per connection (`SMTP_TIMEOUT_SECONDS`).
* **Retry** only what can succeed later: connection failures, timeouts,
  disconnects and 4xx replies, up to `SMTP_MAX_ATTEMPTS` with exponential
  backoff. Authentication failures and 5xx replies fail at once - retrying a
  wrong password or a refused recipient only adds load.
* **Sanitised logging**: the kind of message, the attempt, the error class and
  the SMTP reply code. Never the recipient, the subject, the body (which holds
  a reset token), the host credentials or the server's reply text.
"""

from __future__ import annotations

import asyncio
import re
import smtplib
import socket
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

_ADDRESS = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class MailNotConfigured(AppError):
    status_code = 503
    code = "mail_not_configured"
    message = "Email delivery is not configured on this server."


class MailDeliveryFailed(Exception):
    """Sending failed. `transient` says whether a later attempt could work."""

    def __init__(self, reason: str, *, transient: bool, smtp_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.transient = transient
        self.smtp_code = smtp_code


@dataclass(slots=True, frozen=True)
class MailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None
    # For logs and metrics only (e.g. "password_reset"). Never content.
    kind: str = "generic"
    headers: dict[str, str] = field(default_factory=dict)


def smtp_config_problems() -> list[str]:
    """What is wrong with the SMTP settings. Names settings, never values."""
    problems: list[str] = []
    if not settings.smtp_host:
        problems.append("SMTP_HOST is not set")
    if not settings.mail_from:
        problems.append("MAIL_FROM is not set")
    elif not _ADDRESS.match(_bare_address(settings.mail_from)):
        problems.append("MAIL_FROM is not an email address")
    if not 1 <= settings.smtp_port <= 65535:
        problems.append("SMTP_PORT is out of range")
    if settings.smtp_ssl and settings.smtp_starttls:
        problems.append("SMTP_SSL and SMTP_STARTTLS are exclusive; choose one")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        problems.append("SMTP_USERNAME and SMTP_PASSWORD must be set together")
    if settings.smtp_timeout_seconds <= 0:
        problems.append("SMTP_TIMEOUT_SECONDS must be positive")
    if settings.smtp_max_attempts < 1:
        problems.append("SMTP_MAX_ATTEMPTS must be at least 1")
    return problems


def _bare_address(value: str) -> str:
    """`Astrofrekans <noreply@x.com>` -> `noreply@x.com`."""
    match = re.search(r"<([^>]+)>", value)
    return (match.group(1) if match else value).strip()


class Mailer(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def send(self, message: MailMessage) -> None: ...


class DisabledMailer:
    name = "disabled"

    @property
    def configured(self) -> bool:
        return False

    async def send(self, message: MailMessage) -> None:
        raise MailNotConfigured()


class LogMailer:
    """Local development: the message lands in the log, never in a mailbox."""

    name = "log"

    @property
    def configured(self) -> bool:
        return not settings.is_production

    async def send(self, message: MailMessage) -> None:
        if settings.is_production:  # pragma: no cover - refused at boot too
            raise MailNotConfigured()
        # Escaped to ASCII: a developer console that is not UTF-8 (Windows
        # cp1252) must not turn a Turkish "ş" into a failed "send".
        logger.info(
            "mail_logged_local_only",
            kind=message.kind,
            subject=message.subject.encode("ascii", "backslashreplace").decode(),
            body=message.text.encode("ascii", "backslashreplace").decode(),
        )


class MemoryMailer:
    """Tests: what would have been sent, in order."""

    name = "memory"

    def __init__(self) -> None:
        self.outbox: list[MailMessage] = []

    @property
    def configured(self) -> bool:
        return not settings.is_production

    async def send(self, message: MailMessage) -> None:
        self.outbox.append(message)


def build_email(message: MailMessage) -> EmailMessage:
    """Plain text first, HTML as the alternative. No tracking, no remote assets."""
    mail = EmailMessage()
    mail["From"] = settings.mail_from
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail["Date"] = formatdate(localtime=False, usegmt=True)
    mail["Message-ID"] = make_msgid(domain=_bare_address(settings.mail_from or "x@astrofrekans").split("@")[-1])
    # Tells mail systems this is automatic: no out-of-office replies to it.
    mail["Auto-Submitted"] = "auto-generated"
    for key, value in message.headers.items():
        mail[key] = value
    mail.set_content(message.text)
    if message.html:
        mail.add_alternative(message.html, subtype="html")
    return mail


def _classify(error: Exception) -> MailDeliveryFailed:
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return MailDeliveryFailed("smtp_auth_failed", transient=False, smtp_code=error.smtp_code)
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _ in error.recipients.values()]
        transient = bool(codes) and all(400 <= code < 500 for code in codes)
        return MailDeliveryFailed(
            "smtp_recipient_refused", transient=transient, smtp_code=codes[0] if codes else None
        )
    if isinstance(error, smtplib.SMTPResponseException):
        return MailDeliveryFailed(
            "smtp_reply_error",
            transient=400 <= error.smtp_code < 500,
            smtp_code=error.smtp_code,
        )
    if isinstance(error, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError)):
        return MailDeliveryFailed("smtp_disconnected", transient=True)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return MailDeliveryFailed("smtp_timeout", transient=True)
    if isinstance(error, ssl.SSLError):
        # A certificate or protocol mismatch will not fix itself.
        return MailDeliveryFailed("smtp_tls_error", transient=False)
    if isinstance(error, OSError):
        return MailDeliveryFailed("smtp_unreachable", transient=True)
    return MailDeliveryFailed("smtp_error", transient=False)


class SmtpMailer:
    name = "smtp"

    @property
    def configured(self) -> bool:
        return not smtp_config_problems()

    def _connect(self) -> smtplib.SMTP:
        timeout = settings.smtp_timeout_seconds
        context = ssl.create_default_context()
        if settings.smtp_ssl:
            return smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout, context=context
            )
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
        if settings.smtp_starttls:
            server.starttls(context=context)
        return server

    def _send_blocking(self, mail: EmailMessage) -> None:
        with self._connect() as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(mail)

    async def send(self, message: MailMessage) -> None:
        if not self.configured:
            raise MailNotConfigured()
        mail = build_email(message)
        attempts = settings.smtp_max_attempts
        for attempt in range(1, attempts + 1):
            try:
                # smtplib blocks; a slow relay must not stall the event loop.
                await asyncio.to_thread(self._send_blocking, mail)
            except Exception as error:  # noqa: BLE001 - classified below
                failure = _classify(error)
                logger.warning(
                    "mail_attempt_failed",
                    kind=message.kind,
                    provider=self.name,
                    attempt=attempt,
                    max_attempts=attempts,
                    reason=failure.reason,
                    smtp_code=failure.smtp_code,
                    error_class=type(error).__name__,
                    transient=failure.transient,
                )
                if not failure.transient or attempt == attempts:
                    raise failure from None
                await asyncio.sleep(settings.smtp_retry_backoff_seconds * (2 ** (attempt - 1)))
                continue
            logger.info("mail_sent", kind=message.kind, provider=self.name, attempt=attempt)
            return


_mailer: Mailer | None = None


def get_mailer() -> Mailer:
    global _mailer
    if _mailer is None:
        _mailer = {
            "smtp": SmtpMailer,
            "log": LogMailer,
            "memory": MemoryMailer,
        }.get(settings.mail_provider, DisabledMailer)()
    return _mailer


def set_mailer(mailer: Mailer | None) -> None:
    """Tests only. None resets to the configured provider."""
    global _mailer
    _mailer = mailer
