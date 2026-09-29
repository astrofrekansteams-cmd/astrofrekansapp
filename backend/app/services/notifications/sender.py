"""Turning an outbox row into a delivered notification.

Separated from the worker loop so the delivery decision - which devices, what
counts as a failure, which tokens to retire - is testable without a running
process.

Two rules that are easy to get wrong:

* **A dead token is retired, not retried.** FCM's `UnregisteredError` means the
  app was uninstalled or the token rotated. Retrying it fails forever and the
  outbox row never clears.
* **No enabled devices is not a failure.** A user with notifications off has
  nothing to deliver to. Marking that `failed` would fill the failure metric
  with people exercising a preference.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notifications.preferences import notification_allowed
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.chat import NotificationOutbox
from app.domain.chat import CALL_EVENTS
from app.services.firebase.provider import (
    FirebaseError,
    FirebaseNotConfigured,
    FirebaseProviders,
    PushMessage,
)
from app.services.notifications.apns import AppleVoipPushProvider, get_voip_provider
from app.services.notifications.call_delivery import CallPushSender
from app.services.notifications.devices import DeviceService
from app.services.notifications.messages import localised_payload, user_language
from app.services.notifications.outbox import OutboxService

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class DeliveryOutcome:
    delivered: int
    failed: int
    retired_tokens: int
    skipped_reason: str | None = None

    @property
    def was_skipped(self) -> bool:
        return self.skipped_reason is not None


class NotificationSender:
    def __init__(
        self,
        session: AsyncSession,
        firebase: FirebaseProviders,
        voip: AppleVoipPushProvider | None = None,
    ) -> None:
        self.session = session
        self.firebase = firebase
        self.voip = voip or get_voip_provider()
        self.outbox = OutboxService(session)
        self.devices = DeviceService(session)

    async def deliver(self, row: NotificationOutbox) -> DeliveryOutcome:
        """Send one outbox row, and record what happened to it.

        Call lifecycle events take the per-device call path (APNs VoIP,
        data-only FCM); everything else takes the B9 notification path below,
        unchanged.
        """
        if row.event_type in {event.value for event in CALL_EVENTS}:
            outcome = await CallPushSender(self.session, self.firebase, self.voip).deliver(row)
            return DeliveryOutcome(
                outcome.delivered, outcome.failed, outcome.retired_tokens, outcome.skipped_reason
            )

        # The user's switches. Calls took the path above and never get here.
        if not await notification_allowed(self.session, row.user_id, row.event_type):
            outcome = DeliveryOutcome(0, 0, 0, skipped_reason="user_preference_off")
            await self.outbox.mark_skipped(row, reason=outcome.skipped_reason or "")
            return outcome

        tokens = await self.devices.active_tokens(row.user_id)
        if not tokens:
            outcome = DeliveryOutcome(0, 0, 0, skipped_reason="no_enabled_devices")
            await self.outbox.mark_skipped(row, reason=outcome.skipped_reason or "")
            return outcome

        # Text in the recipient's language as of now; data exactly as queued,
        # plus the inbox id so opening the push marks the same record read.
        payload = localised_payload(
            row.payload or {},
            event=row.event_type,
            language=await user_language(self.session, row.user_id),
        )
        data = {
            str(key): str(value)
            for key, value in (payload.get("data") or {}).items()
        }
        data.setdefault("notification_id", str(row.id))
        message = PushMessage(
            title=str(payload.get("title") or "Astrofrekans"),
            body=str(payload.get("body") or ""),
            data=data,
            # Several messages in one conversation collapse into one badge
            # rather than a stack of identical lines.
            collapse_key=(
                f"conversation:{row.conversation_id}"
                if row.conversation_id
                else None
            ),
        )

        try:
            result = await self.firebase.push.send_multicast(tokens, message)
        except FirebaseNotConfigured:
            # Nothing is wrong with the notification; the server simply cannot
            # send it yet. Worth retrying when configuration arrives.
            await self.outbox.mark_failed(
                row, error_code="firebase_not_configured", retryable=True
            )
            return DeliveryOutcome(0, len(tokens), 0)
        except FirebaseError as exc:
            await self.outbox.mark_failed(
                row,
                error_code=getattr(exc, "code", "firebase_unavailable"),
                retryable=True,
            )
            return DeliveryOutcome(0, len(tokens), 0)

        retired = 0
        for token in result.invalid_tokens:
            if await self.devices.disable_token(token, reason="unregistered"):
                retired += 1

        if result.success_count == 0 and result.failure_count:
            await self.outbox.mark_failed(
                row,
                error_code="all_deliveries_failed",
                # Only worth retrying if something transient happened. If every
                # token was simply dead, retrying changes nothing.
                retryable=result.retryable,
            )
            return DeliveryOutcome(0, result.failure_count, retired)

        await self.outbox.mark_sent(
            row, delivered=result.success_count, failed=result.failure_count
        )
        return DeliveryOutcome(result.success_count, result.failure_count, retired)

    def should_notify_sender(self) -> bool:
        """Whether a sender's own other devices get the notification.

        Off by default. Somebody who just typed a message does not need their
        tablet to buzz about it, and the cross-device sync a client wants is a
        Firestore listener's job rather than a push notification's.
        """
        return settings.push_notify_sender_other_devices
