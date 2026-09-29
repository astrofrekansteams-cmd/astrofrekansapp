"""Synastry, composite and Davison endpoints.

Every result is a snapshot: it records the fingerprint of both people's birth
data and the engine and scoring versions, so editing a saved person later
produces a *new* report instead of quietly changing one the user has read.

The compatibility score is an astrological factor index. The response says so
in ``score_semantics``, because a bare percentage next to two names reads as a
prediction, and this one is not.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import Charts, CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.exceptions import MissingBirthData
from app.core.rate_limit import RateLimit
from app.domain.compatibility import CompatibilityKind
from app.schemas.astrology import chart_to_schema
from app.schemas.compatibility import (
    CompatibilityReportResponse,
    CompatibilityInterpretRequest,
    CompatibilityReportSummary,
    CompatibilityRequest,
    CompositeResponse,
    DavisonResponse,
    HouseOverlayResponse,
    SynastryAspectResponse,
    SynastryResponse,
    ThemeScoreResponse,
)
from app.domain.ai import Locale, ReportType
from app.schemas.ai import ReportJobResponse, ReportResponse
from app.services.ai.factory import ai_available, build_report_service
from app.services.ai.provider import AINotConfigured
from app.services.compatibility.service import CompatibilityService
from app.services.coins.unlock import coin_gate
from app.services.features import Feature


router = APIRouter(prefix="/compatibility", tags=["compatibility"])

_limit = Depends(RateLimit("60/hour", scope="compatibility"))
_interpret_limit = Depends(
    UserRateLimit(
        settings.compatibility_interpret_rate_limit,
        scope="compatibility_interpret",
        code="ai_rate_limited",
    )
)

# Each calculation kind has its own reading: a different prompt, not one
# prompt with the chart type swapped in.
_READING_TYPES = {
    "synastry": ReportType.SYNASTRY_READING,
    "composite": ReportType.COMPOSITE_READING,
    "davison": ReportType.DAVISON_READING,
}


def _service(session, charts) -> CompatibilityService:
    return CompatibilityService(session, charts)


@router.post(
    "/synastry",
    response_model=SynastryResponse,
    dependencies=[_limit],
    summary="Synastry between two charts",
    description=(
        "Inter-aspects, contacts to each other's angles, and **directional** "
        "house overlays: A's planets in B's houses is a different statement "
        "from B's planets in A's houses, and both are returned."
    ),
)
async def synastry(
    payload: CompatibilityRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> SynastryResponse:
    gate = await coin_gate(session, user, Feature.SYNASTRY, request)
    service = _service(session, charts)
    person_a = await service.resolve(user, payload.person_a, house_system=payload.house_system)
    person_b = await service.resolve(user, payload.person_b, house_system=payload.house_system)

    fingerprint = service._fingerprint(CompatibilityKind.SYNASTRY, person_a, person_b)
    if not payload.refresh:
        cached = await service._cached(fingerprint)
        stored = (
            await service._existing_report(user, fingerprint)
            if cached is not None
            else None
        )
        if cached is not None and stored is not None:
            await gate.charge()
            await session.commit()
            return SynastryResponse.model_validate(
                {**cached, "cached": True, "report_id": stored.id}
            )

    result = service._synastry.analyse(person_a.chart, person_b.chart)
    response = SynastryResponse(
        overall_score=result.overall_score,
        score_semantics=result.score_semantics,
        themes=[
            ThemeScoreResponse(
                theme=item.theme,
                score=item.score,
                strength=item.strength,
                positive_factors=item.positive_factors,
                challenging_factors=item.challenging_factors,
                factor_ids=item.factor_ids,
            )
            for item in result.themes
        ],
        aspects=[
            SynastryAspectResponse(
                id=item.id,
                person_a_body=item.person_a_body,
                person_a_angle=item.person_a_angle,
                person_b_body=item.person_b_body,
                person_b_angle=item.person_b_angle,
                aspect=item.aspect,
                nature=item.nature,
                orb=item.orb,
                max_orb=item.max_orb,
                weight=item.weight,
                themes=item.themes,
                label=item.label,
            )
            for item in result.aspects
        ],
        overlays_a_in_b=[_overlay(item) for item in result.overlays_a_in_b],
        overlays_b_in_a=[_overlay(item) for item in result.overlays_b_in_a],
        highlights=result.highlights,
        source_factors=result.source_factors,
        warnings=result.warnings,
        person_a_label=person_a.label,
        person_b_label=person_b.label,
        engine_version=result.engine_version,
        scoring_version=result.scoring_version,
    )

    report = await service._store(
        user=user,
        kind=CompatibilityKind.SYNASTRY,
        a=person_a,
        b=person_b,
        fingerprint=fingerprint,
        payload=response.model_dump(mode="json"),
    )
    await gate.charge()
    await session.commit()
    return response.model_copy(update={"report_id": report.id})


def _overlay(item) -> HouseOverlayResponse:  # noqa: ANN001
    return HouseOverlayResponse(
        id=item.id,
        direction=item.direction,
        planet=item.planet,
        house=item.house,
        longitude=item.longitude,
        weight=item.weight,
        themes=item.themes,
        label=item.label,
    )


@router.post(
    "/composite",
    response_model=CompositeResponse,
    dependencies=[_limit],
    summary="Midpoint composite chart",
    description=(
        "A chart of midpoints - not a moment that ever existed in the sky. "
        "Midpoints are taken along the short arc, so 359 and 1 degree meet at "
        "0; points that are exactly opposite have no unique midpoint and are "
        "listed in `ambiguous_midpoints`."
    ),
)
async def composite(
    payload: CompatibilityRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> CompositeResponse:
    gate = await coin_gate(session, user, Feature.COMPOSITE, request)
    service = _service(session, charts)
    person_a = await service.resolve(user, payload.person_a, house_system=payload.house_system)
    person_b = await service.resolve(user, payload.person_b, house_system=payload.house_system)

    fingerprint = service._fingerprint(CompatibilityKind.COMPOSITE, person_a, person_b)
    if not payload.refresh:
        cached = await service._cached(fingerprint)
        stored = (
            await service._existing_report(user, fingerprint)
            if cached is not None
            else None
        )
        if cached is not None and stored is not None:
            await gate.charge()
            await session.commit()
            return CompositeResponse.model_validate(
                {**cached, "cached": True, "report_id": stored.id}
            )

    result = service._composite.composite(person_a.chart, person_b.chart)
    response = CompositeResponse(
        method=result.method,
        house_method=result.house_method,
        chart=chart_to_schema(result.chart),
        aspects=result.aspects,
        elements=result.elements,
        modalities=result.modalities,
        dominant_element=result.dominant_element,
        dominant_modality=result.dominant_modality,
        ambiguous_midpoints=result.ambiguous_midpoints,
        warnings=result.warnings,
        engine_version=result.engine_version,
    )

    report = await service._store(
        user=user,
        kind=CompatibilityKind.COMPOSITE,
        a=person_a,
        b=person_b,
        fingerprint=fingerprint,
        payload=response.model_dump(mode="json"),
        derived_chart=result.chart,
    )
    await gate.charge()
    await session.commit()
    return response.model_copy(update={"report_id": report.id})


@router.post(
    "/davison",
    response_model=DavisonResponse,
    dependencies=[_limit],
    summary="Davison relationship chart",
    description=(
        "A real chart for the midpoint in time between the two births and the "
        "geographic midpoint between the two birthplaces. The time midpoint is "
        "taken in UTC and the place midpoint on the sphere, so the date line "
        "and DST do not distort it."
    ),
)
async def davison(
    payload: CompatibilityRequest,
    request: Request,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> DavisonResponse:
    gate = await coin_gate(session, user, Feature.DAVISON, request)
    service = _service(session, charts)
    person_a = await service.resolve(user, payload.person_a, house_system=payload.house_system)
    person_b = await service.resolve(user, payload.person_b, house_system=payload.house_system)

    fingerprint = service._fingerprint(CompatibilityKind.DAVISON, person_a, person_b)
    if not payload.refresh:
        cached = await service._cached(fingerprint)
        stored = (
            await service._existing_report(user, fingerprint)
            if cached is not None
            else None
        )
        if cached is not None and stored is not None:
            await gate.charge()
            await session.commit()
            return DavisonResponse.model_validate(
                {**cached, "cached": True, "report_id": stored.id}
            )

    # The midpoint needs both birthplaces, and a chart only keeps its place
    # when time and place are both known. Missing input is the caller's
    # problem (422), not a server failure.
    if any(
        chart.subject.latitude is None or chart.subject.longitude is None
        for chart in (person_a.chart, person_b.chart)
    ):
        raise MissingBirthData(
            "A Davison chart needs the birth time and place of both people.",
            details={"required": ["birth_time", "birth_place"], "chart": "davison"},
        )

    result = service._composite.davison(
        person_a.chart, person_b.chart, house_system=payload.house_system
    )
    response = DavisonResponse(
        method=result.method,
        midpoint_utc=result.midpoint_utc,
        midpoint_latitude=result.midpoint_latitude,
        midpoint_longitude=result.midpoint_longitude,
        chart=chart_to_schema(result.chart),
        warnings=result.warnings,
        engine_version=result.engine_version,
    )

    report = await service._store(
        user=user,
        kind=CompatibilityKind.DAVISON,
        a=person_a,
        b=person_b,
        fingerprint=fingerprint,
        payload=response.model_dump(mode="json"),
        derived_chart=result.chart,
    )
    await gate.charge()
    await session.commit()
    return response.model_copy(update={"report_id": report.id})


@router.get(
    "/reports",
    response_model=list[CompatibilityReportSummary],
    summary="Your compatibility reports",
)
async def list_reports(
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
    kind: CompatibilityKind | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CompatibilityReportSummary]:
    reports = await _service(session, charts).list_reports(
        user_id=user.id, kind=kind, limit=limit
    )
    return [_summary(report) for report in reports]


@router.get(
    "/reports/{report_id}",
    response_model=CompatibilityReportResponse,
    summary="One stored report",
)
async def get_report(
    report_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    charts: Charts,
) -> CompatibilityReportResponse:
    report = await _service(session, charts).get_report(
        user_id=user.id, report_id=report_id
    )
    return CompatibilityReportResponse(
        **_summary(report).model_dump(),
        structured_result=report.structured_result,
    )


def _summary(report) -> CompatibilityReportSummary:  # noqa: ANN001
    return CompatibilityReportSummary(
        id=report.id,
        kind=CompatibilityKind(report.kind),
        person_a_label=report.person_a_label,
        person_b_label=report.person_b_label,
        person_a_ref=report.person_a_ref,
        person_b_ref=report.person_b_ref,
        engine_version=report.engine_version,
        scoring_version=report.scoring_version,
        created_at=report.created_at,
    )


def _locale(requested: Locale | None, user) -> Locale:  # noqa: ANN001
    if requested is not None:
        return requested
    preferred = (user.profile.language if user.profile else None) or "tr"
    try:
        return Locale(preferred)
    except ValueError:
        return Locale.TR


@router.post(
    "/reports/{report_id}/interpretation",
    response_model=None,
    responses={
        200: {"model": ReportResponse},
        202: {"model": ReportJobResponse},
    },
    dependencies=[_interpret_limit],
    summary="AI reading of a compatibility calculation",
    description=(
        "Interprets a stored synastry, composite or Davison calculation. The "
        "model only reads the calculated factors (planets, signs, houses, "
        "aspects, orbs, angles when present); it never calculates. Sections "
        "cite the factor ids they rest on. Cached per calculation, locale and "
        "prompt version: asking again returns the same reading unless "
        "`refresh` is set. `background=true` (default) answers 202 with a job "
        "to poll at `/ai/report-jobs/{id}`. Fails with `ai_not_configured` "
        "when no provider is set up - the calculation itself is unaffected."
    ),
)
async def interpret_compatibility(
    report_id: uuid.UUID,
    payload: CompatibilityInterpretRequest,
    user: CurrentUser,
    session: DbSession,
) -> ReportResponse | JSONResponse:
    if not ai_available():
        raise AINotConfigured()

    service = CompatibilityService(session, None)
    row = await service.get_report(user_id=user.id, report_id=report_id)
    report_type = _READING_TYPES[row.kind]

    reports = build_report_service(session)
    outcome = await reports.request(
        user,
        report_type=report_type,
        source_id=row.id,
        locale=_locale(payload.locale, user),
        refresh=payload.refresh,
        background=payload.background,
    )
    await session.commit()

    from app.api.v1.ai import deliver_report

    return await deliver_report(reports, session, user, outcome)
