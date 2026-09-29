"""Synastry scoring configuration.

``synastry_score_v1``. Every weight the compatibility score uses is here, and
every one of them is explained in ``docs/synastry_engine.md``.

Three things this scoring is **not**:

* it is not a probability that a relationship will last,
* it is not a ranking of people,
* it is not derived from an LLM.

It is an astrological factor index: how much classical relationship symbolism
this pair of charts contains, computed the same way every time.
"""

from __future__ import annotations

from app.domain.compatibility import RelationshipTheme as T
from app.domain.enums import AspectType, ChartAngle, Planet

SYNASTRY_SCORING_VERSION = "synastry_score_v1"
SYNASTRY_ORB_VERSION = "synastry_orbs_v1"

# --- orbs -----------------------------------------------------------------

# Wider than transit orbs (both charts are static, so an inter-aspect is a
# standing condition) but tighter than natal orbs for the minor pairs.
SYNASTRY_ORBS: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 8.0,
    AspectType.OPPOSITION: 7.0,
    AspectType.TRINE: 6.0,
    AspectType.SQUARE: 6.0,
    AspectType.SEXTILE: 4.0,
}

LUMINARY_ORB_BONUS = 2.0
ANGLE_ORB_BONUS = 1.0
NODE_ORB_PENALTY = -2.0
MIN_ORB = 1.0

# --- aspect quality -------------------------------------------------------

ASPECT_WEIGHT: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 1.00,
    AspectType.TRINE: 0.85,
    AspectType.OPPOSITION: 0.75,
    AspectType.SQUARE: 0.70,
    AspectType.SEXTILE: 0.55,
}

# Sign of an aspect's contribution. Oppositions and squares are not simply
# "bad" in a relationship - they are the charge - so they contribute
# positively to conflict and sexual chemistry and negatively to trust and the
# long-term themes. See THEME_POLARITY below.
HARMONIOUS_ASPECTS = (AspectType.TRINE, AspectType.SEXTILE)
CHALLENGING_ASPECTS = (AspectType.SQUARE, AspectType.OPPOSITION)

# --- pair weights ---------------------------------------------------------

# The classical relationship pairs, weighted by how much traditional and
# modern practice leans on them. A pair not listed falls back to
# DEFAULT_PAIR_WEIGHT.
PAIR_WEIGHTS: dict[frozenset[Planet], float] = {
    frozenset({Planet.SUN, Planet.MOON}): 1.00,
    frozenset({Planet.MOON}): 0.90,  # Moon-Moon
    frozenset({Planet.VENUS, Planet.MARS}): 0.95,
    frozenset({Planet.SUN, Planet.VENUS}): 0.75,
    frozenset({Planet.MOON, Planet.VENUS}): 0.80,
    frozenset({Planet.SUN, Planet.SUN}): 0.70,
    frozenset({Planet.VENUS}): 0.75,  # Venus-Venus
    frozenset({Planet.MARS}): 0.65,  # Mars-Mars
    frozenset({Planet.MERCURY}): 0.70,  # Mercury-Mercury
    frozenset({Planet.MERCURY, Planet.MOON}): 0.70,
    frozenset({Planet.MOON, Planet.MARS}): 0.70,
    frozenset({Planet.SUN, Planet.MARS}): 0.65,
    frozenset({Planet.SATURN, Planet.SUN}): 0.75,
    frozenset({Planet.SATURN, Planet.MOON}): 0.75,
    frozenset({Planet.SATURN, Planet.VENUS}): 0.75,
    frozenset({Planet.SATURN, Planet.MARS}): 0.60,
    frozenset({Planet.JUPITER, Planet.SUN}): 0.60,
    frozenset({Planet.JUPITER, Planet.MOON}): 0.60,
    frozenset({Planet.JUPITER, Planet.VENUS}): 0.60,
    frozenset({Planet.PLUTO, Planet.VENUS}): 0.70,
    frozenset({Planet.PLUTO, Planet.MARS}): 0.60,
    frozenset({Planet.PLUTO, Planet.MOON}): 0.60,
    frozenset({Planet.URANUS, Planet.VENUS}): 0.55,
    frozenset({Planet.NEPTUNE, Planet.VENUS}): 0.55,
    frozenset({Planet.NORTH_NODE, Planet.SUN}): 0.70,
    frozenset({Planet.NORTH_NODE, Planet.MOON}): 0.70,
    frozenset({Planet.NORTH_NODE, Planet.VENUS}): 0.65,
    frozenset({Planet.SOUTH_NODE, Planet.SUN}): 0.60,
    frozenset({Planet.SOUTH_NODE, Planet.MOON}): 0.60,
    frozenset({Planet.SOUTH_NODE, Planet.VENUS}): 0.60,
}

