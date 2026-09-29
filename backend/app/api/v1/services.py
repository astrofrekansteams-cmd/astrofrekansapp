from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.domain.marketplace import FulfillmentMode, ServiceCategory
from app.schemas.service import ServiceDefinitionResponse, service_to_schema
from app.services.catalog.service import CatalogService

router = APIRouter(prefix="/services", tags=["catalog"])


@router.get(
    "",
    response_model=list[ServiceDefinitionResponse],
    summary="The service catalogue",
    description=(
        "Everything Astrofrekans can deliver, and how: automated (engine plus "
        "Astro AI), expert (a real astrologer) or hybrid (engine pre-analysis, "
        "expert consultation). The client uses `requires_*` to know what to "
        "collect before an order can be created."
    ),
)
async def list_services(
    session: DbSession,
    category: ServiceCategory | None = Query(default=None),
    fulfillment_mode: FulfillmentMode | None = Query(default=None),
    include_inactive: bool = Query(
        default=False, description="Include services that are not shipped yet."
    ),
) -> list[ServiceDefinitionResponse]:
    rows = await CatalogService(session).list_services(
        category=category,
        fulfillment_mode=fulfillment_mode,
        include_inactive=include_inactive,
    )
    return [service_to_schema(row) for row in rows]


@router.get(
    "/{code}",
    response_model=ServiceDefinitionResponse,
    summary="One service by code",
)
async def get_service(code: str, session: DbSession) -> ServiceDefinitionResponse:
    return service_to_schema(await CatalogService(session).get_by_code(code))
