"""Call lifecycle push: the right transport per device, once per device.

Ordinary notifications (a chat message, a booking) keep the B9 path: one FCM
multicast with a `notification` block. Call events are different in kind -
they are a ringing phone, then the end of one - and the platforms have
dedicated, stricter channels for them:

| Event | Android (FCM token) | iOS PushKit VoIP token | iOS FCM token | web |
| --- | --- | --- | --- | --- |
| `incoming_call` | data-only, HIGH, short TTL | APNs `voip` | alert, only if the user has no VoIP token | alert |
| `call_cancelled` / `call_answered` | data-only, HIGH | never (Apple: no pushes to cancel) | background update, best effort | - |
| `call_missed` | data-only, HIGH | never | alert (a missed-call notice) | alert |

Every push is a **presentation hint**. It authorises nothing: answering goes
`GET /calls/{id}` -> `POST /calls/{id}/join` -> LiveKit, through B10's checks.

Delivery is recorded per device (`notification_deliveries`, unique per outbox
row and device): one logical delivery per device, however many physical
attempts it takes. Retries resend only what is not yet delivered. Delivery is
**at least once**: a delivery left `sending` by a worker that died is claimed
again when its lease lapses, so a crash never silently loses a ring. The rare
duplicate that produces is suppressed on the device by `call_id` +
`event_version` (and on iOS by the CallKit UUID derived from `call_id`).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.chat import NotificationDelivery, NotificationOutbox, PushDevice
from app.domain.chat import DevicePlatform, PushCredential, PushEvent
from app.services.firebase.provider import (
    DataPushMessage,
    FirebaseError,
    FirebaseNotConfigured,
    FirebaseProviders,
    PushMessage,
)
from app.services.notifications.apns import AppleVoipPushProvider
from app.services.notifications.devices import DeviceService, mask_token
from app.services.notifications.outbox import OutboxService

from app.services.notifications.messages import localised_payload, user_language
logger = get_logger(__name__)


class CallTransport(StrEnum):
    APNS_VOIP = "apns_voip"
    FCM_CALL_DATA = "fcm_call_data"
    FCM_BACKGROUND = "fcm_background"
    FCM_ALERT = "fcm_alert"


# Within one ring, later lifecycle events outrank earlier ones.
_EVENT_RANK = {
    PushEvent.INCOMING_CALL: 0,
    PushEvent.CALL_ANSWERED: 1,
    PushEvent.CALL_CANCELLED: 2,
    PushEvent.CALL_MISSED: 3,
}


def call_event_fields(
    event: PushEvent,
    *,
    call_id: str,
    call_type: str,
    ringing_at: datetime | None,
) -> tuple[dict[str, str], datetime | None]:
    """The whole call push payload, and when it stops being worth sending.

    Minimal by construction: the call id and its type, an ordering version,
    and - for a ring - when it stops ringing. Never a name, a service, an
    order, an amount or a LiveKit token.

    `event_version` = ring start (ms) * 4 + rank. A later ring always outranks
    anything from an earlier one, and within a ring answered/cancelled/missed
    outrank the ring itself - so a client keeping the highest version per
    `call_id` never lets a late `incoming_call` resurrect a call that ended,
    whatever order FCM delivers in (it does not guarantee one).

    Expiry follows B10's ring timeout, the one lifecycle clock: a ring is
    worthless after it, and so is a dismissal of it. A missed-call notice has
    no expiry.
    """
    ring_ms = int(_aware(ringing_at).timestamp() * 1000) if ringing_at else 0
    fields = {
        "call_id": call_id,
        "call_type": call_type,
        "event_version": str(ring_ms * 4 + _EVENT_RANK[event]),
    }
    ring_end = (
        _aware(ringing_at) + timedelta(seconds=settings.call_ring_timeout_seconds)
        if ringing_at
        else None
    )
    if event is PushEvent.INCOMING_CALL:
        if ring_end is not None:
            fields["expires_at"] = str(int(ring_end.timestamp()))
        return fields, ring_end
    if event in (PushEvent.CALL_CANCELLED, PushEvent.CALL_ANSWERED):
        return fields, ring_end
    return fields, None


def route(event: PushEvent, device: PushDevice, *, user_has_voip: bool) -> CallTransport | None:
    """Which transport a call event takes to one device, or None for none."""
    if device.credential_type == PushCredential.APNS_VOIP.value:
        # PushKit: every VoIP push must be reported to CallKit as a new
        # incoming call, and Apple says not to push again to cancel it.
        return CallTransport.APNS_VOIP if event is PushEvent.INCOMING_CALL else None

    platform = device.platform
    if platform == DevicePlatform.ANDROID.value:
        return CallTransport.FCM_CALL_DATA
    if platform == DevicePlatform.IOS.value:
        if event is PushEvent.INCOMING_CALL:
            # Rings on iOS go through PushKit. An ordinary alert is the
            # fallback only for a user with no VoIP registration at all (an
            # app version from before it), so a registered iPhone never gets
            # both a CallKit ring and a banner.
            return None if user_has_voip else CallTransport.FCM_ALERT
        if event is PushEvent.CALL_MISSED:
            return CallTransport.FCM_ALERT
        return CallTransport.FCM_BACKGROUND
    if event in (PushEvent.INCOMING_CALL, PushEvent.CALL_MISSED):
        return CallTransport.FCM_ALERT
    return None


def _aware(moment: datetime | None) -> datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


@dataclass(slots=True, frozen=True)
class CallDeliveryOutcome:
    delivered: int
    failed: int
    retired_tokens: int
    skipped_reason: str | None = None


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True, frozen=True)
class _Claim:
    """What one send needs, copied out of the ORM before any network call."""

    delivery_id: uuid.UUID
    attempt: int  # the fencing token: only this attempt may record its result
    device_id: uuid.UUID
    token: str
    environment: str | None
    transport: CallTransport


@dataclass(slots=True, frozen=True)
class _Result:
    claim: _Claim
    status: DeliveryStatus
    error_code: str | None = None
    dead: bool = False


class CallPushSender:
    def __init__(
        self,
        session: AsyncSession,
        firebase: FirebaseProviders,
        voip: AppleVoipPushProvider,
    ) -> None:
        self.session = session
        self.firebase = firebase
        self.voip = voip
        self.outbox = OutboxService(session)
        self.devices = DeviceService(session)

    async def deliver(self, row: NotificationOutbox) -> CallDeliveryOutcome:
        """Claim this row's due deliveries, send them, record what happened.

        Three steps, and the network is only ever in the middle one:

        1. **Claim** (one transaction, committed): due deliveries - `pending`,
           or `sending` whose lease has lapsed - are locked `FOR UPDATE SKIP
           LOCKED`, set `sending` with a lease and `attempts + 1`.
        2. **Send**, with no transaction open.
        3. **Record**: each result is written only if the delivery is still
           this attempt's (`attempts` is the fence). A worker that lost its
           lease cannot overwrite the one that took over.

        At least once: a worker that dies after sending but before recording
        leaves `sending`; when the lease lapses the delivery is sent again.
        The duplicate is suppressed on the device by `call_id` +
        `event_version`.
        """
        now = datetime.now(UTC)
        row_id = row.id
        user_id = row.user_id
        # Visible text (missed-call notice, iOS fallback alert) in the
        # callee's current language. The data a ringing screen reads is
        # untouched.
        payload = localised_payload(
            dict(row.payload or {}),
            event=row.event_type,
            language=await user_language(self.session, row.user_id),
        )
        expires_at = _aware(row.expires_at)
        lease_until = _aware(row.lease_expires_at) or now + timedelta(
            seconds=settings.push_outbox_lease_seconds
        )

        if expires_at is not None and now >= expires_at:
            await self._close_open(row_id, error_code="skipped_expired")
            await self.outbox.mark_expired(row)
            return CallDeliveryOutcome(0, 0, 0, skipped_reason="skipped_expired")

        event = PushEvent(row.event_type)
        devices = await self.devices.enabled_devices(user_id)
        user_has_voip = any(
            device.credential_type == PushCredential.APNS_VOIP.value for device in devices
        )
        targets = [
            (device, transport)
            for device in devices
            if (transport := route(event, device, user_has_voip=user_has_voip)) is not None
        ]
        await self._ensure(row_id, targets)
        claims = await self._claim(row_id, now, lease_until)

        data = {str(key): str(value) for key, value in (payload.get("data") or {}).items()}
        results = await self._send(claims, data, payload, expires_at)
        retired = await self._record(results)
        return await self._finish(row, retired)

    # --------------------------------------------------------- claiming

    async def _ensure(self, row_id: uuid.UUID, targets) -> None:  # noqa: ANN001
        """One logical delivery row per target device. Never two."""
        existing = set(
            await self.session.scalars(
                select(NotificationDelivery.device_id).where(NotificationDelivery.outbox_id == row_id)
            )
        )
        for device, transport in targets:
            if device.id in existing:
                continue
            try:
                async with self.session.begin_nested():
                    self.session.add(
                        NotificationDelivery(
                            outbox_id=row_id,
                            device_id=device.id,
                            transport=transport.value,
                            status=DeliveryStatus.PENDING.value,
                            attempts=0,
                        )
                    )
                    await self.session.flush()
            except IntegrityError:
                # Another worker recorded this target first: the same logical
                # delivery, which it or we will claim below.
                pass

    async def _claim(self, row_id: uuid.UUID, now: datetime, lease_until: datetime) -> list[_Claim]:
        statement = (
            select(NotificationDelivery, PushDevice)
            .join(PushDevice, PushDevice.id == NotificationDelivery.device_id)
            .where(
                NotificationDelivery.outbox_id == row_id,
                or_(
                    NotificationDelivery.status == DeliveryStatus.PENDING.value,
                    and_(
                        NotificationDelivery.status == DeliveryStatus.SENDING.value,
                        or_(
                            NotificationDelivery.lease_until.is_(None),
                            NotificationDelivery.lease_until <= now,
                        ),
                    ),
                ),
            )
            .order_by(NotificationDelivery.created_at)
        )
        if self.session.bind is not None and self.session.bind.dialect.name != "sqlite":
            statement = statement.with_for_update(skip_locked=True, of=NotificationDelivery)

        claims: list[_Claim] = []
        for delivery, device in (await self.session.execute(statement)).all():
            if not device.enabled:
                delivery.status = DeliveryStatus.SKIPPED.value
                delivery.error_code = "device_disabled"
                delivery.lease_until = None
                continue
            delivery.status = DeliveryStatus.SENDING.value
            delivery.attempts += 1
            delivery.lease_until = lease_until
            delivery.last_attempt_at = now
            claims.append(
                _Claim(
                    delivery_id=delivery.id,
                    attempt=delivery.attempts,
                    device_id=device.id,
                    token=device.token,
                    environment=device.apns_environment,
                    transport=CallTransport(delivery.transport),
                )
            )
        # Committed before anything is sent: the claim is visible, and no
        # transaction is held open across a provider call.
        await self.session.commit()
        return claims

    # ---------------------------------------------------------- sending

    async def _send(self, claims, data, payload, expires_at) -> list[_Result]:  # noqa: ANN001
        """Network only. Touches no database state."""
        now = datetime.now(UTC)
        if expires_at is not None and now >= expires_at:
            return [_Result(c, DeliveryStatus.SKIPPED, "skipped_expired") for c in claims]
        ttl = max(1, int((expires_at - now).total_seconds())) if expires_at else None

        # Every provider operation runs at once, each under the same hard
        # timeout, so the whole send takes about one timeout at most - always
        # inside the claim's lease (CALL_PUSH_SEND_TIMEOUT_SECONDS +
        # margin <= CALL_PUSH_LEASE_SECONDS, checked at startup).
        groups: dict[CallTransport, list[_Claim]] = {}
        for claim in claims:
            groups.setdefault(claim.transport, []).append(claim)
        operations = []
        for transport, group in groups.items():
            if transport is CallTransport.APNS_VOIP:
                operations += [self._send_voip(claim, data, expires_at, now) for claim in group]
            else:
                operations.append(self._send_fcm(transport, group, data, payload, ttl))
        results: list[_Result] = []
        for batch in await asyncio.gather(*operations):
            results += batch
        return results

    async def _send_voip(self, claim, data, expires_at, now) -> list[_Result]:  # noqa: ANN001
        """One APNs VoIP request, bounded by CALL_PUSH_SEND_TIMEOUT_SECONDS."""
        if settings.apns_voip_expiration_seconds <= 0:
            expiration = 0
        else:
            bound = int(now.timestamp()) + settings.apns_voip_expiration_seconds
            expiration = min(bound, int(expires_at.timestamp())) if expires_at else bound
        try:
            result = await asyncio.wait_for(
                self.voip.send_voip(
                    claim.token,
                    data,
                    environment=claim.environment or settings.apns_environment,
                    expiration=expiration,
                    # Stable across retries: the logical delivery, not the
                    # attempt. APNs uses it to report errors; it does not
                    # deduplicate on it.
                    apns_id=str(claim.delivery_id),
                ),
                timeout=settings.call_push_send_timeout_seconds,
            )
        except TimeoutError:
            # Unknown whether APNs got it. Retried: at least once.
            logger.warning(
                "call_push_voip_timeout",
                delivery_id=str(claim.delivery_id),
                attempt=claim.attempt,
            )
            return [_Result(claim, DeliveryStatus.PENDING, "provider_timeout")]

        logger.info(
            "call_push_voip",
            delivery_id=str(claim.delivery_id),
            attempt=claim.attempt,
            outcome=result.outcome,
            reason=result.reason,
            token_fingerprint=mask_token(claim.token),
        )
        if result.outcome == "sent":
            return [_Result(claim, DeliveryStatus.DELIVERED)]
        if result.outcome == "invalid_token":
            return [_Result(claim, DeliveryStatus.FAILED, _code("apns", result.reason), dead=True)]
        if result.outcome == "retry":
            return [_Result(claim, DeliveryStatus.PENDING, _code("apns", result.reason))]
        if result.outcome == "not_configured":
            return [_Result(claim, DeliveryStatus.SKIPPED, "provider_not_configured")]
        return [_Result(claim, DeliveryStatus.FAILED, _code("apns", result.reason))]

    async def _send_fcm(self, transport, claims, data, payload, ttl) -> list[_Result]:  # noqa: ANN001
        tokens = [claim.token for claim in claims]
        try:
            if transport is CallTransport.FCM_ALERT:
                operation = self.firebase.push.send_multicast(
                    tokens,
                    PushMessage(
                        title=str(payload.get("title") or "Astrofrekans"),
                        body=str(payload.get("body") or ""),
                        data=data,
                        collapse_key=f"call:{data.get('call_id', '')}",
                        ttl_seconds=ttl,
                    ),
                )
            else:
                operation = self.firebase.push.send_data(
                    tokens,
                    DataPushMessage(
                        data=data,
                        # HIGH: each of these starts or ends a visible ringing
                        # screen or posts a missed-call notice.
                        android_priority="high",
                        ttl_seconds=ttl,
                        # Only undelivered messages collapse: a device offline
                        # through a whole call gets the latest event for it,
                        # not a stale ring followed by its cancellation.
                        collapse_key=f"call:{data.get('call_id', '')}",
                        apns_background=transport is CallTransport.FCM_BACKGROUND,
                    ),
                )
            # firebase-admin's own HTTP timeout is 120 s (and B9 relies on it
            # for ordinary pushes); a call push is bounded here instead.
            result = await asyncio.wait_for(
                operation, timeout=settings.call_push_send_timeout_seconds
            )
        except TimeoutError:
            # The SDK call may still complete in its thread: unknown, so
            # retried - at least once.
            return [_Result(c, DeliveryStatus.PENDING, "provider_timeout") for c in claims]
        except FirebaseNotConfigured:
            return [_Result(c, DeliveryStatus.SKIPPED, "provider_not_configured") for c in claims]
        except FirebaseError:
            return [_Result(c, DeliveryStatus.PENDING, "fcm_unavailable") for c in claims]

        invalid = set(result.invalid_tokens)
        retry = set(result.retry_tokens)
        results = []
        for claim in claims:
            if claim.token in invalid:
                results.append(_Result(claim, DeliveryStatus.FAILED, "fcm_unregistered", dead=True))
            elif claim.token in retry or (result.success_count == 0 and result.retryable):
                results.append(_Result(claim, DeliveryStatus.PENDING, "fcm_transient"))
            else:
                results.append(_Result(claim, DeliveryStatus.DELIVERED))
        return results

    # -------------------------------------------------------- recording

    async def _record(self, results: list[_Result]) -> int:
        now = datetime.now(UTC)
        retired = 0
        for result in results:
            claim = result.claim
            written = await self.session.execute(
                update(NotificationDelivery)
                .where(
                    NotificationDelivery.id == claim.delivery_id,
                    NotificationDelivery.attempts == claim.attempt,
                    NotificationDelivery.status == DeliveryStatus.SENDING.value,
                )
                .values(
                    status=result.status.value,
                    error_code=result.error_code,
                    lease_until=None,
                    sent_at=now if result.status is DeliveryStatus.DELIVERED else None,
                )
                .execution_options(synchronize_session=False)
            )
            if written.rowcount == 0:
                # Our lease lapsed and another attempt owns the delivery now.
                # The physical send happened; the record is theirs to write.
                logger.warning(
                    "call_push_result_superseded",
                    delivery_id=str(claim.delivery_id),
                    attempt=claim.attempt,
                )
            if result.dead:
                if claim.transport is CallTransport.APNS_VOIP:
                    device = await self.session.get(PushDevice, claim.device_id)
                    if device is not None and device.enabled:
                        reason = (result.error_code or "apns_invalid").lower()
                        await self.devices.disable_device(device, reason=reason)
                        retired += 1
                elif await self.devices.disable_token(claim.token, reason="unregistered"):
                    retired += 1
        await self.session.flush()
        return retired

    async def _close_open(self, row_id: uuid.UUID, *, error_code: str) -> None:
        """Nothing still open for this row will ever be sent."""
        await self.session.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.outbox_id == row_id,
                NotificationDelivery.status.in_(
                    [DeliveryStatus.PENDING.value, DeliveryStatus.SENDING.value]
                ),
            )
            .values(status=DeliveryStatus.SKIPPED.value, error_code=error_code, lease_until=None)
            .execution_options(synchronize_session=False)
        )

    # -------------------------------------------------------- finishing

    async def _finish(self, row: NotificationOutbox, retired: int) -> CallDeliveryOutcome:
        rows = (
            await self.session.execute(
                select(NotificationDelivery.status, NotificationDelivery.error_code).where(
                    NotificationDelivery.outbox_id == row.id
                )
            )
        ).all()
        counts = Counter(status for status, _ in rows)
        delivered = counts[DeliveryStatus.DELIVERED.value]
        others = len(rows) - delivered

        if not rows:
            await self.outbox.mark_skipped(row, reason="no_enabled_devices")
            return CallDeliveryOutcome(0, 0, retired, skipped_reason="no_enabled_devices")
        if counts[DeliveryStatus.SENDING.value]:
            # In flight under another worker's live lease. The row stays with
            # whoever finishes it - or returns to the queue when that lease
            # lapses.
            await self.session.commit()
            return CallDeliveryOutcome(delivered, others, retired)
        if counts[DeliveryStatus.PENDING.value]:
            if row.attempts < row.max_attempts:
                await self.outbox.mark_failed(row, error_code="call_delivery_retry", retryable=True)
                return CallDeliveryOutcome(delivered, others, retired)
            await self._close_pending_as_failed(row.id)
        if delivered:
            await self.outbox.mark_sent(row, delivered=delivered, failed=others)
        elif all(
            status == DeliveryStatus.SKIPPED.value and code == "provider_not_configured"
            for status, code in rows
        ):
            # Not a failure of the notification: the transport is not set up
            # here (no APNs key, or no Firebase). Not retried.
            await self.outbox.mark_skipped(row, reason="provider_not_configured")
            return CallDeliveryOutcome(0, others, retired, skipped_reason="provider_not_configured")
        else:
            await self.outbox.mark_failed(row, error_code="all_deliveries_failed", retryable=False)
        return CallDeliveryOutcome(delivered, others, retired)

    async def _close_pending_as_failed(self, row_id: uuid.UUID) -> None:
        await self.session.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.outbox_id == row_id,
                NotificationDelivery.status == DeliveryStatus.PENDING.value,
            )
            .values(status=DeliveryStatus.FAILED.value, error_code="max_attempts", lease_until=None)
            .execution_options(synchronize_session=False)
        )


def _code(prefix: str, reason: str | None) -> str:
    return f"{prefix}_{reason or 'error'}"[:60]