DEFAULT_PAIR_WEIGHT = 0.35

# Contacts to the angles: the Ascendant is the person, the MC their direction
# in the world. A planet on either is felt.
ANGLE_WEIGHTS: dict[ChartAngle, float] = {
    ChartAngle.ASC: 0.90,
    ChartAngle.MC: 0.70,
}

ANGLE_PLANET_WEIGHTS: dict[Planet, float] = {
    Planet.SUN: 1.00,
    Planet.MOON: 1.00,
    Planet.VENUS: 0.95,
    Planet.MARS: 0.85,
    Planet.MERCURY: 0.70,
    Planet.JUPITER: 0.70,
    Planet.SATURN: 0.75,
    Planet.URANUS: 0.55,
    Planet.NEPTUNE: 0.55,
    Planet.PLUTO: 0.65,
    Planet.NORTH_NODE: 0.65,
    Planet.SOUTH_NODE: 0.55,
}

# --- house overlays -------------------------------------------------------

# Which houses matter for a relationship, and how much a planet landing there
# counts. Directional: this is "A's planet in B's house".
OVERLAY_HOUSE_WEIGHTS: dict[int, float] = {
    1: 0.80,
    2: 0.45,
    3: 0.40,
    4: 0.65,
    5: 0.85,
    6: 0.35,
    7: 0.95,
    8: 0.80,
    9: 0.45,
    10: 0.55,
    11: 0.55,
    12: 0.50,
}

OVERLAY_PLANET_WEIGHTS: dict[Planet, float] = {
    Planet.SUN: 0.90,
    Planet.MOON: 1.00,
    Planet.VENUS: 0.95,
    Planet.MARS: 0.85,
    Planet.MERCURY: 0.60,
    Planet.JUPITER: 0.70,
    Planet.SATURN: 0.70,
    Planet.URANUS: 0.45,
    Planet.NEPTUNE: 0.45,
    Planet.PLUTO: 0.55,
    Planet.NORTH_NODE: 0.60,
    Planet.SOUTH_NODE: 0.50,
}

OVERLAY_SCALE = 0.45  # overlays weigh less than exact inter-aspects

# --- themes ---------------------------------------------------------------

# Which themes a planetary pair speaks to.
PAIR_THEMES: dict[frozenset[Planet], tuple[T, ...]] = {
    frozenset({Planet.SUN, Planet.MOON}): (T.GENERAL, T.EMOTIONAL, T.LONG_TERM),
    frozenset({Planet.MOON}): (T.EMOTIONAL, T.TRUST),
    frozenset({Planet.VENUS, Planet.MARS}): (T.ROMANCE, T.SEXUAL_CHEMISTRY),
    frozenset({Planet.VENUS}): (T.ROMANCE, T.GENERAL),
    frozenset({Planet.MARS}): (T.SEXUAL_CHEMISTRY, T.CONFLICT),
    frozenset({Planet.MERCURY}): (T.COMMUNICATION,),
    frozenset({Planet.MERCURY, Planet.MOON}): (T.COMMUNICATION, T.EMOTIONAL),
    frozenset({Planet.SUN, Planet.VENUS}): (T.ROMANCE, T.GENERAL),
    frozenset({Planet.MOON, Planet.VENUS}): (T.EMOTIONAL, T.ROMANCE),
    frozenset({Planet.MOON, Planet.MARS}): (T.EMOTIONAL, T.CONFLICT),
    frozenset({Planet.SUN, Planet.MARS}): (T.CONFLICT, T.SEXUAL_CHEMISTRY),
    frozenset({Planet.SATURN, Planet.SUN}): (T.LONG_TERM, T.TRUST),
    frozenset({Planet.SATURN, Planet.MOON}): (T.LONG_TERM, T.EMOTIONAL),
    frozenset({Planet.SATURN, Planet.VENUS}): (T.LONG_TERM, T.ROMANCE),
    frozenset({Planet.SATURN, Planet.MARS}): (T.CONFLICT, T.LONG_TERM),
    frozenset({Planet.JUPITER, Planet.SUN}): (T.GENERAL, T.TRUST),
    frozenset({Planet.JUPITER, Planet.MOON}): (T.EMOTIONAL, T.TRUST),
    frozenset({Planet.JUPITER, Planet.VENUS}): (T.ROMANCE, T.GENERAL),
    frozenset({Planet.PLUTO, Planet.VENUS}): (T.SEXUAL_CHEMISTRY, T.KARMIC),
    frozenset({Planet.PLUTO, Planet.MARS}): (T.SEXUAL_CHEMISTRY, T.CONFLICT),
    frozenset({Planet.PLUTO, Planet.MOON}): (T.KARMIC, T.EMOTIONAL),
    frozenset({Planet.URANUS, Planet.VENUS}): (T.ROMANCE, T.CONFLICT),
    frozenset({Planet.NEPTUNE, Planet.VENUS}): (T.ROMANCE, T.TRUST),
    frozenset({Planet.NORTH_NODE, Planet.SUN}): (T.KARMIC, T.LONG_TERM),
    frozenset({Planet.NORTH_NODE, Planet.MOON}): (T.KARMIC, T.EMOTIONAL),
    frozenset({Planet.NORTH_NODE, Planet.VENUS}): (T.KARMIC, T.ROMANCE),
    frozenset({Planet.SOUTH_NODE, Planet.SUN}): (T.KARMIC,),
    frozenset({Planet.SOUTH_NODE, Planet.MOON}): (T.KARMIC,),
    frozenset({Planet.SOUTH_NODE, Planet.VENUS}): (T.KARMIC, T.ROMANCE),
}

