"""Essential and accidental dignity.

``dignity_rules_v1``. The tables below are the standard Hellenistic /
medieval ones as given in:

* **Rulership, exaltation, detriment, fall** - the classical scheme used by
  Ptolemy (*Tetrabiblos* I.17-19) and every traditional text since.
* **Triplicity** - the Dorothean (Dorotheus of Sidon) scheme, day / night /
  participating ruler, as used by William Lilly, *Christian Astrology* (1647).
* **Terms (bounds)** - the Egyptian terms, Lilly's table.
* **Faces (decans)** - the Chaldean order, Lilly's table.

Outer planets appear in a horary chart but are never significators here: the
classical scheme has no rulership for them, and inventing one would change the
judgement. That is a deliberate restriction, not an omission.

Accidental dignity conventions (each documented in
``docs/horary_engine.md``):

* **angular / succedent / cadent** - houses 1,4,7,10 / 2,5,8,11 / 3,6,9,12.
* **combust** - within 8°30' of the Sun (Lilly).
* **under the beams** - within 17° of the Sun and not combust (Lilly).
* **cazimi** - within 17' of the Sun, which is a *strengthening* condition.
* **retrograde / direct / stationary** - from the computed longitude speed.
* **fast / slow** - speed compared with the body's mean daily motion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.astrology import Chart, PlanetPosition, separation
from app.domain.enums import Planet, ZodiacSign
from app.services.astrology.sampling import MEAN_DAILY_MOTION

DIGNITY_RULES_VERSION = "dignity_rules_v1"

# The seven classical planets. Significators are chosen only from these.
CLASSICAL_PLANETS: tuple[Planet, ...] = (
    Planet.SUN,
    Planet.MOON,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
)

MODERN_PLANETS: tuple[Planet, ...] = (
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
)

# --- rulership ------------------------------------------------------------

TRADITIONAL_RULERS: dict[ZodiacSign, Planet] = {
    ZodiacSign.ARIES: Planet.MARS,
    ZodiacSign.TAURUS: Planet.VENUS,
    ZodiacSign.GEMINI: Planet.MERCURY,
    ZodiacSign.CANCER: Planet.MOON,
    ZodiacSign.LEO: Planet.SUN,
    ZodiacSign.VIRGO: Planet.MERCURY,
    ZodiacSign.LIBRA: Planet.VENUS,
    ZodiacSign.SCORPIO: Planet.MARS,
    ZodiacSign.SAGITTARIUS: Planet.JUPITER,
    ZodiacSign.CAPRICORN: Planet.SATURN,
    ZodiacSign.AQUARIUS: Planet.SATURN,
    ZodiacSign.PISCES: Planet.JUPITER,
}

# Detriment is the opposite sign of a planet's domicile.
DETRIMENTS: dict[ZodiacSign, tuple[Planet, ...]] = {
    sign: tuple(
        planet
        for other, planet in TRADITIONAL_RULERS.items()
        if ZodiacSign(list(ZodiacSign)[(other.index + 6) % 12]) is sign
    )
    for sign in ZodiacSign
}

# Exaltation sign and degree (Ptolemy / Lilly).
EXALTATIONS: dict[Planet, tuple[ZodiacSign, int]] = {
    Planet.SUN: (ZodiacSign.ARIES, 19),
    Planet.MOON: (ZodiacSign.TAURUS, 3),
    Planet.MERCURY: (ZodiacSign.VIRGO, 15),
    Planet.VENUS: (ZodiacSign.PISCES, 27),
    Planet.MARS: (ZodiacSign.CAPRICORN, 28),
    Planet.JUPITER: (ZodiacSign.CANCER, 15),
    Planet.SATURN: (ZodiacSign.LIBRA, 21),
    Planet.NORTH_NODE: (ZodiacSign.GEMINI, 3),
}

FALLS: dict[Planet, ZodiacSign] = {
    planet: ZodiacSign(list(ZodiacSign)[(sign.index + 6) % 12])
    for planet, (sign, _) in EXALTATIONS.items()
}

# --- triplicity (Dorothean: day ruler, night ruler, participating) --------

TRIPLICITIES: dict[str, tuple[Planet, Planet, Planet]] = {
    "fire": (Planet.SUN, Planet.JUPITER, Planet.SATURN),
    "earth": (Planet.VENUS, Planet.MOON, Planet.MARS),
    "air": (Planet.SATURN, Planet.MERCURY, Planet.JUPITER),
    "water": (Planet.VENUS, Planet.MARS, Planet.MOON),
}

# --- Egyptian terms (Lilly's table): (upper bound degree, ruler) ----------

EGYPTIAN_TERMS: dict[ZodiacSign, tuple[tuple[int, Planet], ...]] = {
    ZodiacSign.ARIES: (
        (6, Planet.JUPITER),
        (12, Planet.VENUS),
        (20, Planet.MERCURY),
        (25, Planet.MARS),
        (30, Planet.SATURN),
    ),
    ZodiacSign.TAURUS: (
        (8, Planet.VENUS),
        (14, Planet.MERCURY),
        (22, Planet.JUPITER),
        (27, Planet.SATURN),
        (30, Planet.MARS),
    ),
    ZodiacSign.GEMINI: (
        (6, Planet.MERCURY),
        (12, Planet.JUPITER),
        (17, Planet.VENUS),
        (24, Planet.MARS),
        (30, Planet.SATURN),
    ),
    ZodiacSign.CANCER: (
        (7, Planet.MARS),
        (13, Planet.VENUS),
        (19, Planet.MERCURY),
        (26, Planet.JUPITER),
        (30, Planet.SATURN),
    ),
    ZodiacSign.LEO: (
        (6, Planet.JUPITER),
        (11, Planet.VENUS),
        (18, Planet.SATURN),
        (24, Planet.MERCURY),
        (30, Planet.MARS),
    ),
    ZodiacSign.VIRGO: (
        (7, Planet.MERCURY),
        (17, Planet.VENUS),
        (21, Planet.JUPITER),
        (28, Planet.MARS),
        (30, Planet.SATURN),
    ),
    ZodiacSign.LIBRA: (
        (6, Planet.SATURN),
        (14, Planet.MERCURY),
        (21, Planet.JUPITER),
        (28, Planet.VENUS),
        (30, Planet.MARS),
    ),
    ZodiacSign.SCORPIO: (
        (7, Planet.MARS),
        (11, Planet.VENUS),
        (19, Planet.MERCURY),
        (24, Planet.JUPITER),
        (30, Planet.SATURN),
    ),
    ZodiacSign.SAGITTARIUS: (
        (12, Planet.JUPITER),
        (17, Planet.VENUS),
        (21, Planet.MERCURY),
        (26, Planet.SATURN),
        (30, Planet.MARS),
    ),
    ZodiacSign.CAPRICORN: (
        (7, Planet.MERCURY),
        (14, Planet.JUPITER),
        (22, Planet.VENUS),
        (26, Planet.SATURN),
        (30, Planet.MARS),
    ),
    ZodiacSign.AQUARIUS: (
        (7, Planet.MERCURY),
        (13, Planet.VENUS),
        (20, Planet.JUPITER),
        (25, Planet.MARS),
        (30, Planet.SATURN),
    ),
    ZodiacSign.PISCES: (
        (12, Planet.VENUS),
        (16, Planet.JUPITER),
        (19, Planet.MERCURY),
        (28, Planet.MARS),
        (30, Planet.SATURN),
    ),
}

# --- faces / decans (Chaldean order) --------------------------------------

CHALDEAN_ORDER: tuple[Planet, ...] = (
    Planet.MARS,
    Planet.SUN,
    Planet.VENUS,
    Planet.MERCURY,
    Planet.MOON,
    Planet.SATURN,
    Planet.JUPITER,
)

# Lilly's table starts Aries 0-10 with Mars, and then runs the Chaldean order
# continuously through the zodiac.
FACES: dict[ZodiacSign, tuple[Planet, Planet, Planet]] = {
    sign: tuple(
        CHALDEAN_ORDER[(sign.index * 3 + decan) % 7] for decan in range(3)
    )
    for sign in ZodiacSign
}

# --- accidental dignity thresholds (Lilly) --------------------------------

CAZIMI_DEGREES = 17 / 60
COMBUST_DEGREES = 8.5
UNDER_BEAMS_DEGREES = 17.0
STATIONARY_SPEED_FRACTION = 0.05

ANGULAR_HOUSES = (1, 4, 7, 10)
SUCCEDENT_HOUSES = (2, 5, 8, 11)
CADENT_HOUSES = (3, 6, 9, 12)


class DignityKind(StrEnum):
    DOMICILE = "domicile"
    EXALTATION = "exaltation"
    TRIPLICITY = "triplicity"
    TERM = "term"
    FACE = "face"
    DETRIMENT = "detriment"
    FALL = "fall"
    PEREGRINE = "peregrine"


class HousePlacement(StrEnum):
    ANGULAR = "angular"
    SUCCEDENT = "succedent"
    CADENT = "cadent"


class SolarCondition(StrEnum):
    CAZIMI = "cazimi"
    COMBUST = "combust"
    UNDER_BEAMS = "under_beams"
    FREE = "free"


class MotionState(StrEnum):
    DIRECT = "direct"
    RETROGRADE = "retrograde"
    STATIONARY = "stationary"


@dataclass(slots=True, frozen=True)
class EssentialDignity:
    planet: Planet
    sign: ZodiacSign
    degree: float
    dignities: list[DignityKind]
    debilities: list[DignityKind]
    triplicity_ruler: Planet | None
    term_ruler: Planet | None
    face_ruler: Planet | None
    peregrine: bool
    score: int

    @property
    def is_dignified(self) -> bool:
        return bool(self.dignities)


@dataclass(slots=True, frozen=True)
class AccidentalDignity:
    planet: Planet
    house: int | None
    placement: HousePlacement | None
    motion: MotionState
    speed: float
    speed_ratio: float
    solar_condition: SolarCondition
    solar_distance: float
    notes: list[str] = field(default_factory=list)


def sign_element(sign: ZodiacSign) -> str:
    return ["fire", "earth", "air", "water"][sign.index % 4]


def triplicity_ruler(sign: ZodiacSign, *, is_day: bool) -> Planet:
    day_ruler, night_ruler, _ = TRIPLICITIES[sign_element(sign)]
    return day_ruler if is_day else night_ruler


def term_ruler(sign: ZodiacSign, degree: float) -> Planet:
    for bound, ruler in EGYPTIAN_TERMS[sign]:
        if degree < bound:
            return ruler
    return EGYPTIAN_TERMS[sign][-1][1]


def face_ruler(sign: ZodiacSign, degree: float) -> Planet:
    return FACES[sign][min(int(degree // 10), 2)]


# The classical five-fold weighting (Lilly): domicile +5, exaltation +4,
# triplicity +3, term +2, face +1; detriment -5, fall -4, peregrine -5.
DIGNITY_SCORES: dict[DignityKind, int] = {
    DignityKind.DOMICILE: 5,
    DignityKind.EXALTATION: 4,
    DignityKind.TRIPLICITY: 3,
    DignityKind.TERM: 2,
    DignityKind.FACE: 1,
    DignityKind.DETRIMENT: -5,
    DignityKind.FALL: -4,
    DignityKind.PEREGRINE: -5,
}


def essential_dignity(
    planet: Planet, longitude: float, *, is_day: bool
) -> EssentialDignity:
    sign = ZodiacSign.from_longitude(longitude)
    degree = longitude % 30

    dignities: list[DignityKind] = []
    debilities: list[DignityKind] = []

    if TRADITIONAL_RULERS[sign] is planet:
        dignities.append(DignityKind.DOMICILE)

    exaltation = EXALTATIONS.get(planet)
    if exaltation is not None and exaltation[0] is sign:
        dignities.append(DignityKind.EXALTATION)

    triplicity = triplicity_ruler(sign, is_day=is_day)
    if triplicity is planet:
        dignities.append(DignityKind.TRIPLICITY)

    term = term_ruler(sign, degree)
    if term is planet:
        dignities.append(DignityKind.TERM)

    face = face_ruler(sign, degree)
    if face is planet:
        dignities.append(DignityKind.FACE)

    if planet in DETRIMENTS.get(sign, ()):
        debilities.append(DignityKind.DETRIMENT)
    if FALLS.get(planet) is sign:
        debilities.append(DignityKind.FALL)

    # Peregrine: no essential dignity at all in its own place.
    peregrine = not dignities
    if peregrine:
        debilities.append(DignityKind.PEREGRINE)

    score = sum(DIGNITY_SCORES[item] for item in dignities + debilities)

    return EssentialDignity(
        planet=planet,
        sign=sign,
        degree=round(degree, 4),
        dignities=dignities,
        debilities=debilities,
        triplicity_ruler=triplicity,
        term_ruler=term,
        face_ruler=face,
        peregrine=peregrine,
        score=score,
    )


def house_placement(house: int | None) -> HousePlacement | None:
    if house is None:
        return None
    if house in ANGULAR_HOUSES:
        return HousePlacement.ANGULAR
    if house in SUCCEDENT_HOUSES:
        return HousePlacement.SUCCEDENT
    return HousePlacement.CADENT


def solar_condition(
    planet: Planet, longitude: float, sun_longitude: float
) -> tuple[SolarCondition, float]:
    """Cazimi / combust / under the beams, by distance from the Sun."""
    if planet is Planet.SUN:
        return SolarCondition.FREE, 0.0
    distance = separation(longitude, sun_longitude)
    if distance <= CAZIMI_DEGREES:
        return SolarCondition.CAZIMI, distance
    if distance <= COMBUST_DEGREES:
        return SolarCondition.COMBUST, distance
    if distance <= UNDER_BEAMS_DEGREES:
        return SolarCondition.UNDER_BEAMS, distance
    return SolarCondition.FREE, distance


def motion_state(planet: Planet, speed: float) -> MotionState:
    mean = MEAN_DAILY_MOTION.get(planet, 1.0)
    if abs(speed) < abs(mean) * STATIONARY_SPEED_FRACTION:
        return MotionState.STATIONARY
    return MotionState.RETROGRADE if speed < 0 else MotionState.DIRECT


def accidental_dignity(
    position: PlanetPosition, *, sun_longitude: float
) -> AccidentalDignity:
    condition, distance = solar_condition(
        position.planet, position.longitude, sun_longitude
    )
    mean = MEAN_DAILY_MOTION.get(position.planet, 1.0)
    ratio = position.speed_longitude / mean if mean else 0.0

    notes: list[str] = []
    if condition is SolarCondition.CAZIMI:
        notes.append("cazimi_strengthens")
    if condition is SolarCondition.COMBUST:
        notes.append("combust_weakens")
    if ratio > 1.0:
        notes.append("swift_in_motion")
    elif 0 < ratio < 0.7:
        notes.append("slow_in_motion")

    return AccidentalDignity(
        planet=position.planet,
        house=position.house,
        placement=house_placement(position.house),
        motion=motion_state(position.planet, position.speed_longitude),
        speed=round(position.speed_longitude, 5),
        speed_ratio=round(ratio, 4),
        solar_condition=condition,
        solar_distance=round(distance, 4),
        notes=notes,
    )


def is_day_chart(chart: Chart) -> bool:
    """A chart is diurnal when the Sun is above the horizon.

    Houses 7-12 are above the horizon in the usual convention, so the Sun in
    one of them makes the chart diurnal. Without houses the engine falls back
    to the Sun's position relative to the Ascendant degree.
    """
    sun = chart.position(Planet.SUN)
    if sun is None:
        return True
    if sun.house is not None:
        return sun.house >= 7
    if chart.angles is None:
        return True
    return ((sun.longitude - chart.angles.ascendant) % 360) >= 180
