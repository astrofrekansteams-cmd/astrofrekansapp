"""Deleting an account: re-authenticated, blocked while services are open.

Why each rule:

* **Re-authentication.** A stolen access token must not be enough to erase an
  account. An email-and-password account confirms its password; an account
  without a local password (Firebase sign-in) confirms its email address.
* **Blocked while something is still in motion.** A live appointment, an
  order that is not finished, or money owed back cannot be abandoned by
  deleting the account - the other party (an expert, the refund queue) would
  be left holding a service with nobody on the other end. The caller is told
  what is open, and `GET /users/me/deletion-check` answers the same question
  before a password is asked for.
* **Audit-safe.** Nothing is erased in the request: the account is soft
  deleted (`deleted_at`, `is_active = false`), every session is revoked, push
  devices are disabled and an expert profile leaves the directory. Orders,
  payments, refunds and the ledger stay intact for the records they are. The
  log line carries the user id and the outcome, never the email.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, CurrentPasswordIncorrect
from app.core.logging import get_logger
from app.core.security import verify_password
from app.db.models.marketplace import Appointment, Expert, ServiceOrder
from app.db.models.payments import RefundRequest
from app.db.models.user import User
from app.domain.marketplace import ExpertStatus, OrderStatus

logger = get_logger(__name__)

TERMINAL_ORDERS = (
    OrderStatus.COMPLETED.value,
    OrderStatus.CANCELLED.value,
    OrderStatus.REFUNDED.value,
    OrderStatus.FAILED.value,
)
OPEN_REFUNDS = ("requested", "manual_review", "approved", "processing")


class AccountHasActiveServices(AppError):
    status_code = 409
    code = "account_has_active_services"
    message = "Finish or cancel your open orders and appointments before deleting the account."


class DeletionConfirmationRequired(AppError):
    status_code = 422
    code = "deletion_confirmation_required"
    message = "Confirm the deletion with your password or your email address."


@dataclass(slots=True, frozen=True)
class DeletionBlockers:
    open_orders: int
    live_appointments: int
    open_refunds: int
    expert_open_orders: int

    @property
    def blocked(self) -> bool:
        return any(
            (self.open_orders, self.live_appointments, self.open_refunds, self.expert_open_orders)
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "open_orders": self.open_orders,
            "live_appointments": self.live_appointments,
            "open_refunds": self.open_refunds,
            "expert_open_orders": self.expert_open_orders,
        }


class AccountDeletionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def blockers(self, user: User) -> DeletionBlockers:
        # A pending-payment order with nothing paid is abandoned, not open:
        # it holds no money and the slot hold expires on its own. Everything
        # else that is not finished blocks. A cancelled order whose money is
        # still under review is counted once - as an open refund, below.
        open_orders = await self.session.scalar(
            select(func.count(ServiceOrder.id)).where(
                ServiceOrder.user_id == user.id,
                ServiceOrder.deleted_at.is_(None),
                ServiceOrder.status.not_in(
                    TERMINAL_ORDERS + (OrderStatus.PENDING_PAYMENT.value,)
                ),
            )
        )
        live_appointments = await self.session.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.user_id == user.id,
                Appointment.status.in_(("pending", "confirmed")),
            )
        )
        open_refunds = await self.session.scalar(
            select(func.count(RefundRequest.id)).where(
                RefundRequest.user_id == user.id,
                RefundRequest.status.in_(OPEN_REFUNDS),
            )
        )
        expert = await self.session.scalar(select(Expert).where(Expert.user_id == user.id))
        expert_open = 0
        if expert is not None:
            expert_open = await self.session.scalar(
                select(func.count(ServiceOrder.id)).where(
                    ServiceOrder.expert_id == expert.id,
                    ServiceOrder.deleted_at.is_(None),
                    ServiceOrder.status.not_in(
                        TERMINAL_ORDERS + (OrderStatus.PENDING_PAYMENT.value,)
                    ),
                )
            )
        return DeletionBlockers(
            open_orders=int(open_orders or 0),
            live_appointments=int(live_appointments or 0),
            open_refunds=int(open_refunds or 0),
            expert_open_orders=int(expert_open or 0),
        )

    def _reauthenticate(
        self, user: User, *, password: str | None, confirm_email: str | None
    ) -> None:
        if user.password_hash:
            if not password or not verify_password(password, user.password_hash):
                raise CurrentPasswordIncorrect()
            return
        if not confirm_email or confirm_email.strip().lower() != user.email.strip().lower():
            raise DeletionConfirmationRequired()

    async def delete(
        self, user: User, *, password: str | None, confirm_email: str | None
    ) -> None:
        # Credentials first: a blocked account still must not reveal its open
        # services to somebody who only holds a token.
        self._reauthenticate(user, password=password, confirm_email=confirm_email)
        found = await self.blockers(user)
        if found.blocked:
            logger.info("account_deletion_blocked", user_id=str(user.id), **found.as_dict())
            raise AccountHasActiveServices(details=found.as_dict())

        from app.repositories.user_repository import UserRepository
        from app.services.auth.service import AuthService
        from app.services.notifications.devices import DeviceService

        await AuthService(self.session).logout_everywhere(user)
        devices = DeviceService(self.session)
        for device in await devices.enabled_devices(user.id):
            await devices.disable_device(device, reason="account_deleted")
        expert = await self.session.scalar(select(Expert).where(Expert.user_id == user.id))
        if expert is not None and expert.status != ExpertStatus.SUSPENDED.value:
            # Out of the directory; the profile row stays for past orders.
            expert.status = ExpertStatus.INACTIVE.value
        await UserRepository(self.session).soft_delete(user)
        await self.session.flush()
        logger.info("account_deleted", user_id=str(user.id), method="self_service")
