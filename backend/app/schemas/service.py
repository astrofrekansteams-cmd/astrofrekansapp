from __future__ import annotations

import uuid

from app.db.models.service import ServiceDefinition
from app.domain.marketplace import FulfillmentMode, ServiceCategory
from app.schemas.common import APIModel


class ServiceDefinitionResponse(APIModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    category: ServiceCategory
    fulfillment_modes: list[FulfillmentMode]
    estimated_duration_minutes: int | None = None

    requires_birth_data: bool
    requires_partner_data: bool
    requires_question: bool

    supports_chat: bool
    supports_voice: bool
    supports_video: bool
    supports_appointment: bool
    supports_automated_report: bool

    requires_premium: bool
    active: bool


def service_to_schema(row: ServiceDefinition) -> ServiceDefinitionResponse:
    return ServiceDefinitionResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        category=ServiceCategory(row.category),
        fulfillment_modes=[FulfillmentMode(mode) for mode in row.fulfillment_modes],
        estimated_duration_minutes=row.estimated_duration_minutes,
        requires_birth_data=row.requires_birth_data,
        requires_partner_data=row.requires_partner_data,
        requires_question=row.requires_question,
        supports_chat=row.supports_chat,
        supports_voice=row.supports_voice,
        supports_video=row.supports_video,
        supports_appointment=row.supports_appointment,
        supports_automated_report=row.supports_automated_report,
        requires_premium=row.requires_premium,
        active=row.active,
    )
