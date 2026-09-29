"""Horary conventions, as configuration.

``horary_rules_v1``. Everything a horary astrologer would argue about lives
here rather than being scattered through the code: which house answers which
question, what counts as an early or late Ascendant, which orbs apply, and
what "void of course" means.

Conventions follow William Lilly, *Christian Astrology* (1647), which is the
reference text for modern traditional horary. Where practitioners differ (the
health house, the void-of-course definition) the choice is named and
versioned, not hidden.
"""

from __future__ import annotations

from enum import StrEnum

from app.domain.enums import AspectType

HORARY_RULES_VERSION = "horary_rules_v1"

# Which definition of void of course this engine uses:
# the Moon makes no further Ptolemaic aspect to a classical planet before it
# leaves its current sign. (The alternative "no aspect within orb" definition
# gives different answers; it is not used.)
VOC_DEFINITION = "traditional_sign_based_v1"


class HoraryCategory(StrEnum):
    """Question categories the client can send.

    Mapped to houses below. An astrologer can always override the house.
    """

    GENERAL = "general"
    RELATIONSHIP = "relationship"
    MARRIAGE = "marriage"
    LOVE = "love"
    CAREER = "career"
    JOB = "job"
    BUSINESS = "business"
    MONEY = "money"
    PERSONAL_FINANCE = "personal_finance"
    DEBT = "debt"
    HOME = "home"
    PROPERTY = "property"
    FAMILY = "family"
    CHILDREN = "children"
    PREGNANCY = "pregnancy"
    HEALTH = "health"
    ILLNESS = "illness"
    EDUCATION = "education"
    TRAVEL_SHORT = "travel_short"
    TRAVEL_LONG = "travel_long"
    LOST_OBJECT = "lost_object"
    LEGAL = "legal"
    FRIEND = "friend"
    ENEMY = "enemy"
    SPIRITUAL = "spiritual"


# Category -> house of the matter asked about (the "quesited" house).
#
# Lilly's assignments. Two are conventions rather than universals and are
# marked as such in the notes below:
#   * health: house 6 (the illness) rather than house 1 (the body). Lilly
#     judges the querent's health from the 1st and the disease from the 6th;
#     this engine reports house 6 and lists house 1 as the alternative.
#   * lost object: house 2 (moveable goods) for the querent's own property.
CATEGORY_HOUSES: dict[HoraryCategory, int] = {
    HoraryCategory.GENERAL: 1,
    HoraryCategory.RELATIONSHIP: 7,
    HoraryCategory.MARRIAGE: 7,
    HoraryCategory.LOVE: 5,
    HoraryCategory.CAREER: 10,
    HoraryCategory.JOB: 10,
    HoraryCategory.BUSINESS: 10,
    HoraryCategory.MONEY: 2,
    HoraryCategory.PERSONAL_FINANCE: 2,
    HoraryCategory.DEBT: 8,
    HoraryCategory.HOME: 4,
    HoraryCategory.PROPERTY: 4,
    HoraryCategory.FAMILY: 4,
    HoraryCategory.CHILDREN: 5,
    HoraryCategory.PREGNANCY: 5,
    HoraryCategory.HEALTH: 6,
    HoraryCategory.ILLNESS: 6,
    HoraryCategory.EDUCATION: 9,
    HoraryCategory.TRAVEL_SHORT: 3,
    HoraryCategory.TRAVEL_LONG: 9,
    HoraryCategory.LOST_OBJECT: 2,
    HoraryCategory.LEGAL: 7,
    HoraryCategory.FRIEND: 11,
    HoraryCategory.ENEMY: 12,
    HoraryCategory.SPIRITUAL: 9,
}

# Alternatives worth surfacing so an astrologer can switch without arguing
# with the software.
CATEGORY_ALTERNATIVE_HOUSES: dict[HoraryCategory, tuple[int, ...]] = {
    HoraryCategory.HEALTH: (1,),
    HoraryCategory.ILLNESS: (1,),
    HoraryCategory.LOVE: (7,),
    HoraryCategory.LEGAL: (9,),
    HoraryCategory.LOST_OBJECT: (4,),
    HoraryCategory.BUSINESS: (2,),
}

