"""Expert profiles, offerings and availability.

Two authorisation rules shape this file:

* **A user may not promote themselves.** `status` and `verified` are moderation
  decisions. An applicant lands in `pending_review`, and the transitions that
  make a profile public (`approve`, `verify`, `suspend`, `reactivate`) exist as
  service methods with no route attached - ready for an admin surface, not
  reachable by the person being moderated.
* **The catalogue is the source of truth.** An offering may narrow what a
  service definition allows; it can never widen it. An expert cannot sell a
  video consultation for a service the platform does not deliver by video, nor
  declare that their version needs no birth data when the definition says it
  does.
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
    ExpertAvailability,
    ExpertAvailabilityException,
    ExpertService,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.marketplace import (
    AvailabilityExceptionType,
    DeliveryType,
    ExpertSpecialty,
    ExpertStatus,
    FulfillmentMode,
)
from app.services.marketplace.slots import zone

logger = get_logger(__name__)

SUPPORTED_LANGUAGES = ("tr", "az", "en")

# Which catalogue capability each delivery channel needs. An offering is only
# valid if the definition supports the channel it is sold through.
DELIVERY_CAPABILITY = {
    DeliveryType.CHAT: "supports_chat",
    DeliveryType.VOICE: "supports_voice",
    DeliveryType.VIDEO: "supports_video",
    DeliveryType.WRITTEN_REPORT: "supports_automated_report",
}


class ExpertProfileExists(AppError):
    status_code = 409
    code = "expert_profile_exists"
    message = "This account already has an expert profile."


class InvalidExpertData(AppError):
    status_code = 422
    code = "invalid_expert_data"
    message = "That expert profile is not valid."


class ServiceNotOfferable(AppError):
    status_code = 422
    code = "service_not_offerable"
    message = "This service cannot be offered that way."


class ExpertProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------ create

    async def apply(
        self,
        user: User,
        *,
        display_name: str,
        bio: str | None,
        headline: str | None,
        languages: list[str],
        specialties: list[str],
        experience_years: int,
        timezone: str,
        avatar_key: str | None = None,
    ) -> Expert:
        """Create the caller's own profile, in `pending_review`.

        Never `active`, never `verified`: an applicant who could publish
        themselves is not an applicant.
        """
        existing = await self.session.scalar(
            select(Expert).where(Expert.user_id == user.id)
        )
        if existing is not None:
            raise ExpertProfileExists()

        self._validate(
            languages=languages,
            specialties=specialties,
            timezone=timezone,
            experience_years=experience_years,
        )

        expert = Expert(
            user_id=user.id,
            display_name=display_name.strip(),
            headline=(headline or "").strip() or None,
            bio=(bio or "").strip() or None,
            avatar_key=avatar_key,
            languages=sorted(set(languages)),
            specialties=sorted(set(specialties)),
            experience_years=experience_years,
            timezone=timezone,
            status=ExpertStatus.PENDING_REVIEW.value,
            verified=False,
            rating_average=0,
            rating_count=0,
        )
        self.session.add(expert)
        await self.session.flush()

        logger.info(
            "expert_application_created",
            expert_id=str(expert.id),
            user_id=str(user.id),
            specialties=len(expert.specialties),
        )
        return expert

    def _validate(
        self,
        *,
        languages: list[str],
        specialties: list[str],
        timezone: str,
        experience_years: int,
    ) -> None:
        unknown_languages = set(languages) - set(SUPPORTED_LANGUAGES)
        if unknown_languages:
            raise InvalidExpertData(
                f"Unsupported languages: {sorted(unknown_languages)}",
                details={"supported": list(SUPPORTED_LANGUAGES)},
            )
        if not languages:
            raise InvalidExpertData("At least one language is required.")

        valid_specialties = {item.value for item in ExpertSpecialty}
        unknown = set(specialties) - valid_specialties
        if unknown:
            raise InvalidExpertData(
                f"Unknown specialties: {sorted(unknown)}",
                details={"supported": sorted(valid_specialties)},
            )
        if not specialties:
            raise InvalidExpertData("At least one specialty is required.")

        if not 0 <= experience_years <= 80:
            raise InvalidExpertData("Experience years must be between 0 and 80.")

        zone(timezone)  # raises invalid_timezone

    # -------------------------------------------------------------- read

    async def get_public(self, expert_id: uuid.UUID) -> Expert:
        """A profile as a stranger sees it: active only."""
        expert = await self.session.scalar(
            select(Expert).where(
                Expert.id == expert_id,
                Expert.status == ExpertStatus.ACTIVE.value,
                Expert.deleted_at.is_(None),
            )
        )
        if expert is None:
            # A profile that is not public is simply not found - the status of
            # somebody's application is not public information.
            raise NotFound("Expert not found.")
        return expert

    async def get_own(self, user: User) -> Expert:
        expert = await self.session.scalar(
            select(Expert).where(
                Expert.user_id == user.id, Expert.deleted_at.is_(None)
            )
        )
        if expert is None:
            raise NotFound("You do not have an expert profile.")
        return expert

    async def get_for_expert_id(self, user: User, expert_id: uuid.UUID) -> Expert:
        """The caller's own profile, by id. Anyone else's is a 404."""
        expert = await self.session.scalar(
            select(Expert).where(
                Expert.id == expert_id,
                Expert.user_id == user.id,
                Expert.deleted_at.is_(None),
            )
        )
        if expert is None:
            raise NotFound("Expert not found.")
        return expert

    # ------------------------------------------------------------ update

    async def update_own(self, user: User, **fields) -> Expert:
        """Edit the caller's own profile. Moderation fields are refused."""
        expert = await self.get_own(user)

        for forbidden in ("verified", "rating_average", "rating_count"):
            if forbidden in fields and fields[forbidden] is not None:
                raise PermissionDenied(
                    "That field is set by moderation, not by the expert.",
                    details={"field": forbidden},
                )

        status = fields.get("status")
        if status is not None:
            requested = ExpertStatus(status)
            if not requested.is_self_assignable:
                raise PermissionDenied(
                    "An expert cannot put their own profile into that state.",
                    details={
                        "requested": requested.value,
                        "allowed": [
                            item.value
                            for item in ExpertStatus
                            if item.is_self_assignable
                        ],
                    },
                )
            expert.status = requested.value

        languages = fields.get("languages")
        specialties = fields.get("specialties")
        timezone = fields.get("timezone")
        if any(item is not None for item in (languages, specialties, timezone)):
            self._validate(
                languages=languages if languages is not None else expert.languages,
                specialties=(
                    specialties if specialties is not None else expert.specialties
                ),
                timezone=timezone or expert.timezone,
                experience_years=(
                    fields.get("experience_years")
                    if fields.get("experience_years") is not None
                    else expert.experience_years
                ),
            )

        for field in (
            "display_name",
            "headline",
            "bio",
            "avatar_key",
            "experience_years",
            "timezone",
        ):
            value = fields.get(field)
            if value is not None:
                setattr(expert, field, value)
        if languages is not None:
            expert.languages = sorted(set(languages))
        if specialties is not None:
            expert.specialties = sorted(set(specialties))

        await self.session.flush()
        return expert

    # ------------------------------------------- moderation (no routes yet)

    async def approve(self, expert_id: uuid.UUID) -> Expert:
        """Make a profile public. For a future admin surface only."""
        expert = await self._load(expert_id)
        expert.status = ExpertStatus.ACTIVE.value
        await self.session.flush()
        logger.info("expert_approved", expert_id=str(expert.id))
        return expert

    async def verify(self, expert_id: uuid.UUID, *, verified: bool = True) -> Expert:
        expert = await self._load(expert_id)
        expert.verified = verified
        await self.session.flush()
        logger.info(
            "expert_verification_changed",
            expert_id=str(expert.id),
            verified=verified,
        )
        return expert

    async def suspend(self, expert_id: uuid.UUID, *, reason: str | None = None) -> Expert:
        expert = await self._load(expert_id)
        expert.status = ExpertStatus.SUSPENDED.value
        await self.session.flush()
        logger.warning(
            "expert_suspended", expert_id=str(expert.id), reason=reason
        )

        # New call tokens are refused by the call policy from here on; calls
        # already live are stopped now (B10). See docs/call_authorization.md.
        from app.services.calls.factory import get_call_provider
        from app.services.calls.service import CallService

        await CallService(self.session, get_call_provider()).terminate_for_expert(
            expert.id
        )
        return expert

    async def reactivate(self, expert_id: uuid.UUID) -> Expert:
        expert = await self._load(expert_id)
        expert.status = ExpertStatus.ACTIVE.value
        await self.session.flush()
        logger.info("expert_reactivated", expert_id=str(expert.id))
        return expert

    async def _load(self, expert_id: uuid.UUID) -> Expert:
        expert = await self.session.scalar(
            select(Expert).where(Expert.id == expert_id)
        )
        if expert is None:
            raise NotFound("Expert not found.")
        return expert


