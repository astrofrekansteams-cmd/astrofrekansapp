"""Astrology API contracts.

These mirror the Flutter client's models (``lib/core/astrology/domain``) so the
mobile data layer can be swapped from mock to API without touching the UI:
planets/signs/aspects travel as snake_case enum values, longitudes as degrees,
every instant as UTC ISO-8601.
"""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import Field

from app.domain.astrology import Chart, MoonPhase
from app.domain.enums import (
    AspectNature,
    AspectType,
    ChartKind,
    Element,
    HouseSystem,
    Modality,
    MoonPhaseName,
    Planet,
    ZodiacSign,
)
from app.schemas.common import APIModel


class BirthDataResponse(APIModel):
    birth_date: date
    birth_time: time | None
    time_known: bool
    place: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    utc_datetime: datetime
    utc_offset_hours: float


class PlanetPositionResponse(APIModel):
    planet: Planet
    sign: ZodiacSign
    longitude: float = Field(description="Ecliptic longitude in degrees (0-360).")
    latitude: float
    degree: int = Field(description="Whole degrees inside the sign (0-29).")
    minute: int
    speed_longitude: float = Field(description="Degrees per day; negative = retrograde.")
    retrograde: bool
    house: int | None = None


class HousePositionResponse(APIModel):
    number: int
    sign: ZodiacSign
    cusp_longitude: float
    degree: int
    minute: int


class AnglesResponse(APIModel):
    ascendant: float
    descendant: float
    midheaven: float
    imum_coeli: float
    ascendant_sign: ZodiacSign
    descendant_sign: ZodiacSign
    midheaven_sign: ZodiacSign
    imum_coeli_sign: ZodiacSign


class AspectResponse(APIModel):
    first: Planet
    second: Planet
    aspect: AspectType
    nature: AspectNature
    orb: float
    applying: bool


class ChartSubjectResponse(APIModel):
    """What the chart was cast for - a birth, a question, an event."""

    kind: ChartKind
    moment_utc: datetime
    latitude: float | None
    longitude: float | None
    timezone: str | None
    location_name: str | None = None


class NatalChartResponse(APIModel):
    kind: ChartKind = ChartKind.NATAL
    engine: str
    engine_version: str
    computed_at: datetime
    house_system: HouseSystem
    requested_house_system: HouseSystem
    subject: ChartSubjectResponse

    # Present for natal charts; null for horary, return and event charts.
    birth_data: BirthDataResponse | None
    planets: list[PlanetPositionResponse]
    houses: list[HousePositionResponse]
    angles: AnglesResponse | None
    aspects: list[AspectResponse]
    elements: dict[Element, int]
    modalities: dict[Modality, int]
    dominant_element: Element
    dominant_modality: Modality
    dominant_planet: Planet
    big_three: dict[str, ZodiacSign | None]

    # Traditional ruler of each house cusp; the backbone of horary work.
    house_rulers: dict[int, Planet] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class NatalChartRequest(APIModel):
    birth_date: date
    birth_time: time | None = None
    birth_place: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = None
    house_system: HouseSystem = HouseSystem.PLACIDUS


class MoonPhaseResponse(APIModel):
    moment: datetime
    phase: MoonPhaseName
    illumination: float
    age_days: float
    elongation: float
    sign: ZodiacSign
    next_phase: MoonPhaseName | None
    next_phase_at: datetime | None


class PlanetaryPositionsResponse(APIModel):
    moment: datetime
    positions: list[PlanetPositionResponse]


def planet_to_schema(position) -> PlanetPositionResponse:  # noqa: ANN001
    return PlanetPositionResponse(
        planet=position.planet,
        sign=position.sign,
        longitude=round(position.longitude, 6),
        latitude=round(position.latitude, 6),
        degree=position.degree,
        minute=position.minute,
        speed_longitude=round(position.speed_longitude, 6),
        retrograde=position.retrograde,
        house=position.house,
    )


