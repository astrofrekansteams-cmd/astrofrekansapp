"""Domain objects -> API schemas.

Kept apart from the engines so the calculation layer never imports Pydantic,
and from the cache format so a schema change does not silently invalidate
stored payloads (the version keys do that explicitly).
"""

from __future__ import annotations

from app.domain.calendar import CosmicEvent, PersonalCosmicEvent
from app.domain.horoscope import (
    AnnualForecast,
    AreaScore,
    DailyFrequency,
    HouseActivation,
    ImportantDate,
    ImportantHour,
    MonthlyForecast,
    PeriodCluster,
    PersonalHoroscope,
    SolarReturnSummary,
    SourceFactor,
)
from app.domain.transit import HouseIngress, TransitEvent
from app.schemas.forecast import (
    AnnualForecastResponse,
    AreaScoreResponse,
    CosmicEventResponse,
    DailyFrequencyResponse,
    HoroscopeResponse,
    HouseActivationResponse,
    HouseIngressResponse,
    ImportantDateResponse,
    ImportantHourResponse,
    MonthlyForecastResponse,
    NatalContactResponse,
    PeriodClusterResponse,
    PersonalEventResponse,
    SolarReturnResponse,
    SourceFactorResponse,
    TransitPassResponse,
    TransitResponse,
)


def transit_to_schema(event: TransitEvent) -> TransitResponse:
    return TransitResponse(
        id=event.id,
        transiting_body=event.transiting_body,
        target_type=event.target_type,
        target_body=event.target_body,
        target_angle=event.target_angle,
        target_house=event.target_house,
        aspect_type=event.aspect_type,
        nature=event.nature,
        orb=event.orb,
        maximum_orb=event.maximum_orb,
        applying=event.applying,
        start_at=event.start_at,
        exact_at=event.exact_at,
        end_at=event.end_at,
        status=event.status,
        strength=event.strength,
        passes=[
            TransitPassResponse(
                pass_number=item.pass_number,
                exact_at=item.exact_at,
                direction=item.direction,
                speed=item.speed,
            )
            for item in event.passes
        ],
        affected_houses=event.affected_houses,
        window_clipped=event.window_clipped,
        engine_version=event.engine_version,
        scoring_version=event.scoring_version,
        metadata=event.metadata,
    )


def ingress_to_schema(ingress: HouseIngress) -> HouseIngressResponse:
    return HouseIngressResponse(
        id=ingress.id,
        planet=ingress.planet,
        from_house=ingress.from_house,
        to_house=ingress.to_house,
        entered_at=ingress.entered_at,
        estimated_exit_at=ingress.estimated_exit_at,
        retrograde=ingress.retrograde,
        re_entry=ingress.re_entry,
    )


def event_to_schema(event: CosmicEvent) -> CosmicEventResponse:
    return CosmicEventResponse(
        id=event.id,
        type=event.type,
        exact_at=event.exact_at,
        start_at=event.start_at,
        end_at=event.end_at,
        planet=event.planet,
        secondary_planet=event.secondary_planet,
        aspect=event.aspect,
        sign=event.sign,
        longitude=event.longitude,
        degree=event.degree,
        eclipse_subtype=event.eclipse_subtype,
        eclipse_magnitude=event.eclipse_magnitude,
        node_distance=event.node_distance,
        metadata=event.metadata,
    )


def personal_event_to_schema(item: PersonalCosmicEvent) -> PersonalEventResponse:
    return PersonalEventResponse(
        event=event_to_schema(item.event),
        affected_house=item.affected_house,
        natal_aspects=[
            NatalContactResponse(
                target_body=contact.target_body,
                target_angle=contact.target_angle,
                aspect=contact.aspect,
                orb=contact.orb,
            )
            for contact in item.natal_aspects
        ],
        strength=item.strength,
        personal_relevance=item.relevance,
        source_factors=item.source_factors,
    )


def factor_to_schema(factor: SourceFactor) -> SourceFactorResponse:
    return SourceFactorResponse(
        id=factor.id,
        kind=factor.kind,
        label=factor.label,
        contribution=factor.contribution,
        areas=factor.areas,
        at=factor.at,
        detail=factor.detail,
    )


def area_to_schema(area: AreaScore) -> AreaScoreResponse:
    return AreaScoreResponse(
        area=area.area,
        score=area.score,
        trend=area.trend,
        strength=area.strength,
        factor_ids=area.factor_ids,
    )


def hour_to_schema(hour: ImportantHour) -> ImportantHourResponse:
    return ImportantHourResponse(
        start=hour.start,
        end=hour.end,
        type=hour.type,
        strength=hour.strength,
        reason=hour.reason,
        factor_ids=hour.factor_ids,
    )


def date_to_schema(item: ImportantDate) -> ImportantDateResponse:
    return ImportantDateResponse(
        date=item.date,
        label=item.label,
        strength=item.strength,
        nature=item.nature,
        factor_ids=item.factor_ids,
    )


