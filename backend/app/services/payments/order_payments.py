"""How an order gets paid: line items, payment groups, and the one transition.

An order is split into line items, each classified for store policy, and the
lines are grouped by who may collect them:

    live 1:1 voice/video          -> EXTERNAL_MARKETPLACE group
    digital (AI pre-analysis,     -> STORE group: satisfied by a verified store
      automated reports)             purchase (a credit), on iOS or Android
    chat, written report          -> REVIEW group: blocked - nobody collects
                                     until the classification is decided
    free                          -> nothing to collect

A hybrid order is two lines in two groups, never one classification. The
digital line is only ever paid through a store; if no store product is
configured for it, it is **excluded** from the order rather than bundled into
an external payment.

`evaluate()` is the only place an order moves from PENDING_PAYMENT to paid,
and only when every group is satisfied by something a provider verified. A
client cannot send `paid=true` anywhere: no endpoint accepts it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.marketplace import Appointment, ServiceOrder
from app.db.models.payments import (
    OrderLineItem,
    OrderPaymentGroup,
    PaymentIntent,
    PaymentTransaction,
    StoreProduct,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.service import ServiceDefinition
from app.domain.chat import PushEvent
from app.domain.marketplace import (
    AppointmentStatus,
    FulfillmentMode,
    OrderStatus,
    PaymentStatus,
)
from app.domain.payments import (
    LedgerAccount,
    LineItemStatus,
    LineItemType,
    PaymentClassification,
    PaymentGroupStatus,
    PaymentIntentStatus,
    PaymentRail,
    TransactionType,
)
from app.services.notifications.outbox import OutboxService
from app.services.payments.classification import PaymentClassificationService
from app.services.payments.entitlements import EntitlementService
from app.services.payments.ledger import CREDIT, DEBIT, LedgerService, Posting
from app.services.payments.providers.base import ExternalPaymentNotConfigured
from app.services.payments.providers.external import ExternalPaymentEvent

logger = get_logger(__name__)

STORE_RAIL = "store"  # Apple or Google, whichever device pays


class PaymentPolicyReviewRequired(AppError):
    status_code = 409
    code = "payment_policy_review_required"
    message = (
        "This service's payment method has not been decided yet, so it cannot "
        "be paid for."
    )


class OrderNotPayable(AppError):
    status_code = 409
    code = "order_not_payable"
    message = "This order is not waiting for payment."


class NothingToPayHere(AppError):
    status_code = 409
    code = "no_payment_required_on_this_rail"
    message = "Nothing on this order is paid this way."


class OrderPaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.classifier = PaymentClassificationService()
        self.ledger = LedgerService(session)
        self.outbox = OutboxService(session)

    @property
    def _locks(self) -> bool:
        bind = self.session.bind
        return bind is not None and bind.dialect.name != "sqlite"

    # ============================================================== build

    async def _store_product_for(self, *, code: str | None = None, service_code: str | None = None):  # noqa: ANN202
        from app.services.payments.catalog import StoreCatalogService

        catalog = StoreCatalogService(self.session)
        await catalog.sync()
        statement = select(StoreProduct).where(StoreProduct.active.is_(True))
        if code:
            statement = statement.where(StoreProduct.code == code)
        if service_code:
            statement = statement.where(StoreProduct.service_code == service_code)
        product = await self.session.scalar(statement.limit(1))
        # Sold only if it exists on at least one store.
        if product is None or not (product.apple_product_id or product.google_product_id):
            return None
        return product

    async def build(self, order: ServiceOrder, definition: ServiceDefinition) -> list[OrderLineItem]:
        """Line items and payment groups for a new order. Idempotent."""
        existing = list(
            await self.session.scalars(
                select(OrderLineItem).where(OrderLineItem.order_id == order.id)
            )
        )
        if existing:
            return existing

        lines: list[OrderLineItem] = []
        if order.fulfillment_mode == FulfillmentMode.AUTOMATED.value:
            product = await self._store_product_for(service_code=definition.code)
            if product is None:
                # Nothing configured to sell it: it stays what B8 made it, free.
                classification = self.classifier.classify_digital(amount_minor=0)
                lines.append(self._line(order, LineItemType.AUTOMATED_REPORT, definition.code,
                                        classification.value, amount=0))
            else:
                lines.append(self._line(order, LineItemType.AUTOMATED_REPORT, definition.code,
                                        PaymentClassification.DIGITAL_STORE, amount=None,
                                        store_product_code=product.code))
        else:
            session_class = self.classifier.classify_expert_session(
                order.delivery_type, amount_minor=order.total_minor
            )
            lines.append(
                self._line(
                    order, LineItemType.EXPERT_SESSION, definition.code, session_class.value,
                    amount=order.total_minor, commission=True, source_ref=session_class.basis,
                )
            )
            if order.fulfillment_mode == FulfillmentMode.HYBRID.value:
                product = await self._store_product_for(code="ai_pre_analysis")
                line = self._line(order, LineItemType.AI_PRE_ANALYSIS, "ai_pre_analysis",
                                  PaymentClassification.DIGITAL_STORE, amount=None,
                                  store_product_code="ai_pre_analysis")
                if product is None:
                    # Never bundled into an external payment. Without a store
                    # product it is simply not part of this order.
                    line.line_status = LineItemStatus.EXCLUDED.value
                lines.append(line)

        self.session.add_all(lines)
        await self.session.flush()
        await self._build_groups(order, lines)

        if order.status != OrderStatus.PENDING_PAYMENT.value and await self._requires_payment(order):
            # An automated order with a store product now waits for a credit.
            order.status = OrderStatus.PENDING_PAYMENT.value
            order.payment_status = PaymentStatus.PENDING.value
            await self.session.flush()
        return lines

    def _line(
        self,
        order: ServiceOrder,
        item_type: LineItemType,
        code: str,
        classification: PaymentClassification | str,
        *,
        amount: int | None,
        commission: bool = False,
        store_product_code: str | None = None,
        source_ref: str | None = None,
    ) -> OrderLineItem:
        classification = PaymentClassification(classification)
        rail = {
            PaymentClassification.LIVE_PERSON_TO_PERSON: PaymentRail.EXTERNAL_MARKETPLACE.value,
            PaymentClassification.DIGITAL_STORE: STORE_RAIL,
        }.get(classification, PaymentRail.NONE.value)
        return OrderLineItem(
            order_id=order.id,
            item_type=item_type.value,
            code=code,
            description=order.service_title if item_type is LineItemType.EXPERT_SESSION else None,
            quantity=1,
            unit_amount_minor=amount,
            total_minor=amount,
            currency=order.currency,
            payment_classification=classification.value,
            provider_rail=rail,
            line_status=LineItemStatus.INCLUDED.value,
            store_product_code=store_product_code,
            source_ref=source_ref,
            # The B8 snapshot, attributed to the live line only.
            commission_basis_points=order.commission_basis_points if commission else 0,
            platform_fee_minor=order.platform_fee_minor if commission else 0,
            expert_net_minor=order.expert_net_minor if commission else 0,
        )

    async def _build_groups(self, order: ServiceOrder, lines: list[OrderLineItem]) -> None:
        by_class: dict[str, list[OrderLineItem]] = {}
        for line in lines:
            if line.line_status == LineItemStatus.INCLUDED.value:
                by_class.setdefault(line.payment_classification, []).append(line)
        for classification, members in by_class.items():
            known = [line.total_minor for line in members if line.total_minor is not None]
            amount = sum(known) if len(known) == len(members) else None
            kind = PaymentClassification(classification)
            if kind is PaymentClassification.DIGITAL_STORE:
                status, rail = PaymentGroupStatus.REQUIRED, STORE_RAIL
            elif kind is PaymentClassification.LIVE_PERSON_TO_PERSON:
                status = PaymentGroupStatus.REQUIRED if amount else PaymentGroupStatus.NOT_REQUIRED
                rail = PaymentRail.EXTERNAL_MARKETPLACE.value
            elif kind is PaymentClassification.REVIEW_REQUIRED:
                status = PaymentGroupStatus.BLOCKED_REVIEW if amount else PaymentGroupStatus.NOT_REQUIRED
                rail = PaymentRail.NONE.value
            else:
                status, rail = PaymentGroupStatus.NOT_REQUIRED, PaymentRail.NONE.value
            self.session.add(
                OrderPaymentGroup(
                    order_id=order.id,
                    classification=classification,
                    rail=rail,
                    amount_minor=amount,
                    currency=order.currency,
                    status=status.value,
                )
            )
        await self.session.flush()

    async def groups(self, order_id: uuid.UUID) -> list[OrderPaymentGroup]:
        return list(
            await self.session.scalars(
                select(OrderPaymentGroup)
                .where(OrderPaymentGroup.order_id == order_id)
                .order_by(OrderPaymentGroup.classification)
            )
        )

    async def lines(self, order_id: uuid.UUID) -> list[OrderLineItem]:
        return list(
            await self.session.scalars(
                select(OrderLineItem)
                .where(OrderLineItem.order_id == order_id)
                .order_by(OrderLineItem.created_at)
            )
        )

    async def _requires_payment(self, order: ServiceOrder) -> bool:
        return any(
            group.status in (PaymentGroupStatus.REQUIRED.value, PaymentGroupStatus.BLOCKED_REVIEW.value)
            for group in await self.groups(order.id)
        )

    # ========================================================= transition

    async def evaluate(self, order: ServiceOrder) -> bool:
        """Mark the order paid if - and only if - every group is satisfied."""
        if order.status != OrderStatus.PENDING_PAYMENT.value:
            return False
        groups = await self.groups(order.id)
        if not groups:
            return False
        done = {PaymentGroupStatus.SATISFIED.value, PaymentGroupStatus.NOT_REQUIRED.value}
        if not all(group.status in done for group in groups):
            return False

        order.payment_status = (
            PaymentStatus.PAID.value
            if any(group.status == PaymentGroupStatus.SATISFIED.value for group in groups)
            else PaymentStatus.NOT_REQUIRED.value
        )
        order.status = (
            OrderStatus.PENDING.value
            if order.fulfillment_mode == FulfillmentMode.AUTOMATED.value
            else OrderStatus.CONFIRMED.value
        )
        await self.session.flush()

        appointment = await self.session.scalar(
            select(Appointment).where(Appointment.service_order_id == order.id)
        )
        if appointment is not None and appointment.status == AppointmentStatus.PENDING.value:
            from app.services.marketplace.booking import BookingService

            await BookingService(self.session).confirm(appointment)

        await self.outbox.enqueue(
            event=PushEvent.PAYMENT_SUCCEEDED,
            user_id=order.user_id,
            dedupe_key=f"payment_succeeded:{order.id}",
            data={"order_id": str(order.id)},
            order_id=order.id,
        )
        logger.info(
            "order_paid",
            order_id=str(order.id),
            user_id=str(order.user_id),
            payment_status=order.payment_status,
            status=order.status,
        )
        return True

    # ================================================== store credit

    async def pay_with_credit(self, user_id: uuid.UUID, order: ServiceOrder) -> OrderPaymentGroup:
        """Satisfy the digital group with a verified store credit.

        Consumed under the order's id, so a retry uses the same credit, and a
        second order cannot use it.
        """
        group = await self._group(order, PaymentClassification.DIGITAL_STORE)
        if group.status == PaymentGroupStatus.SATISFIED.value:
            return group
        line = await self.session.scalar(
            select(OrderLineItem).where(
                OrderLineItem.order_id == order.id,
                OrderLineItem.payment_classification == PaymentClassification.DIGITAL_STORE.value,
                OrderLineItem.line_status == LineItemStatus.INCLUDED.value,
            )
        )
        product = await self.session.scalar(
            select(StoreProduct).where(StoreProduct.code == line.store_product_code)
        )
        credit: UserEntitlement = await EntitlementService(self.session).consume(
            user_id, product.entitlement_code, f"order:{order.id}"
        )
        group.status = PaymentGroupStatus.SATISFIED.value
        group.satisfied_at = datetime.now(UTC)
        group.store_purchase_id = credit.store_purchase_id
        if credit.store_purchase_id:
            purchase = await self.session.get(StorePurchase, credit.store_purchase_id)
            group.rail = (
                PaymentRail.APPLE_STORE.value if purchase and purchase.provider == "apple"
                else PaymentRail.GOOGLE_PLAY.value
            )
        await self.session.flush()
        await self.evaluate(order)
        return group

    async def _group(self, order: ServiceOrder, classification: PaymentClassification) -> OrderPaymentGroup:
        statement = select(OrderPaymentGroup).where(
            OrderPaymentGroup.order_id == order.id,
            OrderPaymentGroup.classification == classification.value,
        )
        if self._locks:
            statement = statement.with_for_update()
        group = await self.session.scalar(statement)
        if group is None or group.status == PaymentGroupStatus.NOT_REQUIRED.value:
            raise NothingToPayHere()
        return group

    # ============================================= external checkout

    async def start_external_checkout(
        self,
        user_id: uuid.UUID,
        order: ServiceOrder,
        *,
        idempotency_key: str,
        provider,  # noqa: ANN001 - ExternalMarketplacePaymentProvider
    ):  # noqa: ANN201 - (PaymentIntent, ExternalCheckout)
        """Open an external payment for the order's live 1:1 lines only.

        Refused outright - before any provider is called - if anything on the
        order still needs a policy decision, or if the live line would no
        longer classify as person-to-person (recording enabled, say).
        """
        if order.user_id != user_id:
            raise NotFound("Order not found.")
        if order.status != OrderStatus.PENDING_PAYMENT.value:
            raise OrderNotPayable(details={"status": order.status})

        groups = await self.groups(order.id)
        if any(group.status == PaymentGroupStatus.BLOCKED_REVIEW.value for group in groups):
            raise PaymentPolicyReviewRequired()

        # Classify again now: policy inputs can change between order and pay.
        live = await self.session.scalar(
            select(OrderLineItem).where(
                OrderLineItem.order_id == order.id,
                OrderLineItem.item_type == LineItemType.EXPERT_SESSION.value,
            )
        )
        if live is not None:
            now_class = self.classifier.classify_expert_session(
                order.delivery_type, amount_minor=live.total_minor or 0
            )
            if now_class.value is not PaymentClassification.LIVE_PERSON_TO_PERSON:
                raise PaymentPolicyReviewRequired(details={"basis": now_class.basis})

        group = await self._group(order, PaymentClassification.LIVE_PERSON_TO_PERSON)
        if group.status == PaymentGroupStatus.SATISFIED.value:
            raise OrderNotPayable(details={"reason": "already_paid"})
        if not provider.configured:
            raise ExternalPaymentNotConfigured()

        intent = await self.session.scalar(
            select(PaymentIntent).where(
                PaymentIntent.user_id == user_id,
                PaymentIntent.idempotency_key == idempotency_key,
            )
        )
        if intent is not None and intent.order_id != order.id:
            raise AppError("That idempotency key was used for another payment.",
                           code="idempotency_conflict", status_code=409)
        if intent is None:
            intent = PaymentIntent(
                user_id=user_id,
                order_id=order.id,
                payment_group_id=group.id,
                provider=provider.name,
                rail=PaymentRail.EXTERNAL_MARKETPLACE.value,
                classification=PaymentClassification.LIVE_PERSON_TO_PERSON.value,
                amount_minor=group.amount_minor or 0,
                currency=group.currency,
                status=PaymentIntentStatus.CREATED.value,
                idempotency_key=idempotency_key,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=settings.external_payment_intent_ttl_seconds),
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(intent)
                    await self.session.flush()
            except IntegrityError:
                intent = await self.session.scalar(
                    select(PaymentIntent).where(
                        PaymentIntent.user_id == user_id,
                        PaymentIntent.idempotency_key == idempotency_key,
                    )
                )

        checkout = await provider.create_checkout(
            intent_id=intent.id,
            amount_minor=intent.amount_minor,
            currency=intent.currency,
            idempotency_key=f"intent:{intent.id}",
        )
        intent.external_reference = checkout.external_reference
        if intent.status == PaymentIntentStatus.CREATED.value:
            intent.status = PaymentIntentStatus.PENDING.value
        group.payment_intent_id = intent.id
        await self.session.flush()
        logger.info(
            "external_payment_started",
            payment_intent_id=str(intent.id),
            order_id=str(order.id),
            user_id=str(user_id),
            provider=provider.name,
        )
        return intent, checkout

    async def apply_external_event(self, event: ExternalPaymentEvent, provider_name: str) -> str:
        """A verified provider event about one of our intents."""
        statement = select(PaymentIntent).where(
            PaymentIntent.provider == provider_name,
            PaymentIntent.external_reference == event.external_reference,
        )
        if self._locks:
            statement = statement.with_for_update()
        intent = await self.session.scalar(statement)
        if intent is None:
            return "unknown_intent"

        if event.event_type == "payment_succeeded":
            return await self._on_paid(intent, event)
        if event.event_type == "payment_failed":
            if intent.status in (PaymentIntentStatus.CREATED.value, PaymentIntentStatus.PENDING.value):
                intent.status = PaymentIntentStatus.FAILED.value
                await self.session.flush()
                await self.outbox.enqueue(
                    event=PushEvent.PAYMENT_FAILED,
                    user_id=intent.user_id,
                    dedupe_key=f"payment_failed:{intent.id}",
                    data={"order_id": str(intent.order_id)} if intent.order_id else {},
                )
            return "applied"
        if event.event_type in ("refund_succeeded", "chargeback"):
            from app.services.payments.refunds import RefundService

            return await RefundService(self.session).record_provider_reversal(intent, event)
        return "ignored"

    async def _on_paid(self, intent: PaymentIntent, event: ExternalPaymentEvent) -> str:
        if intent.status == PaymentIntentStatus.PAID.value:
            return "already_paid"
        if event.amount_minor != intent.amount_minor or (event.currency or "").upper() != intent.currency:
            # Never "paid" for a different sum than we asked for.
            logger.warning(
                "external_payment_amount_mismatch",
                payment_intent_id=str(intent.id),
                expected=intent.amount_minor,
                received=event.amount_minor,
            )
            return "amount_mismatch"

        order = await self.session.get(ServiceOrder, intent.order_id) if intent.order_id else None
        live = None
        if order is not None:
            live = await self.session.scalar(
                select(OrderLineItem).where(
                    OrderLineItem.order_id == order.id,
                    OrderLineItem.item_type == LineItemType.EXPERT_SESSION.value,
                )
            )

        now = datetime.now(UTC)
        transaction = PaymentTransaction(
            provider=intent.provider,
            rail=intent.rail,
            user_id=intent.user_id,
            order_id=intent.order_id,
            payment_intent_id=intent.id,
            external_transaction_ref=event.external_transaction_ref or event.event_id,
            type=TransactionType.CHARGE.value,
            amount_minor=event.amount_minor,
            currency=intent.currency,
            provider_fee_minor=event.provider_fee_minor,
            status="succeeded",
            occurred_at=event.occurred_at or now,
            created_at=now,
            metadata_safe={"event_id": event.event_id},
        )
        try:
            async with self.session.begin_nested():
                self.session.add(transaction)
                await self.session.flush()
        except IntegrityError:
            return "already_paid"

        fee = live.platform_fee_minor if live else 0
        net = live.expert_net_minor if live else 0
        if fee + net != intent.amount_minor:
            # A live line always carries the B8 split of exactly its gross.
            fee, net = intent.amount_minor, 0
        await self.ledger.post(
            journal_key=f"charge:{transaction.id}",
            entry_type=TransactionType.CHARGE,
            currency=intent.currency,
            payment_transaction_id=transaction.id,
            order_id=intent.order_id,
            occurred_at=transaction.occurred_at,
            postings=[
                Posting(LedgerAccount.EXTERNAL_PROVIDER_CLEARING, DEBIT, intent.amount_minor),
                Posting(LedgerAccount.PLATFORM_REVENUE, CREDIT, fee),
                Posting(
                    LedgerAccount.EXPERT_PAYABLE_PENDING, CREDIT, net,
                    account_id=order.expert_id if order else None,
                ),
            ],
        )

        intent.status = PaymentIntentStatus.PAID.value
        intent.paid_at = now
        if intent.payment_group_id:
            group = await self.session.get(OrderPaymentGroup, intent.payment_group_id)
            group.status = PaymentGroupStatus.SATISFIED.value
            group.satisfied_at = now
        await self.session.flush()
        if order is not None:
            await self.evaluate(order)
            if order.status == OrderStatus.CANCELLED.value:
                # The money arrived after the order was cancelled (a checkout
                # page left open). It was collected, so it is owed back - and
                # visibly, through the same review a paid cancellation opens.
                from app.services.payments.refunds import RefundService

                order.payment_status = PaymentStatus.PAID.value
                await RefundService(self.session).on_paid_order_cancelled(
                    order, actor=order.cancellation_actor or "system"
                )
                logger.warning("payment_after_cancellation", order_id=str(order.id))
        return "applied"
