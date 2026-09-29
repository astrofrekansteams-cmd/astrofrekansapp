"""Scoring configuration.

Every number the forecast layer uses lives here, versioned. Nothing is
sprinkled through the scoring logic, and nothing is random: the same chart, date and
``SCORING_VERSION`` always produce the same scores.

Raising a weight means bumping the version, which invalidates every cached
forecast - that is the point.
"""

from __future__ import annotations

from app.domain.enums import AspectType, ChartAngle, Planet
from app.domain.horoscope import LifeArea

SCORING_VERSION = "b4.scoring.v1"
ORB_POLICY_VERSION = "b4.orbs.v1"

# --------------------------------------------------------------- transit orbs

# Maximum orb (degrees) for a transiting aspect to a natal point. Tighter than
# natal orbs: a transit only "counts" close to exact.
TRANSIT_ORBS: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 3.0,
    AspectType.OPPOSITION: 3.0,
    AspectType.SQUARE: 2.5,
    AspectType.TRINE: 2.5,
    AspectType.SEXTILE: 2.0,
}

# The Moon moves 13 degrees a day, so a 3 degree orb would be "all day, every
# day"; the outer planets need room or nothing would ever be in orb.
BODY_ORB_FACTOR: dict[Planet, float] = {
    Planet.MOON: 0.6,
    Planet.SUN: 1.0,
    Planet.MERCURY: 1.0,
    Planet.VENUS: 1.0,
    Planet.MARS: 1.0,
    Planet.JUPITER: 1.1,
    Planet.SATURN: 1.1,
    Planet.URANUS: 1.2,
    Planet.NEPTUNE: 1.2,
    Planet.PLUTO: 1.2,
    Planet.NORTH_NODE: 0.8,
    Planet.SOUTH_NODE: 0.8,
}

# ------------------------------------------------------------ transit weights

# How much weight a transiting body carries. Slow bodies matter more because
# their transits are rare and long.
TRANSITING_BODY_WEIGHT: dict[Planet, float] = {
    Planet.MOON: 0.30,
    Planet.SUN: 0.70,
    Planet.MERCURY: 0.50,
    Planet.VENUS: 0.60,
    Planet.MARS: 0.70,
    Planet.JUPITER: 0.85,
    Planet.SATURN: 0.95,
    Planet.URANUS: 0.90,
    Planet.NEPTUNE: 0.85,
    Planet.PLUTO: 1.00,
    Planet.NORTH_NODE: 0.55,
    Planet.SOUTH_NODE: 0.55,
}

# How much a natal point matters as a target.
NATAL_TARGET_WEIGHT: dict[Planet, float] = {
    Planet.SUN: 1.00,
    Planet.MOON: 1.00,
    Planet.MERCURY: 0.75,
    Planet.VENUS: 0.80,
    Planet.MARS: 0.75,
    Planet.JUPITER: 0.65,
    Planet.SATURN: 0.70,
    Planet.URANUS: 0.50,
    Planet.NEPTUNE: 0.50,
    Planet.PLUTO: 0.50,
    Planet.NORTH_NODE: 0.60,
    Planet.SOUTH_NODE: 0.55,
}

ANGLE_TARGET_WEIGHT: dict[ChartAngle, float] = {
    ChartAngle.ASC: 1.00,
    ChartAngle.MC: 0.95,
    ChartAngle.DSC: 0.85,
    ChartAngle.IC: 0.85,
}

# Balanced on purpose: the hard aspects must not outweigh the soft ones, or
# every reading drifts negative simply because squares are counted heavier.
ASPECT_WEIGHT: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 1.00,
    AspectType.OPPOSITION: 0.90,
    AspectType.SQUARE: 0.85,
    AspectType.TRINE: 0.90,
    AspectType.SEXTILE: 0.70,
}

APPLYING_FACTOR = 1.10
SEPARATING_FACTOR = 0.90
ANGLE_INVOLVEMENT_BONUS = 1.15
MULTI_PASS_BONUS = 1.10

# Orb closeness curve: 1 at exact, 0 at the orb limit, falling off faster than
# linear so "nearly exact" dominates.
ORB_FALLOFF_EXPONENT = 1.5

# ----------------------------------------------------------- area mapping

# Which life areas a transit touches, by the *natal* point being hit.
TARGET_AREAS: dict[Planet, tuple[LifeArea, ...]] = {
    Planet.SUN: (LifeArea.GENERAL_ENERGY, LifeArea.PERSONAL_GROWTH, LifeArea.CAREER),
    Planet.MOON: (LifeArea.MOOD, LifeArea.HEALTH_BALANCE, LifeArea.RELATIONSHIPS),
    Planet.MERCURY: (LifeArea.CAREER, LifeArea.PERSONAL_GROWTH),
    Planet.VENUS: (LifeArea.LOVE, LifeArea.RELATIONSHIPS, LifeArea.MONEY),
    Planet.MARS: (LifeArea.GENERAL_ENERGY, LifeArea.CAREER, LifeArea.HEALTH_BALANCE),
    Planet.JUPITER: (LifeArea.LUCK, LifeArea.MONEY, LifeArea.PERSONAL_GROWTH),
    Planet.SATURN: (LifeArea.CAREER, LifeArea.HEALTH_BALANCE, LifeArea.PERSONAL_GROWTH),
    Planet.URANUS: (LifeArea.PERSONAL_GROWTH, LifeArea.GENERAL_ENERGY),
    Planet.NEPTUNE: (LifeArea.PERSONAL_GROWTH, LifeArea.MOOD),
    Planet.PLUTO: (LifeArea.PERSONAL_GROWTH, LifeArea.MONEY),
    Planet.NORTH_NODE: (LifeArea.PERSONAL_GROWTH,),
    Planet.SOUTH_NODE: (LifeArea.PERSONAL_GROWTH,),
}

