"""Contracts for the personal guides: moon guide, returns, numerology, stones."""

from __future__ import annotations

from datetime import date, datetime

from app.domain.enums import AspectNature, Element, MoonPhaseName, Planet, ZodiacSign
from app.schemas.astrology import NatalChartResponse, chart_to_schema
from app.schemas.common import APIModel
from app.services.guides import numerology as numerology_service
from app.services.guides.moon_guide import MoonAspect, MoonGuide
from app.services.guides.returns_guide import ReturnReading
from app.services.guides.stones import Intent, StoneMode, StoneRecommendation


class MoonAspectResponse(APIModel):
    body: Planet
    aspect: str
    orb: float
    applying: bool
    nature: AspectNature
    to_natal: bool


class MoonGuideResponse(APIModel):
    moment: datetime
    sign: ZodiacSign
    degree: float
    phase: MoonPhaseName
    illumination: float
    age_days: float
    next_phase: MoonPhaseName | None
    next_phase_at: datetime | None
    next_sign: ZodiacSign
    next_sign_at: datetime | None
    natal_house: int | None
    sky_aspects: list[MoonAspectResponse]
    natal_aspects: list[MoonAspectResponse]
    good_for: list[str]
    careful_with: list[str]
    summary: str
    version: str


def _aspect(item: MoonAspect) -> MoonAspectResponse:
    return MoonAspectResponse(
        body=item.body,
        aspect=item.aspect,
        orb=item.orb,
        applying=item.applying,
        nature=item.nature,
        to_natal=item.to_natal,
    )


def moon_guide_to_schema(guide: MoonGuide) -> MoonGuideResponse:
    return MoonGuideResponse(
        moment=guide.moment,
        sign=guide.sign,
        degree=guide.degree,
        phase=guide.phase,
        illumination=guide.illumination,
        age_days=guide.age_days,
        next_phase=guide.next_phase,
        next_phase_at=guide.next_phase_at,
        next_sign=guide.next_sign,
        next_sign_at=guide.next_sign_at,
        natal_house=guide.natal_house,
        sky_aspects=[_aspect(a) for a in guide.sky_aspects],
        natal_aspects=[_aspect(a) for a in guide.natal_aspects],
        good_for=guide.good_for,
        careful_with=guide.careful_with,
        summary=guide.summary,
        version=guide.version,
    )


class ReturnThemeResponse(APIModel):
    headline: str
    lines: list[str]
    focus_houses: list[int]
    angular_planets: list[Planet]
    ascendant_in_natal_house: int | None


class ReturnChartResponse(APIModel):
    kind: str
    moment: datetime
    chart: NatalChartResponse
    theme: ReturnThemeResponse
    version: str


def return_to_schema(reading: ReturnReading) -> ReturnChartResponse:
    theme = reading.theme
    return ReturnChartResponse(
        kind=reading.kind,
        moment=reading.moment,
        chart=chart_to_schema(reading.chart),
        theme=ReturnThemeResponse(
            headline=theme.headline,
            lines=theme.lines,
            focus_houses=theme.focus_houses,
            angular_planets=theme.angular_planets,
            ascendant_in_natal_house=theme.ascendant_in_natal_house,
        ),
        version=reading.version,
    )


class NumberMeaningResponse(APIModel):
    number: int
    is_master: bool
    title: str
    keywords: str
    meaning: str


class NumerologyResponse(APIModel):
    name_used: str
    birth_date: date
    reference: date
    life_path: NumberMeaningResponse
    destiny: NumberMeaningResponse
    soul_urge: NumberMeaningResponse
    personality: NumberMeaningResponse
    birthday: NumberMeaningResponse
    personal_year: NumberMeaningResponse
    personal_month: NumberMeaningResponse
    version: str


def _number(value: int, locale: str, *, cycle: bool = False) -> NumberMeaningResponse:
    index = 1 if locale == "en" else 0
    title, keywords, meaning = numerology_service.MEANINGS[value]
    if cycle:
        meaning = numerology_service.CYCLE_MEANINGS[value]
    return NumberMeaningResponse(
        number=value,
        is_master=value in numerology_service.MASTER_NUMBERS,
        title=title[index],
        keywords=keywords[index],
        meaning=meaning[index],
    )


def numerology_to_schema(
    item: numerology_service.NumerologyProfile, locale: str
) -> NumerologyResponse:
    return NumerologyResponse(
        name_used=item.name_used,
        birth_date=item.birth_date,
        reference=item.reference,
        life_path=_number(item.life_path, locale),
        destiny=_number(item.destiny, locale),
        soul_urge=_number(item.soul_urge, locale),
        personality=_number(item.personality, locale),
        birthday=_number(item.birthday, locale),
        personal_year=_number(item.personal_year, locale, cycle=True),
        personal_month=_number(item.personal_month, locale, cycle=True),
        version=item.version,
    )


class StoneReasonResponse(APIModel):
    kind: str
    weight: int
    text: str


class StoneResponse(APIModel):
    key: str
    name: str
    color: str
    elements: list[Element]
    planets: list[Planet]
    signs: list[ZodiacSign]
    intents: list[Intent]
    note: str


class StoneSuggestionResponse(APIModel):
    stone: StoneResponse
    score: int
    reasons: list[StoneReasonResponse]


class StoneRecommendationResponse(APIModel):
    mode: StoneMode
    intent: Intent | None
    moment: datetime
    element_balance: dict[Element, int]
    weakest_elements: list[Element]
    suggestions: list[StoneSuggestionResponse]
    disclaimer: str
    version: str


def stones_to_schema(item: StoneRecommendation, locale: str) -> StoneRecommendationResponse:
    index = 1 if locale == "en" else 0
    return StoneRecommendationResponse(
        mode=item.mode,
        intent=item.intent,
        moment=item.moment,
        element_balance=item.element_balance,
        weakest_elements=item.weakest_elements,
        suggestions=[
            StoneSuggestionResponse(
                stone=StoneResponse(
                    key=s.stone.key,
                    name=s.stone.name[index],
                    color=s.stone.color,
                    elements=list(s.stone.elements),
                    planets=list(s.stone.planets),
                    signs=list(s.stone.signs),
                    intents=list(s.stone.intents),
                    note=s.stone.note[index],
                ),
                score=s.score,
                reasons=[
                    StoneReasonResponse(kind=r.kind, weight=r.weight, text=r.text)
                    for r in s.reasons
                ],
            )
            for s in item.suggestions
        ],
        disclaimer=item.disclaimer,
        version=item.version,
    )
