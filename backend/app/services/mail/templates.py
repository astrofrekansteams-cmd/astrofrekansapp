"""Email content, in the account's language.

Plain text is the canonical body; HTML is an alternative rendering of the
same words for clients that prefer it. The HTML has no remote images, no
tracking and no scripts - one link, escaped.
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from app.core.config import settings
from app.services.mail.mailer import MailMessage
from app.services.notifications.messages import normalise_language

_RESET = {
    "tr": {
        "subject": "Astrofrekans şifre sıfırlama",
        "intro": "Astrofrekans hesabın için şifre sıfırlama istendi.",
        "action": "Yeni şifre belirle",
        "validity": "Bağlantı {minutes} dakika geçerlidir ve bir kez kullanılabilir.",
        "ignore": "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin; şifren değişmez.",
        "fallback": "Düğme çalışmazsa bu adresi tarayıcına yapıştır:",
    },
    "en": {
        "subject": "Astrofrekans password reset",
        "intro": "A password reset was requested for your Astrofrekans account.",
        "action": "Choose a new password",
        "validity": "The link is valid for {minutes} minutes and works once.",
        "ignore": "If you did not ask for this, you can ignore this email; your password stays the same.",
        "fallback": "If the button does not work, paste this address into your browser:",
    },
}


def password_reset_link(token: str) -> str:
    """Put the reset token in the fragment, which is not sent to the web host."""
    base = settings.password_reset_url_base.split("#", 1)[0]
    return f"{base}#token={quote(token, safe='')}"


def password_reset_email(*, to: str, token: str, language: str | None) -> MailMessage:
    copy = _RESET[normalise_language(language)]
    minutes = settings.password_reset_ttl_minutes
    link = password_reset_link(token)
    validity = copy["validity"].format(minutes=minutes)
    text = (
        f"{copy['intro']}\n\n"
        f"{copy['action']}:\n{link}\n\n"
        f"{validity}\n\n"
        f"{copy['ignore']}\n"
    )
    safe_link = escape(link, quote=True)
    html = f"""<!doctype html>
<html lang="{normalise_language(language)}">
<body style="margin:0;padding:24px;background:#0d0b1e;font-family:Arial,Helvetica,sans-serif;color:#f4efe3">
  <div style="max-width:520px;margin:0 auto;background:#17142e;border-radius:12px;padding:28px">
    <h1 style="font-size:20px;margin:0 0 16px;color:#e8c77a">Astrofrekans</h1>
    <p style="font-size:15px;line-height:1.5;margin:0 0 20px">{escape(copy['intro'])}</p>
    <p style="margin:0 0 24px">
      <a href="{safe_link}" style="display:inline-block;background:#e8c77a;color:#1a1530;text-decoration:none;font-weight:bold;padding:12px 20px;border-radius:8px">{escape(copy['action'])}</a>
    </p>
    <p style="font-size:13px;line-height:1.5;margin:0 0 12px;color:#c9c3d9">{escape(validity)}</p>
    <p style="font-size:13px;line-height:1.5;margin:0 0 12px;color:#c9c3d9">{escape(copy['ignore'])}</p>
    <p style="font-size:12px;line-height:1.5;margin:16px 0 0;color:#9a93ad">{escape(copy['fallback'])}<br><span style="word-break:break-all">{safe_link}</span></p>
  </div>
</body>
</html>
"""
    return MailMessage(
        to=to,
        subject=copy["subject"],
        text=text,
        html=html,
        kind="password_reset",
    )