# Pairs that are not in the table above are still reported as aspects - they
# are real contacts and the client may want them - but they do not move any
# theme score. Letting every Jupiter-Neptune contact feed "general" would
# saturate that theme for every couple and destroy its discriminating power.
DEFAULT_THEMES: tuple[T, ...] = ()

HOUSE_THEMES: dict[int, tuple[T, ...]] = {
    1: (T.GENERAL,),
    2: (T.LONG_TERM,),
    3: (T.COMMUNICATION,),
    4: (T.EMOTIONAL, T.LONG_TERM),
    5: (T.ROMANCE, T.SEXUAL_CHEMISTRY),
    6: (T.GENERAL,),
    7: (T.LONG_TERM, T.GENERAL),
    8: (T.SEXUAL_CHEMISTRY, T.TRUST, T.KARMIC),
    9: (T.GENERAL,),
    10: (T.LONG_TERM,),
    11: (T.GENERAL, T.TRUST),
    12: (T.KARMIC, T.TRUST),
}

# How a challenging aspect reads per theme. Squares and oppositions *build*
# conflict and sexual charge while they cost trust and stability, so the sign
# of the contribution depends on the theme, not only on the aspect.
THEME_POLARITY: dict[T, dict[str, float]] = {
    T.GENERAL: {"harmonious": 1.0, "challenging": -0.7, "conjunction": 0.8},
    T.EMOTIONAL: {"harmonious": 1.0, "challenging": -0.6, "conjunction": 0.9},
    T.COMMUNICATION: {"harmonious": 1.0, "challenging": -0.6, "conjunction": 0.9},
    T.ROMANCE: {"harmonious": 1.0, "challenging": -0.4, "conjunction": 1.0},
    T.SEXUAL_CHEMISTRY: {"harmonious": 0.8, "challenging": 0.7, "conjunction": 1.0},
    T.TRUST: {"harmonious": 1.0, "challenging": -0.9, "conjunction": 0.6},
    T.LONG_TERM: {"harmonious": 1.0, "challenging": -0.8, "conjunction": 0.7},
    T.CONFLICT: {"harmonious": -0.6, "challenging": 1.0, "conjunction": 0.4},
    T.KARMIC: {"harmonious": 0.8, "challenging": 0.6, "conjunction": 1.0},
}

# --- normalisation --------------------------------------------------------

# Raw weight is unbounded, so the published score saturates: 50 is "an average
# amount of relationship symbolism", not "a 50% chance of anything".
THEME_BASELINE = 50.0
THEME_SENSITIVITY = 34.0
THEME_SATURATION = 2.6
THEME_MIN = 10
THEME_MAX = 95

# The overall score is the weighted mean of the themes; conflict is inverted
# first, because a high conflict index is not a high compatibility index.
OVERALL_THEME_WEIGHTS: dict[T, float] = {
    T.GENERAL: 1.2,
    T.EMOTIONAL: 1.1,
    T.COMMUNICATION: 0.9,
    T.ROMANCE: 1.1,
    T.SEXUAL_CHEMISTRY: 0.8,
    T.TRUST: 1.0,
    T.LONG_TERM: 1.2,
    T.CONFLICT: 0.7,
    T.KARMIC: 0.6,
}

INVERTED_THEMES: tuple[T, ...] = (T.CONFLICT,)

SCORE_SEMANTICS = (
    "astrological compatibility index: how much classical relationship "
    "symbolism these two charts contain. Not a probability, not a prediction, "
    "and not comparable between different scoring versions."
)

HIGHLIGHT_LIMIT = 8
MIN_HIGHLIGHT_WEIGHT = 0.45
