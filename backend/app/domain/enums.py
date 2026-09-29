"""Domain enums shared by the ORM, the schemas and the astrology engine.

They are plain ``str`` enums so they serialise cleanly into JSON and into the
database without extra mapping.
"""

from __future__ import annotations

from enum import StrEnum


class AuthProvider(StrEnum):
    PASSWORD = "password"
    GOOGLE = "google"
    APPLE = "apple"


class SubscriptionTier(StrEnum):
    """Plans in ascending order. Each includes everything below it."""

    FREE = "free"
    PREMIUM = "premium"
    COSMIC_PLUS = "cosmic_plus"

    @property
    def rank(self) -> int:
        return _TIER_RANK[self]

    def includes(self, other: "SubscriptionTier") -> bool:
        """Whether this plan has everything `other` has."""
        return self.rank >= other.rank

    @property
    def is_paid(self) -> bool:
        return self is not SubscriptionTier.FREE


_TIER_RANK = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.PREMIUM: 1,
    SubscriptionTier.COSMIC_PLUS: 2,
}


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    GRACE = "grace"
    PENDING = "pending"


class SavedPersonRelation(StrEnum):
    PARTNER = "partner"
    SPOUSE = "spouse"
    FRIEND = "friend"
    FAMILY = "family"
    OTHER = "other"


class HouseSystem(StrEnum):
    PLACIDUS = "placidus"
    KOCH = "koch"
    WHOLE_SIGN = "whole_sign"
    EQUAL = "equal"


class ChartKind(StrEnum):
    """What a chart is cast for.

    Only the moment, the place and the house system differ between these -
    the same engine primitive produces all of them. Horary in particular is
    cast for the instant the *question* was asked, never for a birth date.
    """

    NATAL = "natal"
    HORARY = "horary"
    SOLAR_RETURN = "solar_return"
    LUNAR_RETURN = "lunar_return"
    COMPOSITE = "composite"
    DAVISON = "davison"
    PROGRESSED = "progressed"
    RELOCATION = "relocation"
    TRANSIT = "transit"
    EVENT = "event"


class Planet(StrEnum):
    SUN = "sun"
    MOON = "moon"
    MERCURY = "mercury"
    VENUS = "venus"
    MARS = "mars"
    JUPITER = "jupiter"
    SATURN = "saturn"
    URANUS = "uranus"
    NEPTUNE = "neptune"
    PLUTO = "pluto"
    NORTH_NODE = "north_node"
    SOUTH_NODE = "south_node"

    @property
    def is_luminary(self) -> bool:
        return self in (Planet.SUN, Planet.MOON)

    @property
    def is_point(self) -> bool:
        """Lunar nodes are calculated points, not bodies."""
        return self in (Planet.NORTH_NODE, Planet.SOUTH_NODE)

    @property
    def is_personal(self) -> bool:
        return self in (
            Planet.SUN,
            Planet.MOON,
            Planet.MERCURY,
            Planet.VENUS,
            Planet.MARS,
        )


class ZodiacSign(StrEnum):
    ARIES = "aries"
    TAURUS = "taurus"
    GEMINI = "gemini"
    CANCER = "cancer"
    LEO = "leo"
    VIRGO = "virgo"
    LIBRA = "libra"
    SCORPIO = "scorpio"
    SAGITTARIUS = "sagittarius"
    CAPRICORN = "capricorn"
    AQUARIUS = "aquarius"
    PISCES = "pisces"

    @property
    def index(self) -> int:
        return list(ZodiacSign).index(self)

    @property
    def element(self) -> "Element":
        return list(Element)[self.index % 4]

    @property
    def modality(self) -> "Modality":
        return list(Modality)[self.index % 3]

    @property
    def start_longitude(self) -> float:
        return self.index * 30.0

    @classmethod
    def from_longitude(cls, longitude: float) -> "ZodiacSign":
        return list(cls)[int(longitude % 360 // 30)]


class Element(StrEnum):
    FIRE = "fire"
    EARTH = "earth"
    AIR = "air"
    WATER = "water"


class Modality(StrEnum):
    CARDINAL = "cardinal"
    FIXED = "fixed"
    MUTABLE = "mutable"


class AspectType(StrEnum):
    CONJUNCTION = "conjunction"
    SEXTILE = "sextile"
    SQUARE = "square"
    TRINE = "trine"
    OPPOSITION = "opposition"

    @property
    def angle(self) -> float:
        return {
            AspectType.CONJUNCTION: 0.0,
            AspectType.SEXTILE: 60.0,
            AspectType.SQUARE: 90.0,
            AspectType.TRINE: 120.0,
            AspectType.OPPOSITION: 180.0,
        }[self]

    @property
    def nature(self) -> "AspectNature":
        if self in (AspectType.TRINE, AspectType.SEXTILE):
            return AspectNature.HARMONIOUS
        if self in (AspectType.SQUARE, AspectType.OPPOSITION):
            return AspectNature.CHALLENGING
        return AspectNature.NEUTRAL


class AspectNature(StrEnum):
    HARMONIOUS = "harmonious"
    CHALLENGING = "challenging"
    NEUTRAL = "neutral"


class ChartAngle(StrEnum):
    ASC = "asc"
    DSC = "dsc"
    MC = "mc"
    IC = "ic"


class MoonPhaseName(StrEnum):
    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


class TransitTargetType(StrEnum):
    NATAL_PLANET = "natal_planet"
    HOUSE = "house"
    NONE = "none"


class TransitStatus(StrEnum):
    APPROACHING = "approaching"
    EXACT = "exact"
    SEPARATING = "separating"


class CosmicEventType(StrEnum):
    NEW_MOON = "new_moon"
    FULL_MOON = "full_moon"
    MERCURY_RETROGRADE = "mercury_retrograde"
    VENUS_RETROGRADE = "venus_retrograde"
    MARS_RETROGRADE = "mars_retrograde"
    SOLAR_ECLIPSE = "solar_eclipse"
    LUNAR_ECLIPSE = "lunar_eclipse"
    CONJUNCTION = "conjunction"
    OPPOSITION = "opposition"
    SQUARE = "square"
    TRINE = "trine"
    SEXTILE = "sextile"
    PERSONAL_TRANSIT = "personal_transit"


SIGN_RULERS: dict[ZodiacSign, Planet] = {
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
