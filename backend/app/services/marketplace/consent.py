"""Consent: the whole of expert access to user data.

The rule, stated plainly because it is the one that matters most in this
phase: **being an expert grants nothing.** An expert sees a user's chart only
when that user granted that scope, on that order, and has not revoked it. There
is no path in this codebase that reads a user's material for an expert without
finding a live consent row first.

Three consequences worth being explicit about.

*Consent is per order.* A user who shared their natal chart for a career
reading in March has not shared it for a synastry reading in June. Scoping
consent to the account would make "I just wanted help with one thing"
impossible to express.

*Only the user grants.* An expert cannot grant consent to themselves, and
cannot grant it on a user's behalf. The routes reflect that: grant and revoke
live under the user's own order.

*Revocation is forward-looking.* It stops future reads immediately. It cannot
un-see what an expert already read during a consultation, and this module does
not pretend otherwise - see `docs/service_consent.md` for what that means for
notes and deliverables.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound, PermissionDenied
from app.core.logging import get_logger
from app.db.models.marketplace import (
    Expert,
    ServiceConsent,
    ServiceOrder,
    ServiceOrderSource,
)
from app.db.models.user import User
from app.domain.marketplace import ConsentScope, OrderSourceKind, OrderStatus

logger = get_logger(__name__)


class ConsentRequired(AppError):
    status_code = 403
    code = "consent_required"
    message = "The user has not shared that information for this engagement."


class ConsentNotApplicable(AppError):
    status_code = 422
    code = "consent_not_applicable"
    message = "That consent scope does not apply to this order."


# Which scope covers which kind of source. An expert asking to read a
# compatibility report needs SYNASTRY consent, not a general "birth data" one -
# otherwise a single grant would open everything.
SCOPE_FOR_SOURCE = {
    OrderSourceKind.BIRTH_PROFILE: ConsentScope.BIRTH_PROFILE,
    OrderSourceKind.SAVED_PERSON: ConsentScope.PARTNER_PROFILE,
    OrderSourceKind.CHART: ConsentScope.NATAL_CHART,
    OrderSourceKind.COMPATIBILITY_REPORT: ConsentScope.SYNASTRY,
    OrderSourceKind.HORARY_QUESTION: ConsentScope.HORARY,
    OrderSourceKind.DIVINATION_READING: ConsentScope.DIVINATION_READING,
    OrderSourceKind.AI_REPORT: ConsentScope.PREVIOUS_READINGS,
}

# Orders where consent still means something. A cancelled order's consent is
# not a live grant, whatever the row says.
LIVE_ORDER_STATES = tuple(
    status.value
    for status in OrderStatus
    if status
    not in (
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
        OrderStatus.FAILED,
        OrderStatus.DRAFT,
    )
)


class ConsentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------- user

    async def list_for_order(
        self, user: User, order_id: uuid.UUID
    ) -> list[ServiceConsent]:
        order = await self._own_order(user, order_id)
        return list(
            await self.session.scalars(
                select(ServiceConsent)
                .where(ServiceConsent.order_id == order.id)
                .order_by(ServiceConsent.scope)
            )
        )

    async def set_scopes(
        self, user: User, order_id: uuid.UUID, scopes: list[ConsentScope]
    ) -> list[ServiceConsent]:
        """Replace the grants on one order with exactly this set.

        A PUT rather than a pair of toggles: the user is stating what they are
        comfortable sharing, and anything not in the list is revoked. That
        makes "share less than before" a single, obvious action.
        """
        order = await self._own_order(user, order_id)
        if order.expert_id is None:
            raise ConsentNotApplicable(
                "This order has no expert, so there is nobody to share with."
            )

        wanted = set(scopes)
        now = datetime.now(UTC)

        existing = {
            row.scope: row
            for row in await self.session.scalars(
                select(ServiceConsent).where(ServiceConsent.order_id == order.id)
            )
        }

        for scope in wanted:
            row = existing.get(scope.value)
            if row is None:
                self.session.add(
                    ServiceConsent(
                        order_id=order.id,
                        user_id=user.id,
                        expert_id=order.expert_id,
                        scope=scope.value,
                        granted_at=now,
                    )
                )
            elif row.revoked_at is not None:
                # Re-granting a revoked scope starts a fresh grant.
                row.revoked_at = None
                row.granted_at = now

        for value, row in existing.items():
            if value not in {scope.value for scope in wanted}:
                if row.revoked_at is None:
                    row.revoked_at = now

        await self.session.flush()

        logger.info(
            "consent_updated",
            order_id=str(order.id),
            expert_id=str(order.expert_id),
            granted_scopes=sorted(scope.value for scope in wanted),
        )
        return await self.list_for_order(user, order_id)

    async def grant(
        self, user: User, order_id: uuid.UUID, scope: ConsentScope
    ) -> ServiceConsent:
        order = await self._own_order(user, order_id)
        if order.expert_id is None:
            raise ConsentNotApplicable(
                "This order has no expert, so there is nobody to share with."
            )

        row = await self.session.scalar(
            select(ServiceConsent).where(
                ServiceConsent.order_id == order.id,
                ServiceConsent.scope == scope.value,
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = ServiceConsent(
                order_id=order.id,
                user_id=user.id,
                expert_id=order.expert_id,
                scope=scope.value,
                granted_at=now,
            )
            self.session.add(row)
        else:
            row.revoked_at = None
            row.granted_at = now
        await self.session.flush()

        logger.info(
            "consent_granted",
            order_id=str(order.id),
            expert_id=str(order.expert_id),
            scope=scope.value,
        )
        return row

    async def revoke(
        self, user: User, order_id: uuid.UUID, scope: ConsentScope
    ) -> ServiceConsent:
        order = await self._own_order(user, order_id)
        row = await self.session.scalar(
            select(ServiceConsent).where(
                ServiceConsent.order_id == order.id,
                ServiceConsent.scope == scope.value,
            )
        )
        if row is None:
            raise NotFound("That consent was never granted.")

        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.session.flush()

        logger.info(
            "consent_revoked", order_id=str(order.id), scope=scope.value
        )
        return row

    async def list_for_order_unchecked(
        self, order_id: uuid.UUID
    ) -> list[ServiceConsent]:
        """Consent rows for an order whose ownership the caller already checked.

        Used when serialising an order the caller has already been authorised
        for, so the ownership query is not repeated per field.
        """
        return list(
            await self.session.scalars(
                select(ServiceConsent)
                .where(ServiceConsent.order_id == order_id)
                .order_by(ServiceConsent.scope)
            )
        )

    async def _own_order(self, user: User, order_id: uuid.UUID) -> ServiceOrder:
        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.user_id == user.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")
        return order

    # ----------------------------------------------------------- expert

    async def has_consent(
        self, expert: Expert, order_id: uuid.UUID, scope: ConsentScope
    ) -> bool:
        """Is there a live grant of this scope, to this expert, on this order?"""
        row = await self.session.scalar(
            select(ServiceConsent.id)
            .join(ServiceOrder, ServiceOrder.id == ServiceConsent.order_id)
            .where(
                ServiceConsent.order_id == order_id,
                ServiceConsent.expert_id == expert.id,
                ServiceConsent.scope == scope.value,
                ServiceConsent.revoked_at.is_(None),
                # An engagement that was cancelled is not a live engagement.
                ServiceOrder.status.in_(LIVE_ORDER_STATES),
                ServiceOrder.deleted_at.is_(None),
            )
        )
        return row is not None

    async def require_consent(
        self, expert: Expert, order_id: uuid.UUID, scope: ConsentScope
    ) -> None:
        if not await self.has_consent(expert, order_id, scope):
            logger.info(
                "consent_denied",
                order_id=str(order_id),
                expert_id=str(expert.id),
                scope=scope.value,
            )
            raise ConsentRequired(details={"scope": scope.value})

    async def granted_scopes(
        self, expert: Expert, order_id: uuid.UUID
    ) -> list[str]:
        rows = await self.session.scalars(
            select(ServiceConsent.scope)
            .join(ServiceOrder, ServiceOrder.id == ServiceConsent.order_id)
            .where(
                ServiceConsent.order_id == order_id,
                ServiceConsent.expert_id == expert.id,
                ServiceConsent.revoked_at.is_(None),
                ServiceOrder.status.in_(LIVE_ORDER_STATES),
            )
        )
        return sorted(rows)

    async def readable_sources(
        self, expert: Expert, order_id: uuid.UUID
    ) -> list[ServiceOrderSource]:
        """The sources on this order that the expert may actually read.

        A source being *referenced* by an order is not permission to read it.
        This is the filter that turns a reference list into an access list, and
        it is what an expert-facing endpoint must go through.
        """
        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.expert_id == expert.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")

        granted = set(await self.granted_scopes(expert, order_id))
        sources = await self.session.scalars(
            select(ServiceOrderSource).where(
                ServiceOrderSource.order_id == order_id
            )
        )

        allowed: list[ServiceOrderSource] = []
        for source in sources:
            scope = SCOPE_FOR_SOURCE.get(OrderSourceKind(source.source_kind))
            if scope is not None and scope.value in granted:
                allowed.append(source)
        return allowed

    def scope_for_source(self, kind: OrderSourceKind) -> ConsentScope:
        return SCOPE_FOR_SOURCE[kind]


async def assert_expert_cannot_grant(actor_is_expert: bool) -> None:
    """Guard for a mistake that would undo the whole model.

    Kept as a named function so that any future expert-facing write path has
    something explicit to call, rather than relying on a reviewer noticing.
    """
    if actor_is_expert:
        raise PermissionDenied(
            "An expert cannot grant consent on a user's behalf.",
            code="expert_cannot_grant_consent",
        )
