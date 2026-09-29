"""Moon guide: where the Moon is, what it touches, and what that suits.

All positions come from the ephemeris. The guidance lines are picked from
``content`` by phase, element, natal house and aspect nature, so the same
sky and chart always give the same guide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.astrology import Chart, MoonPhase, PlanetPosition
from app.domain.enums import AspectNature, MoonPhaseName, Planet, ZodiacSign
from app.services.astrology.aspects import TRANSIT_ORBS, OrbPolicy, classify_pair
from app.services.astrology.houses import house_of
from app.services.astrology.skyfield_engine import SkyfieldEngine, get_engine
from app.services.guides import content
from app.services.guides.content import pick

# Moon-to-sky aspects: the Moon moves ~13 deg/day, so a 4 deg window is
# roughly the half day it is felt.
SKY_ORBS = OrbPolicy(
    base=dict(TRANSIT_ORBS.base),
    luminary_bonus=1.0,
    node_penalty=-1.0,
)

GUIDE_VERSION = "moon_guide_v1"


@dataclass(slots=True, frozen=True)
class MoonAspect:
    body: Planet
    aspect: str
    orb: float
    applying: bool
    nature: AspectNature
    to_natal: bool


@dataclass(slots=True)
class MoonGuide:
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
    sky_aspects: list[MoonAspect] = field(default_factory=list)
    natal_aspects: list[MoonAspect] = field(default_factory=list)
    good_for: list[str] = field(default_factory=list)
    careful_with: list[str] = field(default_factory=list)
    summary: str = ""
    version: str = GUIDE_VERSION


class MoonGuideService:
    def __init__(self, engine: SkyfieldEngine | None = None) -> None:
        self._engine = engine or get_engine()

    def guide(
        self,
        moment: datetime,
        natal: Chart | None,
        *,
        locale: str = "tr",
        phase: MoonPhase | None = None,
    ) -> MoonGuide:
        """``phase`` may be passed in from the cached chart service; the
        next-phase search inside ``moon_phase`` is the expensive part."""
        moment = moment.astimezone(UTC)
        sky = self._engine.positions(moment)
        moon = next(p for p in sky if p.planet == Planet.MOON)
        phase = phase or self._engine.moon_phase(moment)
        sign = ZodiacSign.from_longitude(moon.longitude)
        next_sign = ZodiacSign.from_longitude((sign.index + 1) * 30.0 % 360.0)

        sky_aspects = self._aspects(moon, [p for p in sky if p.planet != Planet.MOON], SKY_ORBS, False)
        natal_aspects: list[MoonAspect] = []
        natal_house = None
        if natal is not None:
            natal_aspects = self._aspects(moon, natal.positions, TRANSIT_ORBS, True)
            natal_house = house_of(moon.longitude, natal.houses)

        good, careful = self._guidance(phase.phase, sign, natal_house, natal_aspects, locale)
        return MoonGuide(
            moment=moment,
            sign=sign,
            degree=round(moon.longitude % 30.0, 2),
            phase=phase.phase,
            illumination=round(phase.illumination, 4),
            age_days=round(phase.age_days, 2),
            next_phase=phase.next_phase,
            next_phase_at=phase.next_phase_at,
            next_sign=next_sign,
            next_sign_at=self._next_ingress(moment, moon),
            natal_house=natal_house,
            sky_aspects=sky_aspects,
            natal_aspects=natal_aspects,
            good_for=good,
            careful_with=careful,
            summary=self._summary(phase.phase, sign, natal_house, locale),
        )

    # ------------------------------------------------------------ internals

    def _aspects(
        self,
        moon: PlanetPosition,
        others: list[PlanetPosition],
        policy: OrbPolicy,
        to_natal: bool,
    ) -> list[MoonAspect]:
        hits: list[MoonAspect] = []
        for other in others:
            if other.planet == Planet.SOUTH_NODE:
                continue
            hit = classify_pair(
                first_longitude=moon.longitude,
                second_longitude=other.longitude,
                first=Planet.MOON,
                second=other.planet,
                first_speed=moon.speed_longitude,
                # Natal positions are fixed points in time.
                second_speed=0.0 if to_natal else other.speed_longitude,
                policy=policy,
            )
            if hit is not None:
                hits.append(
                    MoonAspect(
                        body=other.planet,
                        aspect=hit.aspect.value,
                        orb=round(hit.orb, 2),
                        applying=hit.applying,
                        nature=hit.aspect.nature,
                        to_natal=to_natal,
                    )
                )
        hits.sort(key=lambda item: item.orb)
        return hits

    def _next_ingress(self, moment: datetime, moon: PlanetPosition) -> datetime | None:
        """Instant the Moon enters the next sign.

        Newton iteration on the remaining arc, seeded by the current speed:
        the Moon never turns retrograde, so it converges in a few steps to
        well under a minute.
        """
        boundary = (int(moon.longitude // 30.0) + 1) * 30.0
        when = moment
        longitude, speed = moon.longitude, moon.speed_longitude
        for _ in range(6):
            remaining = (boundary - longitude) % 360.0
            if remaining > 180.0:  # overshot the boundary slightly
                remaining -= 360.0
            if abs(remaining) < 1e-4 or speed <= 0:
                break
            when = when + timedelta(days=remaining / speed)
            position = self._engine.positions(when, bodies=(Planet.MOON,))[0]
            longitude, speed = position.longitude, position.speed_longitude
        if when - moment > timedelta(days=3):
            return None
        return when.replace(microsecond=0)

    def _guidance(
        self,
        phase: MoonPhaseName,
        sign: ZodiacSign,
        house: int | None,
        natal_aspects: list[MoonAspect],
        locale: str,
    ) -> tuple[list[str], list[str]]:
        good_texts, careful_texts = content.PHASE_GUIDANCE[phase]
        good = [pick(text, locale) for text in good_texts]
        careful = [pick(text, locale) for text in careful_texts]
        good.append(pick(content.ELEMENT_GUIDANCE[sign.element], locale))
        if house is not None:
            topic = pick(content.HOUSE_TOPICS[house], locale)
            good.append(
                pick(
                    (
                        f"Ay natal {house}. evinden geçiyor: {topic} gündemde.",
                        f"The Moon crosses your natal {house}th house: {topic} are in focus.",
                    ),
                    locale,
                )
            )
        for aspect in natal_aspects[:3]:
            text, favourable = content.aspect_guidance(aspect.body, aspect.nature, locale)
            (good if favourable else careful).append(text)
        return good, careful

    def _summary(
        self, phase: MoonPhaseName, sign: ZodiacSign, house: int | None, locale: str
    ) -> str:
        phase_name = pick(content.PHASE_NAMES[phase], locale)
        sign_name = pick(content.SIGN_NAMES[sign], locale)
        mood = pick(content.SIGN_MOODS[sign], locale)
        if house is None:
            return pick(
                (
                    f"{phase_name}, Ay {sign_name} burcunda: günün tonu {mood}.",
                    f"{phase_name}, Moon in {sign_name}: the day feels {mood}.",
                ),
                locale,
            )
        topic = pick(content.HOUSE_TOPICS[house], locale)
        return pick(
            (
                f"{phase_name}, Ay {sign_name} burcunda ve {house}. evinde: {topic} {mood} bir tonla öne çıkıyor.",
                f"{phase_name}, Moon in {sign_name} in your {house}th house: {topic} come forward in a {mood} tone.",
            ),
            locale,
        )


_service: MoonGuideService | None = None


def get_moon_guide_service() -> MoonGuideService:
    global _service
    if _service is None:
        _service = MoonGuideService()
    return _service
