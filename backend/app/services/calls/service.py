"""The call lifecycle: one service, every transition.

Three things drive a call, and all three come through here:

* **People** - create, join, end. Authorised in full every time, including
  every token reissue.
* **The provider** - webhooks saying who joined and who left. The only source
  of "both parties are in the room", so the only thing that can make a call
  ACTIVE. A client saying "we started" changes nothing.
* **The clock** - ring timeouts, reconnect grace, the join window closing, the
  hard duration ceiling. Evaluated lazily on every read and webhook, and by the
  call worker for calls nobody is looking at.

Every status change goes through `_transition`, which consults the table in
`app.domain.calls`. No route assigns a status.

Rows are locked (`SELECT ... FOR UPDATE` on Postgres) before they are changed,
because a webhook, a user tapping "end" and the worker can all arrive for the
same call in the same second.
"""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFound
from app.core.logging import get_logger
from app.db.models.calls import CallParticipant, CallProviderEvent, CallSession
from app.db.models.chat import ExpertConversation, NotificationOutbox
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.calls import (
    LIVE_STATUSES,
    PUBLISH_SOURCES,
    CallEndReason,
    CallStatus,
    CallType,
    ParticipantRole,
    ParticipantStatus,
    ProviderEventType,
    can_transition,
)
from app.domain.chat import PushEvent
from app.services.calls import policy
from app.services.calls.policy import (
    CallAlreadyEnded,
    CallNotFound,
    CallWindow,
    CallWindowClosed,
)
from app.services.calls.provider import (
    CallProviderNotConfigured,
    CallProviderUnavailable,
    JoinToken,
    ProviderWebhookEvent,
    RealtimeCommunicationProvider,
    RoomSpec,
    TokenRequest,
)
from app.services.notifications.outbox import OutboxService
from app.services.notifications.call_delivery import call_event_fields

logger = get_logger(__name__)

MAX_PARTICIPANTS = 2

_TRANSITION_EVENTS = {
    CallStatus.WAITING: "call_waiting",
    CallStatus.RINGING: "call_ringing",
    CallStatus.ACTIVE: "call_started",
    CallStatus.ENDED: "call_ended",
    CallStatus.MISSED: "call_missed",
    CallStatus.CANCELLED: "call_cancelled",
    CallStatus.FAILED: "call_failed",
}


