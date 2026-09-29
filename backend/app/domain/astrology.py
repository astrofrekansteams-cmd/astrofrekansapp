"""Pure domain types for the astrology engine.

No SQLAlchemy, no FastAPI, no provider SDK: these are the values the engine
produces and the schemas serialise. Keeping them plain makes the engine
testable against known astronomical dates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.domain.enums import (
    SIGN_RULERS,
    AspectType,
    ChartAngle,
    ChartKind,
    Element,
    HouseSystem,
    Modality,
    MoonPhaseName,
    Planet,
    ZodiacSign,
)


def normalize_degrees(value: float) -> float:
    result = value % 360.0
    return result + 360.0 if result < 0 else result


def signed_separation(a: float, b: float) -> float:
    """Shortest signed angle from ``b`` to ``a`` in (-180, 180]."""
    diff = (a - b) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def separation(a: float, b: float) -> float:
    return abs(signed_separation(a, b))


@dataclass(slots=True, frozen=True)
class ChartSubject:
    """What a chart is cast *for*: an instant, a place, a house system.

    Every chart the product needs is this plus a kind. A natal chart uses the
    birth moment, a horary chart the moment the question was asked, a solar
    return the moment the Sun returns to its natal degree. The engine only
    ever sees this type, which is why horary and the return charts need no new
    calculation path.
    """

    kind: ChartKind
    moment_utc: datetime
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    house_system: HouseSystem = HouseSystem.PLACIDUS

    # Free text for the UI: birth place, where the question was asked, etc.
    location_name: str | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if self.moment_utc.tzinfo is None:
            raise ValueError("ChartSubject.moment_utc must be timezone aware.")

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def can_compute_houses(self) -> bool:
        """Houses need a place; the instant is always known for a subject."""
        return self.has_location

    @property
    def local_datetime(self) -> datetime:
        zone = ZoneInfo(self.timezone) if self.timezone else UTC
        return self.moment_utc.astimezone(zone)


@dataclass(slots=True, frozen=True)
class BirthData:
    """Birth input in *local* terms plus the zone needed to resolve it.

    ``birth_time`` may be unknown; the engine then falls back to noon and marks
    the chart as ``time_known=False`` (houses and angles are omitted, because
    they would be meaningless).
    """

    birth_date: date
    birth_time: time | None
    timezone: str | None
    latitude: float | None
    longitude: float | None
    place: str | None = None
    house_system: HouseSystem = HouseSystem.PLACIDUS

    @property
    def time_known(self) -> bool:
        return self.birth_time is not None

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def can_compute_houses(self) -> bool:
        return self.time_known and self.has_location and self.timezone is not None

    @property
    def local_datetime(self) -> datetime:
        """Timezone-aware local birth datetime (noon fallback when unknown)."""
        zone = ZoneInfo(self.timezone) if self.timezone else UTC
        moment = self.birth_time or time(12, 0)
        return datetime.combine(self.birth_date, moment, tzinfo=zone)

    @property
    def utc_datetime(self) -> datetime:
        """The same instant in UTC - what the ephemeris is queried with."""
        return self.local_datetime.astimezone(UTC)

    @property
    def utc_offset_hours(self) -> float:
        offset = self.local_datetime.utcoffset()
        return 0.0 if offset is None else offset.total_seconds() / 3600.0

    def to_subject(self, kind: ChartKind = ChartKind.NATAL) -> ChartSubject:
        """Birth data is one kind of chart subject."""
        return ChartSubject(
            kind=kind,
            moment_utc=self.utc_datetime,
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
            house_system=self.house_system,
            location_name=self.place,
        )


@dataclass(slots=True, frozen=True)
class PlanetPosition:
    planet: Planet
    longitude: float
    latitude: float
    speed_longitude: float
    house: int | None = None

    @property
    def sign(self) -> ZodiacSign:
        return ZodiacSign.from_longitude(self.longitude)

    @property
    def degree_in_sign(self) -> float:
        return self.longitude % 30.0

    @property
    def degree(self) -> int:
        return int(self.degree_in_sign)

    @property
    def minute(self) -> int:
        return int(round((self.degree_in_sign - self.degree) * 60)) % 60

    @property
    def retrograde(self) -> bool:
        return self.speed_longitude < 0


@dataclass(slots=True, frozen=True)
class HousePosition:
    number: int
    cusp_longitude: float

    @property
    def sign(self) -> ZodiacSign:
        return ZodiacSign.from_longitude(self.cusp_longitude)

    @property
    def degree_in_sign(self) -> float:
        return self.cusp_longitude % 30.0

    @property
    def degree(self) -> int:
        return int(self.degree_in_sign)

    @property
    def minute(self) -> int:
        return int(round((self.degree_in_sign - self.degree) * 60)) % 60


@dataclass(slots=True, frozen=True)
class ChartAngles:
    ascendant: float
    midheaven: float

    @property
    def descendant(self) -> float:
        return normalize_degrees(self.ascendant + 180.0)

    @property
    def imum_coeli(self) -> float:
        return normalize_degrees(self.midheaven + 180.0)

    def as_dict(self) -> dict[ChartAngle, float]:
        return {
            ChartAngle.ASC: self.ascendant,
            ChartAngle.DSC: self.descendant,
            ChartAngle.MC: self.midheaven,
            ChartAngle.IC: self.imum_coeli,
        }


@dataclass(slots=True, frozen=True)
class AspectHit:
    first: Planet
    second: Planet
    aspect: AspectType
    orb: float
    applying: bool
    exact_angle: float

    @property
    def nature(self):  # noqa: ANN201 - returns AspectNature
        return self.aspect.nature


@dataclass(slots=True, frozen=True)
class Chart:
    """A computed chart of any kind.

    ``birth_data`` is only set for natal charts; every chart carries a
    ``subject`` (instant + place + house system), which is what a horary,
    return or event chart is built from.
    """

    subject: ChartSubject
    computed_at: datetime
    engine: str
    engine_version: str
    positions: list[PlanetPosition]
    houses: list[HousePosition] = field(default_factory=list)
    angles: ChartAngles | None = None
    aspects: list[AspectHit] = field(default_factory=list)
    house_system: HouseSystem = HouseSystem.PLACIDUS
    birth_data: BirthData | None = None

    @property
    def kind(self) -> ChartKind:
        return self.subject.kind

    @property
    def moment_utc(self) -> datetime:
        return self.subject.moment_utc

    @property
    def house_rulers(self) -> dict[int, Planet]:
        """Traditional ruler of each house cusp.

        Horary works almost entirely through these (querent = ruler of house
        1, quesited = ruler of the house of the matter asked about), and they
        are handy for natal analysis too. Empty when the chart has no houses.
        """
        return {
            house.number: SIGN_RULERS[house.sign] for house in self.houses
        }

    def ruler_of(self, house_number: int) -> Planet | None:
        return self.house_rulers.get(house_number)

    def house_rulers_traditional(self) -> dict[int, Planet]:
        """Traditional rulers of each cusp.

        Identical to :attr:`house_rulers` today, but named explicitly because
        horary must never fall back on modern rulerships: the classical scheme
        has no ruler for Uranus, Neptune or Pluto, and inventing one would
        change the judgement.
        """
        return self.house_rulers

    def house(self, number: int) -> HousePosition | None:
        for item in self.houses:
            if item.number == number:
                return item
        return None

    def position(self, planet: Planet) -> PlanetPosition | None:
        for item in self.positions:
            if item.planet == planet:
                return item
        return None

    @property
    def sun(self) -> PlanetPosition | None:
        return self.position(Planet.SUN)

    @property
    def moon(self) -> PlanetPosition | None:
        return self.position(Planet.MOON)

    @property
    def element_distribution(self) -> dict[Element, int]:
        counts = {element: 0 for element in Element}
        for item in self.positions:
            if item.planet.is_point:
                continue
            counts[item.sign.element] += 1
        return counts

    @property
    def modality_distribution(self) -> dict[Modality, int]:
        counts = {modality: 0 for modality in Modality}
        for item in self.positions:
            if item.planet.is_point:
                continue
            counts[item.sign.modality] += 1
        return counts

    @property
    def dominant_element(self) -> Element:
        return max(self.element_distribution.items(), key=lambda pair: pair[1])[0]

    @property
    def dominant_modality(self) -> Modality:
        return max(self.modality_distribution.items(), key=lambda pair: pair[1])[0]

    @property
    def dominant_planet(self) -> Planet:
        """Weighted score, documented in docs/astrology_engine.md.

        Luminaries and angular placements carry more weight than a raw aspect
        count, and the rulers of the Sun / Moon / Ascendant signs get a bonus.
        """
        scores: dict[Planet, float] = {
            item.planet: 0.0 for item in self.positions if not item.planet.is_point
        }
        for item in self.positions:
            if item.planet.is_point:
                continue
            if item.planet.is_luminary:
                scores[item.planet] += 3.0
            if item.house in (1, 4, 7, 10):
                scores[item.planet] += 2.0
        for hit in self.aspects:
            weight = 1.5 if hit.aspect == AspectType.CONJUNCTION else 1.0
            for planet in (hit.first, hit.second):
                if planet in scores:
                    scores[planet] += weight * (1.0 - min(hit.orb, 8.0) / 10.0)
        for sign in self.big_three_signs:
            if sign is None:
                continue
            ruler = SIGN_RULERS[sign]
            if ruler in scores:
                scores[ruler] += 2.0
        return max(scores.items(), key=lambda pair: pair[1])[0]

    @property
    def ascendant_sign(self) -> ZodiacSign | None:
        return (
            ZodiacSign.from_longitude(self.angles.ascendant) if self.angles else None
        )

    @property
    def big_three_signs(self) -> list[ZodiacSign | None]:
        return [
            self.sun.sign if self.sun else None,
            self.moon.sign if self.moon else None,
            self.ascendant_sign,
        ]


@dataclass(slots=True, frozen=True)
class MoonPhase:
    moment: datetime
    phase: MoonPhaseName
    illumination: float
    age_days: float
    elongation: float
    sign: ZodiacSign
    next_phase: MoonPhaseName | None = None
    next_phase_at: datetime | None = None


# The product started with natal charts only; the name is kept so existing
# imports and the API schema stay stable.
NatalChart = Chart
