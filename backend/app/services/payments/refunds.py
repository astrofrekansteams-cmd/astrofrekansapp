"""Refunds: requests, a policy that advises, and money that moves only when told.

Three layers, deliberately separate:

* **RefundPolicy** reads the evidence - the reason, who cancelled, what B10
  says happened to the call - and answers AUTO, MANUAL_REVIEW or
  NOT_ELIGIBLE. It never moves money. It hardcodes no percentage: nobody has
  decided that a technical failure is worth 100%, or that a no-show is worth
  0%, so those cases are MANUAL_REVIEW with the evidence attached.
* **RefundService** records requests, checks amounts, and - on an
  administrator's approval - asks the provider to refund. The only automatic
  path is a store reversal: Apple or Google already moved the money.
* The **ledger** records what moved, proportionally reversing the original
  split, so that refunding a charge in parts reverses it exactly once it is
  all refunded.

Amount safety: `0 < amount <= refundable`, integers only, with the payment
intent's row locked. `payment_intents.refunded_minor <= amount_minor` is also
a check constraint, so two concurrent approvals cannot together refund more
than was paid.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.calls import CallSession
from app.db.models.marketplace import Appointment, ServiceOrder
from app.db.models.payments import (
    OrderPaymentGroup,
    PaymentIntent,
    PaymentTransaction,
    RefundRequest,
)
from app.domain.calls import CallEndReason
from app.domain.chat import PushEvent
from app.domain.marketplace import PaymentStatus
from app.domain.payments import (
    LedgerAccount,
    PaymentGroupStatus,
    PaymentIntentStatus,
    RefundActor,
    RefundDecision,
    RefundReason,
    RefundStatus,
    TransactionType,
)
from app.services.notifications.outbox import OutboxService
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting, split_proportionally
from app.services.payments.providers.external import ExternalPaymentEvent

logger = get_logger(__name__)

ACTIVE_REFUND_STATUSES = (
    RefundStatus.REQUESTED.value,
    RefundStatus.MANUAL_REVIEW.value,
    RefundStatus.APPROVED.value,
    RefundStatus.PROCESSING.value,
)

TECHNICAL_END_REASONS = frozenset(
    {CallEndReason.PROVIDER_ERROR.value, CallEndReason.NETWORK_DISCONNECT.value}
)


class NothingToRefund(AppError):
    status_code = 409
    code = "nothing_to_refund"
    message = "Nothing on this order was paid in a way we can refund."


class RefundAmountInvalid(AppError):
    status_code = 422
    code = "refund_amount_invalid"
    message = "The refund must be more than zero and no more than what remains refundable."


class RefundNotReviewable(AppError):
    status_code = 409
    code = "refund_not_reviewable"
    message = "This refund request is not awaiting review."


@dataclass(slots=True, frozen=True)
class RefundPolicyResult:
    decision: RefundDecision
    basis: str


class RefundPolicy:
    """Evidence in, advice out. No money, no percentages."""

    def evaluate(
        self,
        *,
        reason: RefundReason,
        paid: bool,
        call_end_reasons: list[str],
        appointment_status: str | None,
        cancellation_actor: str | None,
    ) -> RefundPolicyResult:
        if not paid:
            return RefundPolicyResult(RefundDecision.NOT_ELIGIBLE, "not_paid")
        if reason is RefundReason.STORE_REVERSAL:
            # The store already refunded; we only record it.
            return RefundPolicyResult(RefundDecision.AUTO, "store_already_refunded")
        technical = sorted(set(call_end_reasons) & TECHNICAL_END_REASONS)
        if reason is RefundReason.TECHNICAL_FAILURE and technical:
            return RefundPolicyResult(
                RefundDecision.MANUAL_REVIEW, f"technical_evidence:{','.join(technical)}"
            )
        if reason is RefundReason.NO_SHOW or appointment_status == "no_show":
            return RefundPolicyResult(
                RefundDecision.MANUAL_REVIEW, f"no_show:{cancellation_actor or 'unknown'}"
            )
        if reason in (RefundReason.USER_CANCELLATION, RefundReason.EXPERT_CANCELLATION):
            return RefundPolicyResult(
                RefundDecision.MANUAL_REVIEW, f"cancelled_by:{cancellation_actor or reason.value}"
            )
        # Anything not clearly decided is for a person.
        return RefundPolicyResult(RefundDecision.MANUAL_REVIEW, reason.value)


class RefundService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ledger = LedgerService(session)
        self.policy = RefundPolicy()
        self.outbox = OutboxService(session)

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    async def _paid_intent(self, order_id: uuid.UUID) -> PaymentIntent | None:
        statement = select(PaymentIntent).where(
            PaymentIntent.order_id == order_id,
            PaymentIntent.status.in_(
                [PaymentIntentStatus.PAID.value, PaymentIntentStatus.PARTIALLY_REFUNDED.value]
            ),
        )
        if self._locks:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def _pending_total(self, intent_id: uuid.UUID) -> int:
        rows = await self.session.scalars(
            select(RefundRequest.amount_minor).where(
                RefundRequest.payment_intent_id == intent_id,
                RefundRequest.status.in_(
                    [RefundStatus.REQUESTED.value, RefundStatus.MANUAL_REVIEW.value,
                     RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value]
                ),
            )
        )
        return sum(rows)

    async def _evidence(self, order: ServiceOrder) -> tuple[list[str], str | None, str | None]:
        """What B10 and B8 recorded. Evidence for a person, not a verdict."""
        reasons = list(
            await self.session.scalars(
                select(CallSession.end_reason).where(
                    CallSession.order_id == order.id, CallSession.end_reason.is_not(None)
                )
            )
        )
        appointment = await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )
        return (
            [r for r in reasons if r],
            appointment.status if appointment else None,
            order.cancellation_actor or (appointment.cancellation_actor if appointment else None),
        )

    # ============================================================ request

    async def request(
        self,
        *,
        user_id: uuid.UUID,
        order: ServiceOrder,
        amount_minor: int | None,
        reason: RefundReason,
        actor: RefundActor,
        idempotency_key: str,
    ) -> RefundRequest:
        """Record a refund request with the policy's advice. Moves no money."""
        existing = await self.session.scalar(
            select(RefundRequest).where(
                RefundRequest.user_id == user_id,
                RefundRequest.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        intent = await self._paid_intent(order.id)
        if intent is None:
            raise NothingToRefund()
        refundable = intent.amount_minor - intent.refunded_minor - await self._pending_total(intent.id)
        amount = refundable if amount_minor is None else amount_minor
        if not isinstance(amount, int) or amount <= 0 or amount > refundable:
            raise RefundAmountInvalid(details={"refundable_minor": max(refundable, 0)})

        call_reasons, appointment_status, cancel_actor = await self._evidence(order)
        advice = self.policy.evaluate(
            reason=reason,
            paid=True,
            call_end_reasons=call_reasons,
            appointment_status=appointment_status,
            cancellation_actor=cancel_actor,
        )
        request = RefundRequest(
            user_id=user_id,
            order_id=order.id,
            payment_intent_id=intent.id,
            amount_minor=amount,
            currency=intent.currency,
            reason=reason.value,
            actor=actor.value,
            status=RefundStatus.MANUAL_REVIEW.value,
            decision=advice.decision.value,
            decision_basis=advice.basis[:80],
            idempotency_key=idempotency_key[:80],
        )
        try:
            async with self.session.begin_nested():
                self.session.add(request)
                await self.session.flush()
        except IntegrityError:
            return await self.session.scalar(
                select(RefundRequest).where(
                    RefundRequest.user_id == user_id,
                    RefundRequest.idempotency_key == idempotency_key,
                )
            )
        logger.info(
            "refund_requested",
            refund_id=str(request.id),
            order_id=str(order.id),
            reason=reason.value,
            actor=actor.value,
            decision=advice.decision.value,
        )
        return request

    async def on_paid_order_cancelled(self, order: ServiceOrder, *, actor: str) -> RefundRequest | None:
        """A paid order was cancelled: the money is owed back, visibly.

        The order does not pretend nothing was paid. `payment_status` becomes
        `refund_pending` and a request waits for review - it is not refunded
        until a provider says the money moved.
        """
        if order.payment_status not in (
            PaymentStatus.PAID.value,
            PaymentStatus.PARTIALLY_REFUNDED.value,
            PaymentStatus.REFUND_PENDING.value,
        ):
            return None
        existing = await self.session.scalar(
            select(RefundRequest).where(
                RefundRequest.user_id == order.user_id,
                RefundRequest.idempotency_key == f"cancel:{order.id}",
            )
        )
        if existing is not None:
            return existing
        intent = await self._paid_intent(order.id)
        if intent is None:
            return None
        remaining = intent.amount_minor - intent.refunded_minor - await self._pending_total(intent.id)
        if remaining <= 0:
            # Everything paid is already refunded or already awaiting review -
            # a user asked before cancelling. The order still shows the review
            # rather than a second request for money that is spoken for.
            if intent.amount_minor > intent.refunded_minor:
                order.payment_status = PaymentStatus.REFUND_PENDING.value
            return await self.session.scalar(
                select(RefundRequest)
                .where(
                    RefundRequest.order_id == order.id,
                    RefundRequest.status.in_(ACTIVE_REFUND_STATUSES),
                )
                .order_by(RefundRequest.created_at.desc())
                .limit(1)
            )
        order.payment_status = PaymentStatus.REFUND_PENDING.value
        reason = (
            RefundReason.EXPERT_CANCELLATION if actor == "expert" else RefundReason.USER_CANCELLATION
        )
        return await self.request(
            user_id=order.user_id,
            order=order,
            amount_minor=None,
            reason=reason,
            actor=RefundActor.SYSTEM,
            idempotency_key=f"cancel:{order.id}",
        )

    # ============================================================== admin

    async def approve(self, refund_id: uuid.UUID, *, reviewer: str, provider) -> RefundRequest:  # noqa: ANN001
        """Administrator action. Asks the provider to refund, then records it.

        Not reachable from any user-facing route.
        """
        request = await self._lock_request(refund_id)
        if request.status not in (RefundStatus.MANUAL_REVIEW.value, RefundStatus.REQUESTED.value):
            raise RefundNotReviewable(details={"status": request.status})
        intent = await self._lock_intent(request.payment_intent_id)
        if request.amount_minor > intent.amount_minor - intent.refunded_minor:
            raise RefundAmountInvalid()

        request.status = RefundStatus.PROCESSING.value
        request.reviewed_by = reviewer[:40]
        await self.session.flush()

        result = await provider.refund(
            external_reference=intent.external_reference or "",
            amount_minor=request.amount_minor,
            currency=request.currency,
            idempotency_key=f"refund:{request.id}",
        )
        if not result.succeeded:
            request.status = RefundStatus.FAILED.value
            await self.session.flush()
            return request

        transaction = await self._record_reversal(
            intent,
            amount=request.amount_minor,
            kind=TransactionType.REFUND,
            external_ref=result.external_refund_ref,
            journal_key=f"refund:{request.id}",
        )
        request.status = RefundStatus.REFUNDED.value
        request.refund_transaction_id = transaction.id if transaction else None
        request.processed_at = datetime.now(UTC)
        await self.session.flush()
        await self.outbox.enqueue(
            event=PushEvent.REFUND_PROCESSED,
            user_id=request.user_id,
            dedupe_key=f"refund_processed:{request.id}",
            data={"order_id": str(request.order_id)} if request.order_id else {},
        )
        return request

    async def deny(self, refund_id: uuid.UUID, *, reviewer: str) -> RefundRequest:
        request = await self._lock_request(refund_id)
        if request.status not in (RefundStatus.MANUAL_REVIEW.value, RefundStatus.REQUESTED.value):
            raise RefundNotReviewable(details={"status": request.status})
        request.status = RefundStatus.DENIED.value
        request.reviewed_by = reviewer[:40]
        request.processed_at = datetime.now(UTC)
        await self.session.flush()
        await self._settle_order_payment_status(request.order_id)
        return request

    async def _settle_order_payment_status(self, order_id: uuid.UUID | None) -> None:
        """A denied review stops saying "refund pending".

        The order goes back to what the money says: paid, or partly refunded.
        Only when no other request for it is still open.
        """
        if order_id is None:
            return
        order = await self.session.get(ServiceOrder, order_id)
        if order is None or order.payment_status != PaymentStatus.REFUND_PENDING.value:
            return
        still_open = await self.session.scalar(
            select(RefundRequest.id).where(
                RefundRequest.order_id == order_id,
                RefundRequest.status.in_(ACTIVE_REFUND_STATUSES),
            ).limit(1)
        )
        if still_open is not None:
            return
        intent = await self.session.scalar(
            select(PaymentIntent).where(
                PaymentIntent.order_id == order_id,
                PaymentIntent.status.in_(
                    [PaymentIntentStatus.PAID.value, PaymentIntentStatus.PARTIALLY_REFUNDED.value]
                ),
            )
        )
        if intent is None:
            return
        order.payment_status = (
            PaymentStatus.PARTIALLY_REFUNDED.value if intent.refunded_minor else PaymentStatus.PAID.value
        )
        await self.session.flush()

    async def record_provider_reversal(self, intent: PaymentIntent, event: ExternalPaymentEvent) -> str:
        """The provider reports a refund or a chargeback it already made."""
        kind = TransactionType.CHARGEBACK if event.event_type == "chargeback" else TransactionType.REFUND
        amount = event.amount_minor or 0
        if amount <= 0 or amount > intent.amount_minor - intent.refunded_minor:
            logger.warning("provider_reversal_amount_invalid", payment_intent_id=str(intent.id))
            return "amount_invalid"
        transaction = await self._record_reversal(
            intent,
            amount=amount,
            kind=kind,
            external_ref=event.external_transaction_ref or event.event_id,
            journal_key=f"{kind.value}:{event.event_id}",
        )
        return "applied" if transaction else "duplicate"

    # ========================================================== internals

    async def _lock_request(self, refund_id: uuid.UUID) -> RefundRequest:
        statement = select(RefundRequest).where(RefundRequest.id == refund_id)
        if self._locks:
            statement = statement.with_for_update()
        request = await self.session.scalar(statement)
        if request is None:
            raise NotFound("Refund request not found.")
        return request

    async def _lock_intent(self, intent_id: uuid.UUID | None) -> PaymentIntent:
        statement = select(PaymentIntent).where(PaymentIntent.id == intent_id)
        if self._locks:
            statement = statement.with_for_update()
        intent = await self.session.scalar(statement)
        if intent is None:
            raise NothingToRefund()
        return intent

    async def _record_reversal(
        self,
        intent: PaymentIntent,
        *,
        amount: int,
        kind: TransactionType,
        external_ref: str,
        journal_key: str,
    ) -> PaymentTransaction | None:
        """Append the reversal and post the proportional ledger entries. Once."""
        charge = await self.session.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.payment_intent_id == intent.id,
                PaymentTransaction.type == TransactionType.CHARGE.value,
            )
        )
        if charge is None:
            raise NothingToRefund()
        now = datetime.now(UTC)
        partial = intent.refunded_minor + amount < intent.amount_minor
        transaction = PaymentTransaction(
            provider=intent.provider,
            rail=intent.rail,
            user_id=intent.user_id,
            order_id=intent.order_id,
            payment_intent_id=intent.id,
            related_transaction_id=charge.id,
            external_transaction_ref=external_ref,
            type=(
                TransactionType.PARTIAL_REFUND.value
                if kind is TransactionType.REFUND and partial
                else kind.value
            ),
            amount_minor=amount,
            currency=intent.currency,
            status="succeeded",
            occurred_at=now,
            created_at=now,
            metadata_safe={"journal": journal_key.split(":", 1)[0]},
        )
        try:
            async with self.session.begin_nested():
                self.session.add(transaction)
                await self.session.flush()
        except IntegrityError:
            return None

        # Reverse the original split on a running total, so parts add up to
        # the whole exactly. The expert's share comes back from wherever it
        # now sits: pending if not yet released, available if released - and
        # available may go negative. See docs/marketplace_settlement.md.
        order = await self.session.get(ServiceOrder, intent.order_id) if intent.order_id else None
        gross = intent.amount_minor
        charge_net = await self._charge_net(charge)
        expert_part = split_proportionally(
            amount=amount, already=intent.refunded_minor, gross=gross, share=charge_net
        )
        platform_part = amount - expert_part
        released = order is not None and await self.ledger.has_journal(f"release:{order.id}:{intent.currency}")
        expert_account = (
            LedgerAccount.EXPERT_PAYABLE_AVAILABLE if released else LedgerAccount.EXPERT_PAYABLE_PENDING
        )
        await self.ledger.post(
            journal_key=journal_key,
            entry_type=kind,
            currency=intent.currency,
            payment_transaction_id=transaction.id,
            order_id=intent.order_id,
            postings=[
                Posting(LedgerAccount.PLATFORM_REVENUE, DEBIT, platform_part),
                Posting(expert_account, DEBIT, expert_part,
                        account_id=order.expert_id if order else None),
                Posting(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, CREDIT, amount),
            ],
        )

        intent.refunded_minor += amount
        intent.status = (
            PaymentIntentStatus.REFUNDED.value
            if intent.refunded_minor == intent.amount_minor
            else PaymentIntentStatus.PARTIALLY_REFUNDED.value
        )
        if order is not None:
            order.payment_status = (
                PaymentStatus.REFUNDED.value
                if intent.refunded_minor == intent.amount_minor
                else PaymentStatus.PARTIALLY_REFUNDED.value
            )
            if intent.refunded_minor == intent.amount_minor and intent.payment_group_id:
                group = await self.session.get(OrderPaymentGroup, intent.payment_group_id)
                group.status = PaymentGroupStatus.REFUNDED.value
        await self.session.flush()
        logger.info(
            "payment_reversed",
            payment_intent_id=str(intent.id),
            order_id=str(intent.order_id),
            type=transaction.type,
            amount_minor=amount,
            currency=intent.currency,
        )
        return transaction

    async def _charge_net(self, charge: PaymentTransaction) -> int:
        """The expert's share of the original charge, from its own journal."""
        from app.db.models.payments import LedgerEntry

        value = await self.session.scalar(
            select(LedgerEntry.amount_minor).where(
                LedgerEntry.journal_key == f"charge:{charge.id}",
                LedgerEntry.account_type == LedgerAccount.EXPERT_PAYABLE_PENDING.value,
            )
        )
        return int(value or 0)