# The querent is always the 1st house; the Moon is the co-significator.
QUERENT_HOUSE = 1

# Aspects that can perfect a horary judgement (Ptolemaic only).
PERFECTING_ASPECTS: tuple[AspectType, ...] = (
    AspectType.CONJUNCTION,
    AspectType.SEXTILE,
    AspectType.SQUARE,
    AspectType.TRINE,
    AspectType.OPPOSITION,
)

# Moieties (half-orbs) per planet, Lilly's table. Two planets are in aspect
# when their separation is within the sum of their moieties.
MOIETIES: dict[str, float] = {
    "sun": 7.5,
    "moon": 6.0,
    "mercury": 3.5,
    "venus": 4.0,
    "mars": 3.75,
    "jupiter": 4.5,
    "saturn": 4.5,
    "uranus": 2.5,
    "neptune": 2.5,
    "pluto": 2.5,
    "north_node": 2.5,
    "south_node": 2.5,
}

# How far ahead the engine looks for a perfection. Beyond this, an applying
# aspect is reported but not treated as perfecting the matter.
PERFECTION_SEARCH_DAYS = 30

# --- radicality -----------------------------------------------------------

# Lilly's "considerations before judgement". They are *warnings*, never an
# automatic refusal: the engine reports them and lets the astrologer decide.
EARLY_ASCENDANT_DEGREES = 3.0
LATE_ASCENDANT_DEGREES = 27.0

RADICALITY_NOTES: dict[str, str] = {
    "early_ascendant": (
        "Ascendant in the first 3 degrees of a sign: Lilly's caution that the "
        "matter may be too early to judge."
    ),
    "late_ascendant": (
        "Ascendant past 27 degrees: the matter may already be decided, or the "
        "question premature."
    ),
    "saturn_in_seventh": (
        "Saturn in the 7th: Lilly's warning about the astrologer's own "
        "judgement, not about the querent."
    ),
    "void_of_course_moon": (
        "The Moon makes no further Ptolemaic aspect before leaving its sign "
        f"({VOC_DEFINITION}); traditionally read as 'nothing will come of it'."
    ),
    "moon_via_combusta": (
        "The Moon between 15 Libra and 15 Scorpio (the via combusta), a "
        "classical caution."
    ),
    "question_repeat_suspected": (
        "A very similar question was asked recently; traditionally the same "
        "question re-asked is judged from the original chart."
    ),
    "significator_combust": (
        "A significator within 8 degrees 30 minutes of the Sun is combust and "
        "severely weakened."
    ),
    "significators_identical": (
        "The same planet rules both houses; the matter turns on one body and "
        "reception rather than an aspect between two."
    ),
}

VIA_COMBUSTA_START = 195.0  # 15 Libra
VIA_COMBUSTA_END = 225.0  # 15 Scorpio

# Similar-question window for the duplicate hint.
DUPLICATE_QUESTION_HOURS = 48


def house_for_category(
    category: HoraryCategory | None, override: int | None = None
) -> int:
    """The quesited house, with an explicit override always winning."""
    if override is not None:
        if not 1 <= override <= 12:
            raise ValueError("House must be between 1 and 12.")
        return override
    if category is None:
        return CATEGORY_HOUSES[HoraryCategory.GENERAL]
    return CATEGORY_HOUSES[category]


def derive_house(base_house: int, offset: int) -> int:
    """Turned (derived) houses: the Nth house *from* another house.

    ``derive_house(7, 2)`` is the partner's money (the 2nd from the 7th = the
    8th); ``derive_house(5, 7)`` is the child's partner. The 1st from a house
    is the house itself, which is why the offset is one-based.
    """
    if not 1 <= base_house <= 12:
        raise ValueError("Base house must be between 1 and 12.")
    if not 1 <= offset <= 12:
        raise ValueError("Offset must be between 1 and 12.")
    return (base_house - 1 + offset - 1) % 12 + 1


def moiety(planet_value: str) -> float:
    return MOIETIES.get(planet_value, 3.0)


def aspect_orb(first: str, second: str) -> float:
    """Lilly's rule: the orb is the sum of the two planets' moieties."""
    return moiety(first) + moiety(second)