def cluster_to_schema(cluster: PeriodCluster) -> PeriodClusterResponse:
    return PeriodClusterResponse(
        start_at=cluster.start_at,
        end_at=cluster.end_at,
        areas=cluster.areas,
        strength=cluster.strength,
        label=cluster.label,
        source_factors=cluster.source_factors,
    )


def activation_to_schema(item: HouseActivation) -> HouseActivationResponse:
    return HouseActivationResponse(
        house=item.house,
        planets=item.planets,
        strength=item.strength,
        factor_ids=item.factor_ids,
    )


def daily_frequency_to_schema(
    frequency: DailyFrequency,
) -> DailyFrequencyResponse:
    return DailyFrequencyResponse(
        date=frequency.date,
        timezone=frequency.timezone,
        overall=frequency.overall,
        scores={
            area: area_to_schema(score) for area, score in frequency.scores.items()
        },
        important_hours=[hour_to_schema(hour) for hour in frequency.important_hours],
        influences=[factor_to_schema(factor) for factor in frequency.influences],
        message_context=frequency.message_context,
        engine_version=frequency.engine_version,
        scoring_version=frequency.scoring_version,
    )


def horoscope_to_schema(horoscope: PersonalHoroscope) -> HoroscopeResponse:
    return HoroscopeResponse(
        period=horoscope.period,
        start_at=horoscope.start_at,
        end_at=horoscope.end_at,
        timezone=horoscope.timezone,
        overall_score=horoscope.overall_score,
        areas=[area_to_schema(area) for area in horoscope.areas],
        important_dates=[date_to_schema(item) for item in horoscope.important_dates],
        important_hours=[hour_to_schema(item) for item in horoscope.important_hours],
        opportunities=horoscope.opportunities,
        challenges=horoscope.challenges,
        major_transits=[transit_to_schema(item) for item in horoscope.major_transits],
        moon_events=[event_to_schema(item) for item in horoscope.moon_events],
        house_activations=[
            activation_to_schema(item) for item in horoscope.house_activations
        ],
        key_periods=[cluster_to_schema(item) for item in horoscope.key_periods],
        source_factors=[factor_to_schema(item) for item in horoscope.source_factors],
        engine_version=horoscope.engine_version,
        scoring_version=horoscope.scoring_version,
    )


def monthly_to_schema(forecast: MonthlyForecast) -> MonthlyForecastResponse:
    return MonthlyForecastResponse(
        year=forecast.year,
        month=forecast.month,
        start_at=forecast.start_at,
        end_at=forecast.end_at,
        timezone=forecast.timezone,
        overall=forecast.overall,
        areas=[area_to_schema(area) for area in forecast.areas],
        general_theme=forecast.general_theme,
        key_periods=[cluster_to_schema(item) for item in forecast.key_periods],
        important_dates=[date_to_schema(item) for item in forecast.important_dates],
        opportunities=forecast.opportunities,
        challenges=forecast.challenges,
        major_transits=[transit_to_schema(item) for item in forecast.major_transits],
        moon_events=[event_to_schema(item) for item in forecast.moon_events],
        retrogrades=[event_to_schema(item) for item in forecast.retrogrades],
        house_activations=[
            activation_to_schema(item) for item in forecast.house_activations
        ],
        personal_events=[
            personal_event_to_schema(item) for item in forecast.personal_events
        ],
        source_factors=[factor_to_schema(item) for item in forecast.source_factors],
        engine_version=forecast.engine_version,
        scoring_version=forecast.scoring_version,
    )


def solar_return_to_schema(
    summary: SolarReturnSummary | None,
) -> SolarReturnResponse | None:
    if summary is None:
        return None
    return SolarReturnResponse(
        year=summary.year,
        exact_at=summary.exact_at,
        ascendant=summary.ascendant,
        ascendant_sign=summary.ascendant_sign,
        sun_house=summary.sun_house,
    )


def annual_to_schema(forecast: AnnualForecast) -> AnnualForecastResponse:
    return AnnualForecastResponse(
        year=forecast.year,
        start_at=forecast.start_at,
        end_at=forecast.end_at,
        timezone=forecast.timezone,
        overall=forecast.overall,
        areas=[area_to_schema(area) for area in forecast.areas],
        major_transits=[transit_to_schema(item) for item in forecast.major_transits],
        retrograde_periods=[
            event_to_schema(item) for item in forecast.retrograde_periods
        ],
        eclipses=[event_to_schema(item) for item in forecast.eclipses],
        jupiter_movements=[
            ingress_to_schema(item) for item in forecast.jupiter_movements
        ],
        saturn_movements=[
            ingress_to_schema(item) for item in forecast.saturn_movements
        ],
        outer_planet_hits=[
            transit_to_schema(item) for item in forecast.outer_planet_hits
        ],
        house_activations=[
            activation_to_schema(item) for item in forecast.house_activations
        ],
        key_periods=[cluster_to_schema(item) for item in forecast.key_periods],
        important_dates=[date_to_schema(item) for item in forecast.important_dates],
        solar_return=solar_return_to_schema(forecast.solar_return),
        source_factors=[factor_to_schema(item) for item in forecast.source_factors],
        engine_version=forecast.engine_version,
        scoring_version=forecast.scoring_version,
    )