class ExpertServiceManager:
    """An expert's priced offerings, validated against the catalogue."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _definition(self, definition_id: uuid.UUID) -> ServiceDefinition:
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == definition_id,
                ServiceDefinition.active.is_(True),
            )
        )
        if definition is None:
            raise NotFound("That service is not in the catalogue.")
        return definition

    def _check_offerable(
        self, definition: ServiceDefinition, delivery_type: DeliveryType
    ) -> None:
        """Can this definition be sold by an expert, through this channel?"""
        modes = {str(mode) for mode in (definition.fulfillment_modes or [])}
        if not modes & {FulfillmentMode.EXPERT.value, FulfillmentMode.HYBRID.value}:
            raise ServiceNotOfferable(
                f"'{definition.code}' is delivered automatically and cannot be "
                "offered by an expert.",
                details={
                    "service_code": definition.code,
                    "fulfillment_modes": sorted(modes),
                },
            )

        capability = DELIVERY_CAPABILITY[delivery_type]
        if not getattr(definition, capability, False):
            raise ServiceNotOfferable(
                f"'{definition.code}' does not support "
                f"{delivery_type.value} delivery.",
                details={
                    "service_code": definition.code,
                    "delivery_type": delivery_type.value,
                    "supported": [
                        channel.value
                        for channel, flag in DELIVERY_CAPABILITY.items()
                        if getattr(definition, flag, False)
                    ],
                },
            )

    async def create(
        self,
        expert: Expert,
        *,
        service_definition_id: uuid.UUID,
        title: str,
        description: str | None,
        delivery_type: DeliveryType,
        duration_minutes: int,
        price_minor: int,
        currency: str,
    ) -> ExpertService:
        definition = await self._definition(service_definition_id)
        self._check_offerable(definition, delivery_type)

        if price_minor < 0:
            raise InvalidExpertData("A price cannot be negative.")
        if not 5 <= duration_minutes <= 600:
            raise InvalidExpertData(
                "Duration must be between 5 and 600 minutes."
            )
        if len(currency) != 3 or not currency.isalpha():
            raise InvalidExpertData(f"Not an ISO-4217 currency: {currency!r}")

        offering = ExpertService(
            expert_id=expert.id,
            service_definition_id=definition.id,
            title=title.strip(),
            description=(description or "").strip() or None,
            delivery_type=delivery_type.value,
            duration_minutes=duration_minutes,
            price_minor=price_minor,
            currency=currency.upper(),
            active=True,
        )
        self.session.add(offering)
        await self.session.flush()

        logger.info(
            "expert_service_created",
            expert_id=str(expert.id),
            expert_service_id=str(offering.id),
            service_code=definition.code,
            delivery_type=delivery_type.value,
        )
        return offering

    async def get_own(self, expert: Expert, service_id: uuid.UUID) -> ExpertService:
        offering = await self.session.scalar(
            select(ExpertService).where(
                ExpertService.id == service_id,
                ExpertService.expert_id == expert.id,
                ExpertService.deleted_at.is_(None),
            )
        )
        if offering is None:
            raise NotFound("Service not found.")
        return offering

    async def get_public(self, service_id: uuid.UUID) -> ExpertService:
        """A bookable offering: active, on an active expert."""
        offering = await self.session.scalar(
            select(ExpertService)
            .join(Expert, Expert.id == ExpertService.expert_id)
            .where(
                ExpertService.id == service_id,
                ExpertService.active.is_(True),
                ExpertService.deleted_at.is_(None),
                Expert.status == ExpertStatus.ACTIVE.value,
                Expert.deleted_at.is_(None),
            )
        )
        if offering is None:
            raise NotFound("Service not found.")
        return offering

    async def update(
        self, expert: Expert, service_id: uuid.UUID, **fields
    ) -> ExpertService:
        """Edit an offering.

        Changing the price here does **not** change what past orders cost:
        every order carries its own snapshot.
        """
        offering = await self.get_own(expert, service_id)

        delivery = fields.get("delivery_type")
        if delivery is not None:
            definition = await self._definition(offering.service_definition_id)
            self._check_offerable(definition, DeliveryType(delivery))
            offering.delivery_type = DeliveryType(delivery).value

        for field in (
            "title",
            "description",
            "duration_minutes",
            "price_minor",
            "active",
        ):
            value = fields.get(field)
            if value is not None:
                setattr(offering, field, value)

        currency = fields.get("currency")
        if currency is not None:
            offering.currency = currency.upper()

        await self.session.flush()
        return offering

    async def deactivate(self, expert: Expert, service_id: uuid.UUID) -> ExpertService:
        """Stop selling it. Never deleted: past orders point at it."""
        offering = await self.get_own(expert, service_id)
        offering.active = False
        await self.session.flush()
        return offering

    async def list_for_expert(
        self, expert_id: uuid.UUID, *, active_only: bool = True
    ) -> list[ExpertService]:
        statement = select(ExpertService).where(
            ExpertService.expert_id == expert_id,
            ExpertService.deleted_at.is_(None),
        )
        if active_only:
            statement = statement.where(ExpertService.active.is_(True))
        return list(await self.session.scalars(statement))

    async def effective_capabilities(self, offering: ExpertService) -> dict[str, bool]:
        """The offering's channels AND the definition's.

        The client uses this for button visibility. Computing it as an
        intersection means a definition losing video support immediately
        removes the button, without an expert having to edit anything.
        """
        definition = await self.session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.id == offering.service_definition_id
            )
        )
        delivery = DeliveryType(offering.delivery_type)
        return {
            "supports_chat": bool(
                definition and definition.supports_chat
            )
            and delivery is DeliveryType.CHAT,
            "supports_voice": bool(
                definition and definition.supports_voice
            )
            and delivery is DeliveryType.VOICE,
            "supports_video": bool(
                definition and definition.supports_video
            )
            and delivery is DeliveryType.VIDEO,
        }


class AvailabilityManager:
    """The expert's weekly schedule and its exceptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_schedule(self, expert_id: uuid.UUID) -> list[ExpertAvailability]:
        return list(
            await self.session.scalars(
                select(ExpertAvailability)
                .where(ExpertAvailability.expert_id == expert_id)
                .order_by(
                    ExpertAvailability.weekday,
                    ExpertAvailability.start_local_time,
                )
            )
        )

    async def add_window(
        self,
        expert: Expert,
        *,
        weekday: int,
        start_local_time,
        end_local_time,
        timezone: str | None = None,
    ) -> ExpertAvailability:
        if not 0 <= weekday <= 6:
            raise InvalidExpertData("Weekday must be 0 (Monday) to 6 (Sunday).")
        if start_local_time >= end_local_time:
            raise InvalidExpertData(
                "A window must start before it ends. For a window that "
                "crosses midnight, add one window per local day."
            )

        resolved = timezone or expert.timezone
        zone(resolved)

        window = ExpertAvailability(
            expert_id=expert.id,
            weekday=weekday,
            start_local_time=start_local_time,
            end_local_time=end_local_time,
            timezone=resolved,
            active=True,
        )
        self.session.add(window)
        await self.session.flush()
        return window

    async def remove_window(
        self, expert: Expert, window_id: uuid.UUID
    ) -> None:
        window = await self.session.scalar(
            select(ExpertAvailability).where(
                ExpertAvailability.id == window_id,
                ExpertAvailability.expert_id == expert.id,
            )
        )
        if window is None:
            raise NotFound("Availability window not found.")
        await self.session.delete(window)
        await self.session.flush()

    async def list_exceptions(
        self, expert_id: uuid.UUID, *, since: datetime | None = None
    ) -> list[ExpertAvailabilityException]:
        statement = select(ExpertAvailabilityException).where(
            ExpertAvailabilityException.expert_id == expert_id
        )
        if since is not None:
            statement = statement.where(
                ExpertAvailabilityException.ends_at_utc >= since
            )
        return list(
            await self.session.scalars(
                statement.order_by(ExpertAvailabilityException.starts_at_utc)
            )
        )

    async def add_exception(
        self,
        expert: Expert,
        *,
        exception_type: AvailabilityExceptionType,
        starts_at_utc: datetime,
        ends_at_utc: datetime,
        reason: str | None = None,
    ) -> ExpertAvailabilityException:
        if starts_at_utc >= ends_at_utc:
            raise InvalidExpertData("An exception must start before it ends.")

        exception = ExpertAvailabilityException(
            expert_id=expert.id,
            exception_type=exception_type.value,
            starts_at_utc=starts_at_utc,
            ends_at_utc=ends_at_utc,
            reason=(reason or "").strip() or None,
        )
        self.session.add(exception)
        await self.session.flush()
        logger.info(
            "expert_availability_exception_added",
            expert_id=str(expert.id),
            exception_type=exception_type.value,
        )
        return exception

    async def remove_exception(
        self, expert: Expert, exception_id: uuid.UUID
    ) -> None:
        exception = await self.session.scalar(
            select(ExpertAvailabilityException).where(
                ExpertAvailabilityException.id == exception_id,
                ExpertAvailabilityException.expert_id == expert.id,
            )
        )
        if exception is None:
            raise NotFound("Exception not found.")
        await self.session.delete(exception)
        await self.session.flush()

    async def purge_expired(self, expert_id: uuid.UUID) -> int:
        """Housekeeping: exceptions entirely in the past are noise."""
        now = datetime.now(UTC)
        rows = list(
            await self.session.scalars(
                select(ExpertAvailabilityException).where(
                    ExpertAvailabilityException.expert_id == expert_id,
                    ExpertAvailabilityException.ends_at_utc < now,
                )
            )
        )
        for row in rows:
            await self.session.delete(row)
        await self.session.flush()
        return len(rows)