def _fingerprint(value: str) -> str:
    """For logging an identity we did not issue: enough to correlate, no more."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _new_room_name() -> str:
    # Random, not derived from anything. `call_<24 hex>` says nothing about
    # who, what or when.
    return f"call_{secrets.token_hex(12)}"


def _new_identity() -> str:
    return f"p_{secrets.token_hex(12)}"


@dataclass(slots=True)
class Entitlement:
    """Everything the policy needs, loaded once."""

    order: ServiceOrder
    definition: ServiceDefinition
    expert: Expert | None
    offering: ExpertService | None
    appointment: Appointment | None
    user_account: User | None
    expert_account: User | None


@dataclass(slots=True)
class JoinGrant:
    call: CallSession
    participant: CallParticipant
    token: JoinToken
    client_url: str


class CallService:
    def __init__(
        self, session: AsyncSession, provider: RealtimeCommunicationProvider
    ) -> None:
        self.session = session
        self.provider = provider
        self.outbox = OutboxService(session)

    # ================================================================ loading

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    async def _lock(self, call_id: uuid.UUID) -> CallSession | None:
        statement = select(CallSession).where(CallSession.id == call_id)
        if self._locks:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def _participants(
        self, call: CallSession
    ) -> dict[ParticipantRole, CallParticipant]:
        rows = await self.session.scalars(
            select(CallParticipant).where(CallParticipant.call_session_id == call.id)
        )
        return {ParticipantRole(row.role): row for row in rows}

    async def _entitlement(self, order_id: uuid.UUID) -> Entitlement | None:
        order = await self.session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == order_id)
        )
        if order is None:
            return None
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == order.service_definition_id
            )
        )
        expert = (
            await self.session.scalar(select(Expert).where(Expert.id == order.expert_id))
            if order.expert_id
            else None
        )
        offering = (
            await self.session.scalar(
                select(ExpertService).where(ExpertService.id == order.expert_service_id)
            )
            if order.expert_service_id
            else None
        )
        appointment = await self.session.scalar(
            select(Appointment)
            .where(Appointment.service_order_id == order.id)
            .order_by(Appointment.created_at.desc())
            .limit(1)
        )
        user_account = await self.session.scalar(
            select(User).where(User.id == order.user_id)
        )
        expert_account = (
            await self.session.scalar(select(User).where(User.id == expert.user_id))
            if expert
            else None
        )
        return Entitlement(
            order=order,
            definition=definition,
            expert=expert,
            offering=offering,
            appointment=appointment,
            user_account=user_account,
            expert_account=expert_account,
        )

    def _authorise(
        self,
        entitlement: Entitlement,
        call_type: CallType,
        *,
        requested_appointment_id: uuid.UUID | None = None,
    ) -> None:
        policy.check_entitlement(
            order=entitlement.order,
            definition=entitlement.definition,
            expert=entitlement.expert,
            offering=entitlement.offering,
            appointment=entitlement.appointment,
            call_type=call_type,
            user_account=entitlement.user_account,
            expert_account=entitlement.expert_account,
            requested_appointment_id=requested_appointment_id,
        )

    @staticmethod
    def _window(call: CallSession) -> CallWindow:
        return policy.window_for(
            call.scheduled_start_at,
            call.scheduled_end_at,
            created_at=call.created_at,
        )

    async def _live_for_order(self, order_id: uuid.UUID) -> CallSession | None:
        return await self.session.scalar(
            select(CallSession).where(
                CallSession.order_id == order_id,
                CallSession.status.in_([status.value for status in LIVE_STATUSES]),
            )
        )

    # ============================================================ membership

    async def get_for_member(
        self, caller: User, call_id: uuid.UUID, *, now: datetime | None = None
    ) -> tuple[CallSession, CallParticipant]:
        """A call the caller is one of the two people in. Anyone else: 404.

        404 rather than 403 so a guessed id does not confirm a call exists.
        Advances the clock on the way, so what is returned is current.
        """
        call = await self._lock(call_id)
        if call is None:
            raise CallNotFound()
        participant = await self._participant_for(call, caller)
        await self.advance(call, now or policy.utcnow())
        return call, participant

    async def _participant_for(
        self, call: CallSession, caller: User
    ) -> CallParticipant:
        # Membership is the account on the session - `user_id` or the
        # expert's `expert_user_id` - never an expert profile id.
        if caller.id not in (call.user_id, call.expert_user_id):
            raise CallNotFound()
        participant = await self.session.scalar(
            select(CallParticipant).where(
                CallParticipant.call_session_id == call.id,
                CallParticipant.user_id == caller.id,
            )
        )
        if participant is None:  # pragma: no cover - created with the session
            raise CallNotFound()
        return participant

    async def list_for_user(
        self,
        caller: User,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[CallSession]:
        statement = select(CallSession).where(
            or_(
                CallSession.user_id == caller.id,
                CallSession.expert_user_id == caller.id,
            )
        )
        if before is not None:
            statement = statement.where(CallSession.created_at < before)
        return list(
            await self.session.scalars(
                statement.order_by(CallSession.created_at.desc()).limit(limit)
            )
        )

    # ================================================================ create

    async def create(
        self,
        caller: User,
        *,
        order_id: uuid.UUID,
        call_type: CallType,
        appointment_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> tuple[CallSession, bool]:
        """Open the call for an order, or return the one already open.

        Either party may start it. Whoever starts second gets the same session,
        not a second room: `uq_call_sessions_live_order` allows one live call
        per order, and a losing concurrent insert reads the winner's row.

        Returns `(call, created)`. A call whose room could not be provisioned
        comes back FAILED - recorded, not rolled back - and the caller reports
        `call_provider_unavailable`. The order is untouched.
        """
        now = now or policy.utcnow()
        entitlement = await self._entitlement(order_id)
        if entitlement is None:
            raise NotFound("Order not found.")
        order = entitlement.order

        # Membership before anything else, so an outsider learns nothing about
        # the order - not even whether it is callable.
        is_user = caller.id == order.user_id
        is_expert = (
            entitlement.expert is not None and caller.id == entitlement.expert.user_id
        )
        if not (is_user or is_expert):
            raise NotFound("Order not found.")

        existing = await self._live_for_order(order.id)
        if existing is not None:
            existing = await self._lock(existing.id)
            await self.advance(existing, now)
            if CallStatus(existing.status).is_live:
                return existing, False

        self._authorise(
            entitlement, call_type, requested_appointment_id=appointment_id
        )

        appointment = entitlement.appointment
        start = appointment.starts_at_utc if appointment else None
        end = appointment.ends_at_utc if appointment else None
        window = policy.window_for(start, end, created_at=now)
        if window.closes_at is not None and now > window.closes_at:
            raise CallWindowClosed(details={"closed_at": window.closes_at.isoformat()})

        before_window = window.opens_at is not None and now < window.opens_at
        conversation_id = await self.session.scalar(
            select(ExpertConversation.id).where(
                ExpertConversation.order_id == order.id
            )
        )

        call = CallSession(
            id=uuid.uuid4(),
            order_id=order.id,
            appointment_id=appointment.id if appointment else None,
            conversation_id=conversation_id,
            user_id=order.user_id,
            expert_id=entitlement.expert.id,
            expert_user_id=entitlement.expert.user_id,
            created_by_user_id=caller.id,
            call_type=call_type.value,
            status=(
                CallStatus.SCHEDULED.value if before_window else CallStatus.WAITING.value
            ),
            provider=self.provider.name,
            provider_room_name=_new_room_name(),
            scheduled_start_at=start,
            scheduled_end_at=end,
            recording_enabled=False,
        )
        participants = [
            CallParticipant(
                call_session_id=call.id,
                user_id=account_id,
                role=role.value,
                provider_identity=_new_identity(),
                status=ParticipantStatus.INVITED.value,
                connection_count=0,
                token_issued_count=0,
            )
            for role, account_id in (
                (ParticipantRole.USER, order.user_id),
                (ParticipantRole.EXPERT, entitlement.expert.user_id),
            )
        ]

        try:
            # A savepoint, so losing the race undoes only this insert.
            async with self.session.begin_nested():
                self.session.add(call)
                await self.session.flush()
                self.session.add_all(participants)
                await self.session.flush()
        except IntegrityError:
            winner = await self._live_for_order(order.id)
            if winner is None:  # pragma: no cover - the index says otherwise
                raise
            logger.info("call_create_joined_existing", call_id=str(winner.id))
            return winner, False

        logger.info(
            "call_created",
            call_id=str(call.id),
            order_id=str(order.id),
            call_type=call.call_type,
            status=call.status,
            created_by="user" if is_user else "expert",
        )

        if not before_window:
            await self._provision(call, now, fail_session=True)
        return call, True

    async def _provision(
        self, call: CallSession, now: datetime, *, fail_session: bool
    ) -> bool:
        """Create the provider room. Idempotent on the provider side.

        On failure at creation the session becomes FAILED with the error code -
        a new attempt is a new session. On failure at join the session is left
        as it was and the caller gets `call_provider_unavailable`: an outage is
        not a reason to lose a call that is otherwise fine.
        """
        try:
            await self.provider.create_room(
                RoomSpec(
                    name=call.provider_room_name,
                    max_participants=MAX_PARTICIPANTS,
                    empty_timeout_seconds=settings.call_room_empty_timeout_seconds,
                    departure_timeout_seconds=settings.call_reconnect_grace_seconds,
                )
            )
        except (CallProviderUnavailable, CallProviderNotConfigured) as exc:
            call.provider_error_code = exc.code
            if fail_session:
                await self._transition(
                    call, CallStatus.FAILED, now, reason=CallEndReason.PROVIDER_ERROR
                )
                return False
            await self.session.flush()
            raise
        call.room_provisioned_at = now
        call.provider_error_code = None
        await self.session.flush()
        return True

    # ================================================================== join

    async def issue_join_token(
        self, caller: User, call_id: uuid.UUID, *, now: datetime | None = None
    ) -> JoinGrant:
        """Authorise, in full, and only then ask the provider for a token.

            caller -> membership -> order -> expert -> offering -> payment
                   -> channel -> appointment -> window -> call state -> token

        Every reissue repeats all of it. A token refreshed after the
        appointment was cancelled, the expert suspended or the window closed
        is refused like a first request would be.
        """
        started = time.perf_counter()
        now = now or policy.utcnow()
        call = await self._lock(call_id)
        if call is None:
            raise CallNotFound()
        participant = await self._participant_for(call, caller)
        await self.advance(call, now)

        if CallStatus(call.status).is_terminal:
            raise CallAlreadyEnded(details={"status": call.status})

        entitlement = await self._entitlement(call.order_id)
        if entitlement is None:  # pragma: no cover - FK cascade
            raise CallNotFound()
        call_type = CallType(call.call_type)
        self._authorise(entitlement, call_type)
        window = self._window(call)
        policy.check_window(window, now)

        if call.room_provisioned_at is None:
            await self._provision(call, now, fail_session=False)
        if CallStatus(call.status) is CallStatus.SCHEDULED:
            await self._transition(call, CallStatus.WAITING, now)

        ttl = settings.call_token_ttl_seconds
        if window.closes_at is not None:
            # No token outlives the window it was issued for.
            ttl = min(ttl, int((window.closes_at - now).total_seconds()))
        ttl = max(ttl, 1)

        token = self.provider.create_participant_token(
            TokenRequest(
                room=call.provider_room_name,
                identity=participant.provider_identity,
                publish_sources=PUBLISH_SOURCES[call_type],
                ttl_seconds=ttl,
            )
        )

        participant.token_issued_count += 1
        participant.last_token_issued_at = now
        if ParticipantStatus(participant.status) is ParticipantStatus.INVITED:
            participant.status = ParticipantStatus.JOINING.value
        await self.session.flush()

        # The token itself is never logged, and neither is anything derived
        # from it.
        logger.info(
            "call_token_issued",
            call_id=str(call.id),
            participant_id=str(participant.id),
            role=participant.role,
            status=call.status,
            ttl_seconds=ttl,
            reissue=participant.token_issued_count > 1,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return JoinGrant(
            call=call,
            participant=participant,
            token=token,
            client_url=self.provider.client_url,
        )

    # =================================================================== end

    async def end(
        self, caller: User, call_id: uuid.UUID, *, now: datetime | None = None
    ) -> CallSession:
        """Either party may end the consultation. Idempotent.

        Ending an active call makes it ENDED. Ending one that never became
        active withdraws it: CANCELLED. Either way it never becomes live again;
        another attempt is a new session.
        """
        now = now or policy.utcnow()
        call, participant = await self.get_for_member(caller, call_id, now=now)
        status = CallStatus(call.status)
        if status.is_terminal:
            return call

        role = ParticipantRole(participant.role)
        reason = (
            CallEndReason.USER_ENDED
            if role is ParticipantRole.USER
            else CallEndReason.EXPERT_ENDED
        )
        if status is CallStatus.ACTIVE:
            await self._transition(
                call, CallStatus.ENDED, now, reason=reason, ended_by=role.value
            )
        else:
            was_ringing = status is CallStatus.RINGING
            await self._transition(
                call, CallStatus.CANCELLED, now, reason=reason, ended_by=role.value
            )
            if was_ringing:
                other = call.expert_user_id if role is ParticipantRole.USER else call.user_id
                await self._push(PushEvent.CALL_CANCELLED, call, other)
        return call

    # ============================================================ marketplace

    async def cancel_for_order(
        self,
        order_id: uuid.UUID,
        *,
        reason: CallEndReason = CallEndReason.ORDER_CANCELLED,
        now: datetime | None = None,
    ) -> int:
        """The order was cancelled: its calls stop.

        A call that has not started is CANCELLED. One in progress is ENDED -
        a room left open after the engagement was cancelled would be a
        consultation nobody is entitled to any more.
        """
        return await self._stop_live(CallSession.order_id == order_id, reason, now)

    async def cancel_for_appointment(
        self,
        appointment_id: uuid.UUID,
        *,
        reason: CallEndReason = CallEndReason.APPOINTMENT_CANCELLED,
        now: datetime | None = None,
    ) -> int:
        return await self._stop_live(
            CallSession.appointment_id == appointment_id, reason, now
        )

    async def terminate_for_expert(
        self, expert_id: uuid.UUID, *, now: datetime | None = None
    ) -> int:
        """An expert was suspended. Every live call of theirs stops, now.

        Including one in progress. Suspension is a safety action, and leaving a
        user in a room with somebody the platform just suspended is the wrong
        side to err on. The interruption is recorded as `expert_suspended`,
        which is what a refund decision will need.
        """
        return await self._stop_live(
            CallSession.expert_id == expert_id, CallEndReason.EXPERT_SUSPENDED, now
        )

    async def _stop_live(self, clause, reason: CallEndReason, now: datetime | None) -> int:  # noqa: ANN001
        now = now or policy.utcnow()
        ids = list(
            await self.session.scalars(
                select(CallSession.id).where(
                    clause,
                    CallSession.status.in_([s.value for s in LIVE_STATUSES]),
                )
            )
        )
        for call_id in ids:
            call = await self._lock(call_id)
            if call is not None:
                await self._stop(call, now, reason)
        return len(ids)

    async def _stop(
        self, call: CallSession, now: datetime, reason: CallEndReason
    ) -> None:
        status = CallStatus(call.status)
        if status.is_terminal:
            return
        if status is CallStatus.ACTIVE:
            await self._transition(call, CallStatus.ENDED, now, reason=reason, ended_by="system")
            return
        was_ringing = status is CallStatus.RINGING
        await self._transition(
            call, CallStatus.CANCELLED, now, reason=reason, ended_by="system"
        )
        if was_ringing:
            for participant in (await self._participants(call)).values():
                if not self._joined_since(participant, call.ringing_at):
                    await self._push(PushEvent.CALL_CANCELLED, call, participant.user_id)

    # =============================================================== webhooks

    async def apply_provider_event(
        self, event: ProviderWebhookEvent, *, now: datetime | None = None
    ) -> str:
        """Apply one verified provider event. Idempotent.

        The event id is recorded first, under a unique constraint. The same
        webhook delivered twice finds its id taken and changes nothing - so a
        retry can never produce a second transition.
        """
        now = now or policy.utcnow()
        record = CallProviderEvent(
            provider=self.provider.name,
            event_id=event.event_id,
            event_type=event.event_name,
            room_name=(event.room_name or "")[:64] or None,
            participant_identity=(event.participant_identity or "")[:64] or None,
            provider_created_at=event.created_at,
            received_at=now,
            payload_sha256=event.payload_sha256,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            logger.info(
                "call_webhook_duplicate",
                event_type=event.event_name,
                event_id_fingerprint=_fingerprint(event.event_id),
            )
            return "duplicate"

        call = None
        if event.room_name:
            call_id = await self.session.scalar(
                select(CallSession.id).where(
                    CallSession.provider_room_name == event.room_name
                )
            )
            if call_id is not None:
                call = await self._lock(call_id)

        if call is None:
            # Not ours: another environment sharing the LiveKit project, or a
            # room we already forgot. Recorded, never acted on.
            outcome = "unknown_room"
        else:
            record.call_session_id = call.id
            # Webhook timestamps are whole seconds and can trail our clock; an
            # event is never later than when we received it.
            at = min(event.created_at or now, now)
            outcome = await self._dispatch(call, event, at, now)

        record.outcome = outcome
        record.processed_at = now
        await self.session.flush()
        return outcome

    async def _dispatch(
        self,
        call: CallSession,
        event: ProviderWebhookEvent,
        at: datetime,
        now: datetime,
    ) -> str:
        kind = event.event_type
        identity = event.participant_identity

        if kind is ProviderEventType.PARTICIPANT_JOINED and identity:
            return await self._on_joined(call, identity, at, now)

        if (
            kind
            in (
                ProviderEventType.PARTICIPANT_LEFT,
                ProviderEventType.PARTICIPANT_CONNECTION_ABORTED,
            )
            and identity
        ):
            return await self._on_left(call, identity, event.disconnect_reason, at, now)

        if kind is ProviderEventType.ROOM_FINISHED:
            return await self._on_room_finished(call, at, now)

        return "noted"

    async def _participant_by_identity(
        self, call: CallSession, identity: str
    ) -> CallParticipant | None:
        return await self.session.scalar(
            select(CallParticipant).where(
                CallParticipant.call_session_id == call.id,
                CallParticipant.provider_identity == identity,
            )
        )

    async def _on_joined(
        self, call: CallSession, identity: str, at: datetime, now: datetime
    ) -> str:
        participant = await self._participant_by_identity(call, identity)
        if participant is None:
            # Somebody in the room we never issued a token for. Only a holder
            # of our API secret could mint one - so this is either a leaked
            # secret or a bug, and in both cases they are removed.
            logger.warning(
                "call_intruder_detected",
                call_id=str(call.id),
                identity_fingerprint=_fingerprint(identity),
            )
            await self._remove_quietly(call, identity)
            return "intruder"

        if CallStatus(call.status).is_terminal:
            # A leftover token, still inside its TTL, used to walk back into a
            # finished call. LiveKit would recreate the room on join; it is
            # removed and the room deleted again.
            logger.warning(
                "call_join_after_end",
                call_id=str(call.id),
                participant_id=str(participant.id),
                role=participant.role,
            )
            await self._remove_quietly(call, identity)
            await self._delete_room_quietly(call, force=True)
            return "late_join_removed"

        if participant.last_event_at is not None and at < participant.last_event_at:
            return "stale"

        participant.status = ParticipantStatus.JOINED.value
        participant.first_joined_at = participant.first_joined_at or at
        participant.last_joined_at = at
        participant.connection_count += 1
        participant.last_event_at = at
        await self.session.flush()
        logger.info(
            "call_participant_joined",
            call_id=str(call.id),
            participant_id=str(participant.id),
            role=participant.role,
            connection_count=participant.connection_count,
        )

        await self._evaluate_presence(call, at)
        await self.advance(call, now)
        return "applied"

    async def _on_left(
        self,
        call: CallSession,
        identity: str,
        disconnect_reason: str | None,
        at: datetime,
        now: datetime,
    ) -> str:
        participant = await self._participant_by_identity(call, identity)
        if participant is None:
            return "unknown_participant"

        if disconnect_reason == "DUPLICATE_IDENTITY":
            # The same person connected again - a second device, or the app
            # reconnecting - and LiveKit replaced the old connection. They have
            # not left; the newer connection is in the room.
            return "replaced"

        if participant.last_event_at is not None and at < participant.last_event_at:
            return "stale"

        participant.status = (
            ParticipantStatus.LEFT.value
            if disconnect_reason == "CLIENT_INITIATED"
            else ParticipantStatus.DISCONNECTED.value
        )
        participant.last_left_at = at
        participant.last_event_at = at
        await self.session.flush()
        logger.info(
            "call_participant_left",
            call_id=str(call.id),
            participant_id=str(participant.id),
            role=participant.role,
            participant_status=participant.status,
        )
        # Leaving never ends a call on the spot. The reconnect grace decides.
        await self.advance(call, now)
        return "applied"

    async def _on_room_finished(
        self, call: CallSession, at: datetime, now: datetime
    ) -> str:
        """The provider closed the room. Everybody in it is out.

        Not by itself the end of the call: a live call whose room closed is
        re-provisioned on the next join, inside the reconnect grace. The timers
        decide what the absence means.
        """
        call.room_provisioned_at = None
        for participant in (await self._participants(call)).values():
            if participant.status == ParticipantStatus.JOINED.value:
                participant.status = ParticipantStatus.DISCONNECTED.value
                participant.last_left_at = at
                participant.last_event_at = at
        await self.session.flush()
        await self.advance(call, now)
        return "applied"

    # ========================================================= reconciliation

    async def reconcile(self, call: CallSession, *, now: datetime | None = None) -> str:
        """Compare our view of the room with the provider's, and repair ours.

        Webhooks are not guaranteed to arrive. This is the other half: ask the
        provider who is actually in the room. Somebody we think is present but
        is not becomes DISCONNECTED; somebody present we did not know about
        becomes JOINED; somebody present who is not one of the two is removed.
        """
        now = now or policy.utcnow()
        if CallStatus(call.status).is_terminal or call.room_provisioned_at is None:
            await self.advance(call, now)
            call.last_reconciled_at = now
            await self.session.flush()
            return "skipped"

        changed = await self._sync_presence(call, now)
        if changed is None:
            await self.advance(call, now, confirmed=True)
            return "provider_unavailable"
        call.last_reconciled_at = now
        await self.session.flush()
        await self.advance(call, now, confirmed=True)
        return "changed" if changed else "unchanged"

    async def _sync_presence(self, call: CallSession, now: datetime) -> bool | None:
        """Make our participant rows match the provider's room.

        Returns whether anything changed, or None when the provider could not
        be asked. Applies presence transitions (RINGING, ACTIVE) itself, timed
        from when the provider says people joined.
        """
        if call.room_provisioned_at is None:
            return False
        try:
            present = await self.provider.list_participants(call.provider_room_name)
        except (CallProviderUnavailable, CallProviderNotConfigured):
            logger.warning("call_reconcile_provider_unavailable", call_id=str(call.id))
            return None

        in_room = {
            item.identity: item for item in present if item.state != "disconnected"
        }
        participants = await self._participants(call)
        known = {p.provider_identity for p in participants.values()}

        changed = False
        joined_at: list[datetime] = []
        for participant in participants.values():
            joined = participant.status == ParticipantStatus.JOINED.value
            seen = in_room.get(participant.provider_identity)
            if seen is not None and not joined:
                moment = min(seen.joined_at or now, now)
                participant.status = ParticipantStatus.JOINED.value
                participant.first_joined_at = participant.first_joined_at or moment
                participant.last_joined_at = moment
                participant.connection_count += 1
                participant.last_event_at = now
                joined_at.append(moment)
                changed = True
            elif seen is None and joined:
                participant.status = ParticipantStatus.DISCONNECTED.value
                participant.last_left_at = now
                participant.last_event_at = now
                changed = True

        for identity in set(in_room) - known:
            logger.warning(
                "call_intruder_detected",
                call_id=str(call.id),
                identity_fingerprint=_fingerprint(identity),
                source="reconcile",
            )
            await self._remove_quietly(call, identity)

        await self.session.flush()
        if changed:
            await self._evaluate_presence(call, max(joined_at) if joined_at else now)
        return changed

    async def sweep(self, *, now: datetime | None = None, limit: int = 50) -> int:
        """One pass of the call worker over live calls.

        Each call is locked with SKIP LOCKED, so several workers never process
        the same call and never wait on each other.
        """
        now = now or policy.utcnow()
        statement = (
            select(CallSession)
            .where(CallSession.status.in_([s.value for s in LIVE_STATUSES]))
            .order_by(CallSession.created_at)
            .limit(limit)
        )
        if self._locks:
            statement = statement.with_for_update(skip_locked=True)
        calls = list(await self.session.scalars(statement))

        interval = timedelta(seconds=settings.call_reconcile_interval_seconds)
        for call in calls:
            due = call.room_provisioned_at is not None and (
                call.last_reconciled_at is None
                or call.last_reconciled_at + interval <= now
            )
            if due:
                await self.reconcile(call, now=now)
            else:
                await self.advance(call, now)
        return len(calls)

    # ================================================================ presence

    @staticmethod
    def _joined_since(participant: CallParticipant, moment: datetime | None) -> bool:
        if participant.last_joined_at is None:
            return False
        return moment is None or participant.last_joined_at >= moment

    async def _evaluate_presence(self, call: CallSession, at: datetime) -> None:
        """Both in the room: ACTIVE. One in the room: RINGING."""
        participants = await self._participants(call)
        present = [
            p
            for p in participants.values()
            if p.status == ParticipantStatus.JOINED.value
        ]
        status = CallStatus(call.status)

        if status is CallStatus.SCHEDULED and present:
            await self._transition(call, CallStatus.WAITING, at)
            status = CallStatus.WAITING

        if len(present) == len(participants) and status in (
            CallStatus.WAITING,
            CallStatus.RINGING,
        ):
            await self._transition(call, CallStatus.ACTIVE, at)
            if status is CallStatus.RINGING and call.ringing_at is not None:
                # Answered on one device: the callee's other devices are still
                # ringing and need telling. Sent to exactly the people this
                # ring was sent to.
                ring = f":{int(call.ringing_at.timestamp())}"
                rung = await self.session.scalars(
                    select(NotificationOutbox.user_id).where(
                        NotificationOutbox.dedupe_key.like(
                            f"{PushEvent.INCOMING_CALL.value}:{call.id}:%{ring}"
                        )
                    )
                )
                for user_id in set(rung):
                    await self._push(PushEvent.CALL_ANSWERED, call, user_id, suffix=ring)
            return

        if len(present) == 1 and status is CallStatus.WAITING:
            await self._transition(call, CallStatus.RINGING, at)
            ringer = present[0]
            for participant in participants.values():
                if participant.id != ringer.id:
                    # One ring per ringing episode: the key carries when it
                    # started, so a caller who hangs up and calls again rings
                    # again, and a retried webhook does not.
                    await self._push(
                        PushEvent.INCOMING_CALL,
                        call,
                        participant.user_id,
                        suffix=f":{int(at.timestamp())}",
                    )

    # ================================================================== clock

    async def advance(
        self, call: CallSession, now: datetime, *, confirmed: bool = False
    ) -> None:
        """Apply whatever the clock says has happened since we last looked.

        Idempotent and cheap, so it runs on every read, every webhook and every
        worker pass. The order of the checks is the order of precedence.

        Decisions made *from an absence* - a missed call, a call ended by a
        drop - are confirmed with the provider first, once. Webhooks can arrive
        late: a `participant_joined` delivered after a backlog would otherwise
        start a ring timeout that already expired, and mark a call MISSED while
        both people are talking. The room is the truth about who is in it.
        """
        status = CallStatus(call.status)
        if status.is_terminal:
            return

        if not confirmed and self._absence_decision_due(
            call, status, now, await self._participants(call)
        ):
            await self._sync_presence(call, now)
            await self.advance(call, now, confirmed=True)
            return

        window = self._window(call)
        grace = timedelta(seconds=settings.call_reconnect_grace_seconds)
        participants = await self._participants(call)

        # 1. The window closed around the call.
        if window.closes_at is not None and now > window.closes_at:
            at = window.closes_at
            if status is CallStatus.ACTIVE:
                await self._transition(
                    call, CallStatus.ENDED, at, reason=CallEndReason.TIMEOUT, ended_by="system"
                )
            elif status is CallStatus.RINGING:
                await self._miss(call, at, participants)
            else:
                await self._transition(
                    call, CallStatus.ENDED, at, reason=CallEndReason.NO_SHOW, ended_by="system"
                )
            return

        # 2. The hard ceiling, whatever the appointment says.
        if status is CallStatus.ACTIVE and call.started_at is not None:
            ceiling = call.started_at + timedelta(seconds=settings.call_max_duration_seconds)
            if now >= ceiling:
                await self._transition(
                    call, CallStatus.ENDED, ceiling, reason=CallEndReason.TIMEOUT, ended_by="system"
                )
                return

        # 3. A party has been gone longer than the reconnect grace.
        if status is CallStatus.ACTIVE:
            gone = [
                p
                for p in participants.values()
                if p.status in (ParticipantStatus.LEFT.value, ParticipantStatus.DISCONNECTED.value)
                and p.last_left_at is not None
                and p.last_left_at + grace <= now
            ]
            if gone:
                first = min(gone, key=lambda p: p.last_left_at)
                deliberate = first.status == ParticipantStatus.LEFT.value
                role = ParticipantRole(first.role)
                if deliberate:
                    reason = (
                        CallEndReason.USER_ENDED
                        if role is ParticipantRole.USER
                        else CallEndReason.EXPERT_ENDED
                    )
                else:
                    reason = CallEndReason.NETWORK_DISCONNECT
                # The call ended when it stopped being two-way, not when we
                # noticed: the grace is not billed as consultation time.
                await self._transition(
                    call,
                    CallStatus.ENDED,
                    first.last_left_at,
                    reason=reason,
                    ended_by=role.value if deliberate else None,
                )
            return

        # 4. Ringing: the caller gave up, or nobody answered.
        if status is CallStatus.RINGING:
            present = [
                p for p in participants.values() if p.status == ParticipantStatus.JOINED.value
            ]
            if not present:
                left = [p.last_left_at for p in participants.values() if p.last_left_at]
                if left and max(left) + grace <= now:
                    # Nobody is waiting any more. The call returns to WAITING
                    # and can be rung again inside its window.
                    rung = [
                        p
                        for p in participants.values()
                        if not self._joined_since(p, call.ringing_at)
                    ]
                    await self._transition(call, CallStatus.WAITING, max(left) + grace)
                    await self.outbox.skip_pending_with_prefix(
                        f"{PushEvent.INCOMING_CALL.value}:{call.id}:",
                        reason="caller left",
                    )
                    for participant in rung:
                        await self._push(
                            PushEvent.CALL_CANCELLED,
                            call,
                            participant.user_id,
                            suffix=f":{int(call.ringing_at.timestamp())}",
                        )
                    return
            if call.ringing_at is not None:
                timeout = call.ringing_at + timedelta(seconds=settings.call_ring_timeout_seconds)
                if now >= timeout:
                    await self._miss(call, timeout, participants)

    def _absence_decision_due(
        self,
        call: CallSession,
        status: CallStatus,
        now: datetime,
        participants: dict[ParticipantRole, CallParticipant],
    ) -> bool:
        """Whether the clock is about to act on somebody not being there."""
        if call.room_provisioned_at is None:
            return False
        window = self._window(call)
        if window.closes_at is not None and now > window.closes_at:
            return False  # the window decides, whoever is present
        grace = timedelta(seconds=settings.call_reconnect_grace_seconds)
        gone = (ParticipantStatus.LEFT.value, ParticipantStatus.DISCONNECTED.value)
        if status is CallStatus.ACTIVE:
            return any(
                p.status in gone
                and p.last_left_at is not None
                and p.last_left_at + grace <= now
                for p in participants.values()
            )
        if status is CallStatus.RINGING and call.ringing_at is not None:
            timeout = timedelta(seconds=settings.call_ring_timeout_seconds)
            if call.ringing_at + timeout <= now:
                return True
            return any(
                p.last_left_at is not None and p.last_left_at + grace <= now
                for p in participants.values()
            )
        return False

    async def _miss(
        self,
        call: CallSession,
        at: datetime,
        participants: dict[ParticipantRole, CallParticipant],
    ) -> None:
        """MISSED: the call rang, and the other party never came."""
        ringing_at = call.ringing_at
        await self._transition(
            call, CallStatus.MISSED, at, reason=CallEndReason.MISSED, ended_by="system"
        )
        for participant in participants.values():
            if not self._joined_since(participant, ringing_at):
                await self._push(PushEvent.CALL_MISSED, call, participant.user_id)

    # ============================================================ transitions

    async def _transition(
        self,
        call: CallSession,
        target: CallStatus,
        at: datetime,
        *,
        reason: CallEndReason | None = None,
        ended_by: str | None = None,
    ) -> bool:
        """The only place a call's status changes."""
        current = CallStatus(call.status)
        if current is target:
            return False
        if not can_transition(current, target):
            logger.warning(
                "call_transition_refused",
                call_id=str(call.id),
                from_status=current.value,
                to_status=target.value,
            )
            return False

        call.status = target.value
        if target is CallStatus.RINGING:
            call.ringing_at = at
        if target is CallStatus.ACTIVE and call.started_at is None:
            call.started_at = at

        if target.is_terminal:
            ended_at = at
            if call.started_at is not None and ended_at < call.started_at:
                ended_at = call.started_at
            call.ended_at = ended_at
            call.end_reason = reason.value if reason else None
            call.ended_by = ended_by
            # Canonical duration: server-side timestamps only, never a client
            # timer. Reconnections inside the grace count as call time; the
            # grace after a final drop does not.
            call.duration_seconds = (
                max(0, int((ended_at - call.started_at).total_seconds()))
                if call.started_at is not None
                else None
            )
        await self.session.flush()

        logger.info(
            _TRANSITION_EVENTS.get(target, "call_status_changed"),
            call_id=str(call.id),
            from_status=current.value,
            status=target.value,
            end_reason=call.end_reason if target.is_terminal else None,
            duration_seconds=call.duration_seconds if target.is_terminal else None,
        )

        if target is CallStatus.ACTIVE:
            await self.outbox.skip_pending_with_prefix(
                f"{PushEvent.INCOMING_CALL.value}:{call.id}:", reason="answered"
            )
        if target.is_terminal:
            await self.outbox.skip_pending_with_prefix(
                f"{PushEvent.INCOMING_CALL.value}:{call.id}:", reason=f"call {target.value}"
            )
            await self._delete_room_quietly(call)
        return True

    # ============================================================== side jobs

    async def _push(
        self,
        event: PushEvent,
        call: CallSession,
        recipient_user_id: uuid.UUID,
        *,
        suffix: str = "",
    ) -> None:
        """Queue a call notification, in this transaction.

        The payload is the call id and its type. Not the service, not the
        order, not the other person's name - a lock screen is a public
        surface, and the app resolves anything else after the user opens it.
        Never sent to the person who caused it: callers pass the other party.
        """
        data, expires_at = call_event_fields(
            event,
            call_id=str(call.id),
            call_type=call.call_type,
            ringing_at=call.ringing_at,
        )
        await self.outbox.enqueue(
            event=event,
            user_id=recipient_user_id,
            dedupe_key=f"{event.value}:{call.id}:{recipient_user_id}{suffix}",
            data=data,
            variant=call.call_type,
            expires_at=expires_at,
        )

    async def _delete_room_quietly(
        self, call: CallSession, *, force: bool = False
    ) -> None:
        """Best effort. The room's empty timeout is the backstop.

        `force` is for a room we believe is gone but somebody has just walked
        into - LiveKit creates rooms on join, so it may exist again.
        """
        if call.room_provisioned_at is None and not force:
            return
        try:
            await self.provider.delete_room(call.provider_room_name)
        except (CallProviderUnavailable, CallProviderNotConfigured):
            logger.warning("call_room_delete_failed", call_id=str(call.id))
        call.room_provisioned_at = None
        await self.session.flush()

    async def _remove_quietly(self, call: CallSession, identity: str) -> None:
        try:
            await self.provider.remove_participant(call.provider_room_name, identity)
        except (CallProviderUnavailable, CallProviderNotConfigured):
            logger.warning(
                "call_participant_remove_failed",
                call_id=str(call.id),
                identity_fingerprint=_fingerprint(identity),
            )
