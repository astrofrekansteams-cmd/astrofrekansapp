"""Reading and seeding the service catalogue."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.core.logging import get_logger
from app.db.models.service import ServiceDefinition
from app.domain.marketplace import FulfillmentMode, ServiceCategory
from app.services.catalog.definitions import CATALOG, ServiceSpec

logger = get_logger(__name__)


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_services(
        self,
        *,
        category: ServiceCategory | None = None,
        fulfillment_mode: FulfillmentMode | None = None,
        include_inactive: bool = False,
    ) -> list[ServiceDefinition]:
        statement = select(ServiceDefinition).order_by(
            ServiceDefinition.sort_order, ServiceDefinition.code
        )
        if not include_inactive:
            statement = statement.where(ServiceDefinition.active.is_(True))
        if category is not None:
            statement = statement.where(ServiceDefinition.category == category)

        rows = list(await self.session.scalars(statement))
        if fulfillment_mode is not None:
            rows = [
                row for row in rows if fulfillment_mode.value in row.fulfillment_modes
            ]
        return rows

    async def get_by_code(self, code: str) -> ServiceDefinition:
        row = await self.session.scalar(
            select(ServiceDefinition).where(ServiceDefinition.code == code)
        )
        if row is None:
            raise NotFound("Unknown service.", details={"code": code})
        return row

    async def seed(self, specs: tuple[ServiceSpec, ...] = CATALOG) -> tuple[int, int]:
        """Idempotent upsert of the catalogue. Returns (created, updated).

        Safe to run on every deploy: rows are matched by ``code``, and codes
        never change once shipped.
        """
        existing = {
            row.code: row for row in await self.session.scalars(select(ServiceDefinition))
        }
        created = updated = 0

        for spec in specs:
            row = existing.get(spec.code.value)
            if row is None:
                row = ServiceDefinition(code=spec.code.value)
                self.session.add(row)
                created += 1
            else:
                updated += 1

            row.name = spec.name
            row.description = spec.description or None
            row.category = spec.category
            row.fulfillment_modes = [mode.value for mode in spec.fulfillment_modes]
            row.estimated_duration_minutes = spec.estimated_duration_minutes
            row.requires_birth_data = spec.requires_birth_data
            row.requires_partner_data = spec.requires_partner_data
            row.requires_question = spec.requires_question
            row.supports_chat = spec.supports_chat
            row.supports_voice = spec.supports_voice
            row.supports_video = spec.supports_video
            row.supports_appointment = spec.supports_appointment
            row.supports_automated_report = spec.supports_automated_report
            row.requires_premium = spec.requires_premium
            row.active = spec.active
            row.sort_order = spec.sort_order

        await self.session.flush()
        logger.info("service_catalog_seeded", created=created, updated=updated)
        return created, updated
