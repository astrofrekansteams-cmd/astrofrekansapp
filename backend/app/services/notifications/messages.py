"""What a push notification says, in the recipient's language.

The canonical event (`PushEvent`), its `data` (ids for the app to route on)
and its dedupe key never depend on language. Only the visible title and body
do, and they come from here - rendered for the user's `language` both when
the notification is queued and again when it is delivered, so a person who
switched language after a reminder was scheduled still reads it in the new
one.

Lock-screen rules from the outbox still hold: generic wording only - no
names, services, amounts, message text or birth data. Variants are picked
from a fixed list, never passed in as text.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat import PushEvent

SUPPORTED_LANGUAGES = ("tr", "en")
DEFAULT_LANGUAGE = "tr"
APP_NAME = "Astrofrekans"

# event -> {language: body}. The title is the app name in every language.
_BODIES: dict[PushEvent, dict[str, str]] = {
    # Report ready
    PushEvent.AI_REPORT_READY: {
        "tr": "Astro AI yorumun hazır.",
        "en": "Your Astro AI reading is ready.",
    },
    # Appointment reminder / changed / cancelled
    PushEvent.APPOINTMENT_BOOKED: {
        "tr": "Randevun oluşturuldu.",
        "en": "Your appointment is booked.",
    },
    PushEvent.APPOINTMENT_REMINDER: {
        "tr": "Yaklaşan bir randevun var.",
        "en": "You have an upcoming appointment.",
    },
    PushEvent.APPOINTMENT_CANCELLED: {
        "tr": "Bir randevun iptal edildi.",
        "en": "An appointment was cancelled.",
    },
    PushEvent.ORDER_STATUS_CHANGED: {
        "tr": "Siparişinde bir güncelleme var.",
        "en": "Your order was updated.",
    },
    # Expert message
    # Sent to both sides of a consultation, so it names neither.
    PushEvent.NEW_CHAT_MESSAGE: {
        "tr": "Yeni bir mesajın var.",
        "en": "You have a new message.",
    },
    # Payment / refund / subscription
    PushEvent.PAYMENT_SUCCEEDED: {"tr": "Ödemen alındı.", "en": "Your payment was received."},
    PushEvent.PAYMENT_FAILED: {
        "tr": "Ödemen tamamlanamadı.",
        "en": "Your payment did not go through.",
    },
    PushEvent.REFUND_PROCESSED: {"tr": "İaden işlendi.", "en": "Your refund was processed."},
    PushEvent.SUBSCRIPTION_RENEWED: {
        "tr": "Aboneliğin yenilendi.",
        "en": "Your subscription renewed.",
    },
    PushEvent.SUBSCRIPTION_EXPIRED: {
        "tr": "Aboneliğinin süresi doldu.",
        "en": "Your subscription has expired.",
    },
    # System / content
    PushEvent.DAILY_CONTENT: {"tr": "Bugünün gökyüzü hazır.", "en": "Today's sky is ready."},
    PushEvent.PROMOTION: {
        "tr": "Senin için yeni bir içerik var.",
        "en": "There is something new for you.",
    },
    # Calls
    PushEvent.INCOMING_CALL: {"tr": "Gelen görüşme", "en": "Incoming call"},
    PushEvent.CALL_CANCELLED: {"tr": "Görüşme iptal edildi.", "en": "The call was cancelled."},
    PushEvent.CALL_MISSED: {"tr": "Cevapsız görüşme", "en": "Missed call"},
    # Never shown: it only dismisses a ringing screen on other devices.
    PushEvent.CALL_ANSWERED: {
        "tr": "Görüşme başka bir cihazda yanıtlandı.",
        "en": "The call was answered on another device.",
    },
}

_VARIANT_BODIES: dict[tuple[PushEvent, str], dict[str, str]] = {
    (PushEvent.INCOMING_CALL, "audio"): {"tr": "Gelen sesli görüşme", "en": "Incoming voice call"},
    (PushEvent.INCOMING_CALL, "video"): {"tr": "Gelen görüntülü görüşme", "en": "Incoming video call"},
    (PushEvent.CALL_MISSED, "audio"): {"tr": "Cevapsız sesli görüşme", "en": "Missed voice call"},
    (PushEvent.CALL_MISSED, "video"): {"tr": "Cevapsız görüntülü görüşme", "en": "Missed video call"},
}

_FALLBACK = {"tr": "Bir bildirimin var.", "en": "You have a new notification."}


def normalise_language(language: str | None) -> str:
    code = (language or "").strip().lower()[:2]
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def push_text(
    event: PushEvent | str,
    *,
    language: str | None,
    variant: str | None = None,
) -> tuple[str, str]:
    """`(title, body)` for one event in one language. Never raises."""
    lang = normalise_language(language)
    try:
        canonical = event if isinstance(event, PushEvent) else PushEvent(event)
    except ValueError:
        return APP_NAME, _FALLBACK[lang]
    bodies = _VARIANT_BODIES.get((canonical, variant or "")) or _BODIES.get(canonical) or _FALLBACK
    return APP_NAME, bodies[lang]


async def user_language(session: AsyncSession, user_id: uuid.UUID) -> str:
    """The recipient's app language (the account's `language`)."""
    from app.db.models.user import UserProfile

    stored = await session.scalar(
        select(UserProfile.language).where(UserProfile.user_id == user_id)
    )
    return normalise_language(stored)


def localised_payload(payload: dict, *, event: str, language: str) -> dict:
    """The same payload with title/body in `language`. `data` is untouched."""
    title, body = push_text(event, language=language, variant=payload.get("variant"))
    return {**payload, "title": title, "body": body, "language": language}