# Which areas a transiting body brings with it.
TRANSITING_AREAS: dict[Planet, tuple[LifeArea, ...]] = {
    Planet.MOON: (LifeArea.MOOD,),
    Planet.SUN: (LifeArea.GENERAL_ENERGY,),
    Planet.MERCURY: (LifeArea.CAREER,),
    Planet.VENUS: (LifeArea.LOVE, LifeArea.MONEY),
    Planet.MARS: (LifeArea.GENERAL_ENERGY, LifeArea.CAREER),
    Planet.JUPITER: (LifeArea.LUCK, LifeArea.MONEY),
    Planet.SATURN: (LifeArea.CAREER,),
    Planet.URANUS: (LifeArea.PERSONAL_GROWTH,),
    Planet.NEPTUNE: (LifeArea.MOOD,),
    Planet.PLUTO: (LifeArea.PERSONAL_GROWTH,),
    Planet.NORTH_NODE: (LifeArea.PERSONAL_GROWTH,),
    Planet.SOUTH_NODE: (LifeArea.PERSONAL_GROWTH,),
}

# Houses carry their traditional meanings into the areas.
HOUSE_AREAS: dict[int, tuple[LifeArea, ...]] = {
    1: (LifeArea.GENERAL_ENERGY, LifeArea.PERSONAL_GROWTH),
    2: (LifeArea.MONEY,),
    3: (LifeArea.CAREER, LifeArea.PERSONAL_GROWTH),
    4: (LifeArea.HEALTH_BALANCE, LifeArea.RELATIONSHIPS),
    5: (LifeArea.LOVE, LifeArea.LUCK),
    6: (LifeArea.HEALTH_BALANCE, LifeArea.CAREER),
    7: (LifeArea.RELATIONSHIPS, LifeArea.LOVE),
    8: (LifeArea.MONEY, LifeArea.PERSONAL_GROWTH),
    9: (LifeArea.PERSONAL_GROWTH, LifeArea.LUCK),
    10: (LifeArea.CAREER,),
    11: (LifeArea.RELATIONSHIPS, LifeArea.LUCK),
    12: (LifeArea.HEALTH_BALANCE, LifeArea.MOOD),
}

# Benefic / malefic colouring: the sign of a factor's contribution.
BENEFIC_BODIES = (Planet.VENUS, Planet.JUPITER)
MALEFIC_BODIES = (Planet.MARS, Planet.SATURN, Planet.PLUTO)

HARMONIOUS_SIGN = 1.0
CHALLENGING_SIGN = -1.0
CONJUNCTION_BENEFIC_SIGN = 1.0
CONJUNCTION_MALEFIC_SIGN = -0.6
CONJUNCTION_NEUTRAL_SIGN = 0.4

# ------------------------------------------------------- daily frequency

DAILY_FREQUENCY_VERSION = "daily_frequency_v1"

# Every score starts here and moves with the day's factors.
BASELINE_SCORE = 55

# How far a fully saturated area can move from the baseline, and how much
# accumulated factor weight counts as "fully saturated". Contributions are
# combined through tanh, so a day with twenty transits cannot pin every score
# to the floor: more of the same influence keeps the reading in range instead
# of collapsing it.
AREA_SENSITIVITY = 34.0
AREA_SATURATION = 2.2

# The Moon's house placement colours the whole day.
MOON_HOUSE_WEIGHT = 0.45
MOON_PHASE_WEIGHT = 0.30
RETROGRADE_PENALTY = 0.25

# Score floor and ceiling, so a bad day is never 0 and a good one never 100.
SCORE_MIN = 12
SCORE_MAX = 96

# --------------------------------------------------------- important hours

# Window drawn around an exact aspect, scaled by its strength.
IMPORTANT_HOUR_BASE_MINUTES = 45
IMPORTANT_HOUR_MAX_MINUTES = 110
# Moon contacts are what make one hour differ from the next, and the Moon
# scores low by design, so this floor is deliberately low.
IMPORTANT_HOUR_MIN_STRENGTH = 6
MAX_IMPORTANT_HOURS = 4

# ------------------------------------------------------------- clustering

# A cluster is a *relatively* busy stretch, so the threshold is the period's
# own mean plus a fraction of its spread; the absolute floor stops a quiet
# month from inventing key periods.
CLUSTER_THRESHOLD = 0.35
CLUSTER_RELATIVE_SIGMA = 0.75
CLUSTER_MIN_DAYS = 2
CLUSTER_MAX_GAP_DAYS = 1
MAX_CLUSTERS = 6

# ------------------------------------------------------------ selection

# How many transits a period's "major" list keeps.
MAJOR_TRANSIT_LIMIT = {
    "daily": 8,
    "weekly": 12,
    "monthly": 20,
    "yearly": 40,
}

MIN_MAJOR_STRENGTH = 20
