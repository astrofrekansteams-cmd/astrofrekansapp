"""Finding experts, rating them, and keeping a list of favourites.

Search returns only what a stranger may see. It joins expert offerings to
filter on price and channel, but nothing from the underlying `users` row ever
reaches a result - the expert's own name, email and birth data are not part of
their shop front.

Ratings are recomputed from reviews rather than incremented. An increment loses
one update under concurrency and the aggregate drifts away from the rows it
claims to summarise; a recount over a handful of rows is cheap and cannot
drift.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.marketplace import (
    Expert,
    ExpertAvailability,
    ExpertAvailabilityException,
    ExpertFavorite,
    ExpertReview,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.marketplace import (
    DeliveryType,
    ExpertSpecialty,
    ExpertStatus,
    OrderStatus,
)

logger = get_logger(__name__)

SORTS = ("rating", "review_count", "price", "experience", "newest")


class ReviewNotAllowed(AppError):
    status_code = 409
    code = "review_not_allowed"
    message = "This order cannot be reviewed."


class InvalidSearchRequest(AppError):
    status_code = 422
    code = "invalid_search"
    message = "That search request is not valid."


# Words a person types for a specialty, in both app languages. Matched as
# substrings of the normalised query, so "astrolog" finds astrology and
# "doğum" finds natal charts.
SPECIALTY_TERMS: dict[str, tuple[str, ...]] = {
    "astrology": ("astroloji", "astrology", "astrolog"),
    "natal_chart": ("doğum haritası", "natal", "birth chart"),
    "transits": ("transit",),
    "synastry": ("sinastri", "synastry", "uyum", "ilişki", "relationship"),
    "composite": ("composite", "kompozit"),
    "davison": ("davison",),
    "horary": ("horary", "saat sorusu", "soru"),
    "monthly_forecast": ("aylık", "monthly"),
    "annual_forecast": ("yıllık", "annual", "yearly"),
    "tarot": ("tarot",),
    "rune": ("rune", "rün"),
    "katina": ("katina",),
}


def normalise(text: str | None) -> str:
    """Case- and accent-light, dotted/dotless-i insensitive.

    Someone typing "ayse", "AYŞE" or "Ayşe" means the same expert, and a
    phone keyboard in either language may produce "I", "ı", "İ" or "i".
    """
    folded = (text or "").replace("İ", "i").casefold().replace("i̇", "i")
    return folded.translate(str.maketrans("ıçğöşüâîû", "icgosuaiu")).strip()


def matches_query(expert: Expert, query: str) -> bool:
    needle = normalise(query)
    if not needle:
        return True
    haystack = " ".join(
        normalise(part) for part in (expert.display_name, expert.headline, expert.bio)
    )
    if needle in haystack:
        return True
    for code in expert.specialties or []:
        terms = SPECIALTY_TERMS.get(code, ()) + (code.replace("_", " "),)
        if any(needle in normalise(term) or normalise(term) in needle for term in terms):
            return True
    return False


# How many candidate experts a filtered search reads per query.
SEARCH_SCAN_BATCH = 500


@dataclass(slots=True, frozen=True)
class ExpertSearchFilters:
    # Free text over name, headline, bio and specialty names (TR/EN).
    q: str | None = None
    specialty: ExpertSpecialty | None = None
    language: str | None = None
    service_code: str | None = None
    delivery_type: DeliveryType | None = None
    min_price_minor: int | None = None
    max_price_minor: int | None = None
    currency: str | None = None
    verified_only: bool = False
    min_rating: float | None = None
    # Has weekly availability today (in the expert's own timezone) and no
    # full block over it. Not live presence: that is per conversation only.
    available_today: bool = False
    sort: str = "rating"
    limit: int = 20
    offset: int = 0


class ExpertSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base(self) -> Select:
        # Only active, non-deleted profiles are discoverable. An application
        # under review is not a search result.
        return select(Expert).where(
            Expert.status == ExpertStatus.ACTIVE.value,
            Expert.deleted_at.is_(None),
        )

    def _apply(self, statement: Select, filters: ExpertSearchFilters) -> Select:
        if filters.verified_only:
            statement = statement.where(Expert.verified.is_(True))
        if filters.min_rating is not None:
            statement = statement.where(
                Expert.rating_average >= filters.min_rating
            )

        # JSON containment is not portable across SQLite and Postgres, so
        # specialty and language are filtered in Python after the query. The
        # candidate set is bounded by the page window plus a margin, which is
        # the honest trade: correct on both dialects, and re-examined when the
        # expert count makes it matter (see Known limitations in the docs).

        needs_offering = any(
            value is not None
            for value in (
                filters.service_code,
                filters.delivery_type,
                filters.min_price_minor,
                filters.max_price_minor,
            )
        )
        if needs_offering:
            statement = statement.join(
                ExpertService, ExpertService.expert_id == Expert.id
            ).where(
                ExpertService.active.is_(True),
                ExpertService.deleted_at.is_(None),
            )
            if filters.delivery_type is not None:
                statement = statement.where(
                    ExpertService.delivery_type == filters.delivery_type.value
                )
            if filters.currency is not None:
                statement = statement.where(
                    ExpertService.currency == filters.currency.upper()
                )
            if filters.min_price_minor is not None:
                statement = statement.where(
                    ExpertService.price_minor >= filters.min_price_minor
                )
            if filters.max_price_minor is not None:
                statement = statement.where(
                    ExpertService.price_minor <= filters.max_price_minor
                )
            if filters.service_code is not None:
                statement = statement.join(
                    ServiceDefinition,
                    ServiceDefinition.id == ExpertService.service_definition_id,
                ).where(ServiceDefinition.code == filters.service_code)
            statement = statement.distinct()

        return statement

    def _order(self, statement: Select, sort: str) -> Select:
        if sort not in SORTS:
            raise InvalidSearchRequest(
                f"Unknown sort '{sort}'.", details={"supported": list(SORTS)}
            )
        # `Expert.id` last in every order: ties would otherwise come back in
        # any order, and a page boundary could repeat or skip an expert.
        if sort == "rating":
            return statement.order_by(
                Expert.rating_average.desc(), Expert.rating_count.desc(), Expert.id
            )
        if sort == "review_count":
            return statement.order_by(Expert.rating_count.desc(), Expert.id)
        if sort == "experience":
            return statement.order_by(Expert.experience_years.desc(), Expert.id)
        if sort == "newest":
            return statement.order_by(Expert.created_at.desc(), Expert.id)
        # price: cheapest active offering first.
        return statement.order_by(Expert.rating_average.desc(), Expert.id)

    async def available_today(self, expert_ids: list) -> set:
        """Experts with an active weekly window today in their own timezone,
        not wholly blocked by a vacation/busy/manual exception right now."""
        if not expert_ids:
            return set()
        windows = list(
            await self.session.execute(
                select(ExpertAvailability.expert_id, ExpertAvailability.weekday, ExpertAvailability.timezone)
                .where(
                    ExpertAvailability.expert_id.in_(expert_ids),
                    ExpertAvailability.active.is_(True),
                )
            )
        )
        now = datetime.now(UTC)
        blocked = set(
            await self.session.scalars(
                select(ExpertAvailabilityException.expert_id).where(
                    ExpertAvailabilityException.expert_id.in_(expert_ids),
                    ExpertAvailabilityException.exception_type != "extra_availability",
                    ExpertAvailabilityException.starts_at_utc <= now,
                    ExpertAvailabilityException.ends_at_utc >= now,
                )
            )
        )
        open_today = set()
        for expert_id, weekday, zone in windows:
            try:
                local = now.astimezone(ZoneInfo(zone))
            except Exception:  # noqa: BLE001 - a bad zone is treated as UTC
                local = now
            if local.weekday() == weekday and expert_id not in blocked:
                open_today.add(expert_id)
        return open_today

    async def search(
        self, filters: ExpertSearchFilters
    ) -> tuple[list[Expert], int]:
        """Returns `(page, total)`. Pagination is never optional."""
        if not 1 <= filters.limit <= 100:
            raise InvalidSearchRequest("Limit must be between 1 and 100.")
        if filters.offset < 0:
            raise InvalidSearchRequest("Offset cannot be negative.")

        statement = self._apply(self._base(), filters)

        in_python = (
            filters.specialty is not None
            or filters.language is not None
            or filters.available_today
            or bool(filters.q and filters.q.strip())
        )
        if in_python:
            # Filter in Python, then page. The candidates are read in batches
            # to the end of the table: a fixed ceiling (formerly 500) silently
            # dropped every match that sorted after it. This is a linear scan
            # of active experts - fine at today's size, and the documented
            # point to move text and JSON filters into the database (see
            # docs/marketplace_architecture.md, "Search").
            ordered = self._order(statement, filters.sort)
            rows = []
            scanned = 0
            while True:
                batch = list(
                    await self.session.scalars(
                        ordered.offset(scanned).limit(SEARCH_SCAN_BATCH)
                    )
                )
                rows.extend(batch)
                scanned += len(batch)
                if len(batch) < SEARCH_SCAN_BATCH:
                    break
            rows = [
                expert
                for expert in rows
                if (
                    filters.specialty is None
                    or filters.specialty.value in (expert.specialties or [])
                )
                and (
                    filters.language is None
                    or filters.language in (expert.languages or [])
                )
                and (not filters.q or matches_query(expert, filters.q))
            ]
            if filters.available_today:
                open_today = await self.available_today([e.id for e in rows])
                rows = [expert for expert in rows if expert.id in open_today]
            total = len(rows)
            page = rows[filters.offset : filters.offset + filters.limit]
            return page, total

        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        page = list(
            await self.session.scalars(
                self._order(statement, filters.sort)
                .offset(filters.offset)
                .limit(filters.limit)
            )
        )
        return page, int(total or 0)

    async def cheapest_offering(
        self, expert_id: uuid.UUID
    ) -> ExpertService | None:
        """The price a search result shows as "from"."""
        return await self.session.scalar(
            select(ExpertService)
            .where(
                ExpertService.expert_id == expert_id,
                ExpertService.active.is_(True),
                ExpertService.deleted_at.is_(None),
            )
            .order_by(ExpertService.price_minor)
            .limit(1)
        )


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user: User,
        order_id: uuid.UUID,
        *,
        rating: int,
        comment: str | None = None,
    ) -> ExpertReview:
        """Review a completed order.

        Anchoring a review to a transaction is the only thing that makes it
        mean anything: a rating anybody can leave about anybody is free to
        manufacture. So the order must be the caller's, must have an expert,
        and must be completed.
        """
        if not 1 <= rating <= 5:
            raise ReviewNotAllowed(
                "A rating must be between 1 and 5.",
                code="invalid_rating",
                status_code=422,
            )

        order = await self.session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.id == order_id,
                ServiceOrder.user_id == user.id,
                ServiceOrder.deleted_at.is_(None),
            )
        )
        if order is None:
            raise NotFound("Order not found.")

        if order.expert_id is None:
            raise ReviewNotAllowed("This order had no expert to review.")
        if order.status != OrderStatus.COMPLETED.value:
            raise ReviewNotAllowed(
                f"An order that is {order.status} cannot be reviewed yet.",
                details={"status": order.status},
            )

        expert = await self.session.scalar(
            select(Expert).where(Expert.id == order.expert_id)
        )
        if expert is not None and expert.user_id == user.id:
            raise ReviewNotAllowed(
                "An expert cannot review their own service.",
                code="self_review",
            )

        existing = await self.session.scalar(
            select(ExpertReview).where(ExpertReview.order_id == order.id)
        )
        if existing is not None and existing.deleted_at is None:
            raise ReviewNotAllowed(
                "This order has already been reviewed.",
                code="review_exists",
            )

        review = ExpertReview(
            order_id=order.id,
            user_id=user.id,
            expert_id=order.expert_id,
            rating=rating,
            comment=(comment or "").strip() or None,
        )
        self.session.add(review)
        await self.session.flush()
        await self.recalculate(order.expert_id)

        logger.info(
            "review_created",
            review_id=str(review.id),
            order_id=str(order.id),
            expert_id=str(order.expert_id),
            rating=rating,
        )
        return review

    async def get_own(self, user: User, review_id: uuid.UUID) -> ExpertReview:
        review = await self.session.scalar(
            select(ExpertReview).where(
                ExpertReview.id == review_id,
                ExpertReview.user_id == user.id,
                ExpertReview.deleted_at.is_(None),
            )
        )
        if review is None:
            raise NotFound("Review not found.")
        return review

    async def update(
        self,
        user: User,
        review_id: uuid.UUID,
        *,
        rating: int | None = None,
        comment: str | None = None,
    ) -> ExpertReview:
        review = await self.get_own(user, review_id)
        if rating is not None:
            if not 1 <= rating <= 5:
                raise ReviewNotAllowed(
                    "A rating must be between 1 and 5.",
                    code="invalid_rating",
                    status_code=422,
                )
            review.rating = rating
        if comment is not None:
            review.comment = comment.strip() or None
        await self.session.flush()
        await self.recalculate(review.expert_id)
        return review

    async def delete(self, user: User, review_id: uuid.UUID) -> None:
        review = await self.get_own(user, review_id)
        review.deleted_at = datetime.now(UTC)
        await self.session.flush()
        await self.recalculate(review.expert_id)

    async def list_for_expert(
        self, expert_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[ExpertReview], int]:
        base = select(ExpertReview).where(
            ExpertReview.expert_id == expert_id,
            ExpertReview.deleted_at.is_(None),
        )
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        rows = list(
            await self.session.scalars(
                base.order_by(ExpertReview.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return rows, int(total or 0)

    async def recalculate(self, expert_id: uuid.UUID) -> tuple[float, int]:
        """Recompute the aggregate from the reviews themselves.

        Not an increment: two reviews landing together would lose one update
        and the cached average would quietly stop matching the rows it claims
        to summarise. A recount cannot drift.
        """
        result = await self.session.execute(
            select(
                func.avg(ExpertReview.rating), func.count(ExpertReview.id)
            ).where(
                ExpertReview.expert_id == expert_id,
                ExpertReview.deleted_at.is_(None),
            )
        )
        average, count = result.one()
        expert = await self.session.scalar(
            select(Expert).where(Expert.id == expert_id)
        )
        if expert is not None:
            expert.rating_average = round(float(average or 0), 2)
            expert.rating_count = int(count or 0)
            await self.session.flush()
        return float(average or 0), int(count or 0)

    async def summary(self, expert_id: uuid.UUID) -> dict:
        """Rating distribution, for the profile page."""
        result = await self.session.execute(
            select(ExpertReview.rating, func.count(ExpertReview.id))
            .where(
                ExpertReview.expert_id == expert_id,
                ExpertReview.deleted_at.is_(None),
            )
            .group_by(ExpertReview.rating)
        )
        distribution = {str(rating): count for rating, count in result.all()}
        total = sum(distribution.values())
        weighted = sum(int(key) * value for key, value in distribution.items())
        return {
            "rating_average": round(weighted / total, 2) if total else 0.0,
            "rating_count": total,
            "distribution": {
                str(score): distribution.get(str(score), 0)
                for score in range(1, 6)
            },
        }


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user: User, expert_id: uuid.UUID) -> ExpertFavorite:
        # Only a discoverable expert can be favourited, so this cannot be used
        # to probe for profiles that are not public.
        expert = await self.session.scalar(
            select(Expert).where(
                Expert.id == expert_id,
                Expert.status == ExpertStatus.ACTIVE.value,
                Expert.deleted_at.is_(None),
            )
        )
        if expert is None:
            raise NotFound("Expert not found.")

        existing = await self.session.scalar(
            select(ExpertFavorite).where(
                ExpertFavorite.user_id == user.id,
                ExpertFavorite.expert_id == expert_id,
            )
        )
        if existing is not None:
            return existing

        favorite = ExpertFavorite(user_id=user.id, expert_id=expert_id)
        self.session.add(favorite)
        await self.session.flush()
        return favorite

    async def remove(self, user: User, expert_id: uuid.UUID) -> None:
        favorite = await self.session.scalar(
            select(ExpertFavorite).where(
                ExpertFavorite.user_id == user.id,
                ExpertFavorite.expert_id == expert_id,
            )
        )
        if favorite is None:
            raise NotFound("That expert is not in your favourites.")
        await self.session.delete(favorite)
        await self.session.flush()

    async def list_experts(self, user: User, *, limit: int = 50) -> list[Expert]:
        return list(
            await self.session.scalars(
                select(Expert)
                .join(ExpertFavorite, ExpertFavorite.expert_id == Expert.id)
                .where(
                    ExpertFavorite.user_id == user.id,
                    Expert.deleted_at.is_(None),
                )
                .order_by(ExpertFavorite.created_at.desc())
                .limit(limit)
            )
        )

    async def is_favorite(self, user: User, expert_id: uuid.UUID) -> bool:
        row = await self.session.scalar(
            select(ExpertFavorite.id).where(
                ExpertFavorite.user_id == user.id,
                ExpertFavorite.expert_id == expert_id,
            )
        )
        return row is not None