def chart_to_schema(
    chart: Chart, *, requested_house_system: HouseSystem | None = None
) -> NatalChartResponse:
    birth = chart.birth_data
    warnings: list[str] = []
    requested = (
        requested_house_system
        or (birth.house_system if birth else chart.subject.house_system)
    )

    if birth is not None:
        if not birth.time_known:
            warnings.append(
                "birth_time_unknown: houses and angles are omitted and the Moon "
                "may be off by up to 13 degrees."
            )
        if not birth.has_location:
            warnings.append("birth_location_unknown: houses and angles are omitted.")
    if chart.house_system != requested:
        warnings.append(
            f"house_system_fallback: {requested.value} is undefined at this "
            f"latitude, used {chart.house_system.value} instead."
        )

    angles = None
    if chart.angles is not None:
        angles = AnglesResponse(
            ascendant=round(chart.angles.ascendant, 6),
            descendant=round(chart.angles.descendant, 6),
            midheaven=round(chart.angles.midheaven, 6),
            imum_coeli=round(chart.angles.imum_coeli, 6),
            ascendant_sign=ZodiacSign.from_longitude(chart.angles.ascendant),
            descendant_sign=ZodiacSign.from_longitude(chart.angles.descendant),
            midheaven_sign=ZodiacSign.from_longitude(chart.angles.midheaven),
            imum_coeli_sign=ZodiacSign.from_longitude(chart.angles.imum_coeli),
        )

    big_three = chart.big_three_signs
    return NatalChartResponse(
        kind=chart.kind,
        engine=chart.engine,
        engine_version=chart.engine_version,
        computed_at=chart.computed_at,
        house_system=chart.house_system,
        requested_house_system=requested,
        subject=ChartSubjectResponse(
            kind=chart.subject.kind,
            moment_utc=chart.subject.moment_utc,
            latitude=chart.subject.latitude,
            longitude=chart.subject.longitude,
            timezone=chart.subject.timezone,
            location_name=chart.subject.location_name,
        ),
        birth_data=(
            BirthDataResponse(
                birth_date=birth.birth_date,
                birth_time=birth.birth_time,
                time_known=birth.time_known,
                place=birth.place,
                latitude=birth.latitude,
                longitude=birth.longitude,
                timezone=birth.timezone,
                utc_datetime=birth.utc_datetime,
                utc_offset_hours=birth.utc_offset_hours,
            )
            if birth is not None
            else None
        ),
        planets=[planet_to_schema(position) for position in chart.positions],
        houses=[
            HousePositionResponse(
                number=house.number,
                sign=house.sign,
                cusp_longitude=round(house.cusp_longitude, 6),
                degree=house.degree,
                minute=house.minute,
            )
            for house in chart.houses
        ],
        angles=angles,
        aspects=[
            AspectResponse(
                first=hit.first,
                second=hit.second,
                aspect=hit.aspect,
                nature=hit.aspect.nature,
                orb=round(hit.orb, 4),
                applying=hit.applying,
            )
            for hit in chart.aspects
        ],
        elements=chart.element_distribution,
        modalities=chart.modality_distribution,
        dominant_element=chart.dominant_element,
        dominant_modality=chart.dominant_modality,
        dominant_planet=chart.dominant_planet,
        big_three={
            "sun": big_three[0],
            "moon": big_three[1],
            "ascendant": big_three[2],
        },
        house_rulers=chart.house_rulers,
        warnings=warnings,
    )


def moon_phase_to_schema(phase: MoonPhase) -> MoonPhaseResponse:
    return MoonPhaseResponse(
        moment=phase.moment,
        phase=phase.phase,
        illumination=phase.illumination,
        age_days=phase.age_days,
        elongation=phase.elongation,
        sign=phase.sign,
        next_phase=phase.next_phase,
        next_phase_at=phase.next_phase_at,
    )
