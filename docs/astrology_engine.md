# Astrology Engine

How Astrofrekans turns a birth certificate into a chart, and why each choice
was made. Nothing here is decided by an LLM: the AI layer (phase B6) receives
these numbers as context and only writes prose about them.

---

## 1. Library choice and licensing

| Option | Licence | Verdict |
| --- | --- | --- |
| **Skyfield 1.55** + JPL DE421 | MIT (library), public domain (kernel) | **Chosen** |
| pyswisseph (Swiss Ephemeris) | **AGPL-3.0** or paid commercial licence | Rejected for now |
| pymeeus | LGPL-3.0 | Lower accuracy, no houses |
| astropy | BSD | Heavier, no astrology-specific helpers |

`pyswisseph` is the usual choice in astrology software, but its AGPL-3.0
licence reaches network users: hosting an AGPL component in a closed-source
backend obliges us to publish the source of the service, or to buy the Swiss
Ephemeris commercial licence (one-off, per product). Skyfield is MIT, reads the
public-domain JPL DE ephemerides, and is accurate far beyond what astrology
needs. If a paid Swiss Ephemeris licence is bought later, a `SwissEphEngine`
can implement the same `AstrologyEngine` protocol with no other change.

**DE421** covers 1900-2050 and is 16 MB. Baked into the Docker image, so the
container needs no network at boot. DE440s (1849-2150, 32 MB) is a drop-in
replacement if birth years before 1900 are ever needed - change
`EPHEMERIS_PATH` and the `engine_version` string, which invalidates the chart
cache automatically.

## 2. Pipeline

```
birth certificate           →  BirthProfile (local date/time + place)
  ↓ geocoding                  latitude, longitude
  ↓ timezonefinder             IANA zone
  ↓ zoneinfo (historic DST)    UTC instant
  ↓ Skyfield / DE421           apparent geocentric ecliptic positions
  ↓ sidereal time → RAMC       Ascendant, Midheaven
  ↓ Placidus trisection        12 house cusps
  ↓ aspect engine              aspects with orbs, applying/separating
  ↓ weighting                  elements, modalities, dominants
                             → NatalChart
```

## 3. Time and timezone

A one-hour error moves the Ascendant by roughly 15 degrees, so the time chain
is explicit at every step:

* Birth data is stored as **local** date/time plus the **IANA zone** of the
  birth place - never as a raw UTC timestamp, because a stored offset would
  silently rot when historic DST rules are corrected.
* `zoneinfo` applies the rules of the **birth year**, not today's. Example from
  the test suite: Istanbul 1992-05-14 14:30 is UTC+3 (Turkey observed summer
  time), while 1992-01-14 14:30 is UTC+2; since September 2016 Turkey is
  permanently UTC+3.
* **DST gaps** (a local time that never existed) are shifted forward by the
  gap. **Ambiguous** times (the hour that repeats) resolve to the first,
  pre-transition occurrence, which is how birth records read.
* Everything downstream is UTC. The API returns UTC instants and the local
  offset separately.

Unknown birth time: the engine falls back to noon local, omits houses and
angles entirely, and the response carries a `birth_time_unknown` warning. It
never invents an Ascendant.

## 4. Bodies

Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, plus
the **mean** lunar nodes (Meeus 47.7). Outer planets are read from their system
barycentres, whose offset from the planet is orders of magnitude below
astrological resolution.

Positions are **apparent geocentric ecliptic** coordinates (light-time and
aberration corrected) in the ecliptic-of-date frame - the convention western
tropical astrology uses.

**Retrograde** is measured, not guessed: longitude speed comes from a central
difference over ±6 hours, and `retrograde = speed < 0`. The test suite checks
the consequence rather than the number: Mercury comes out retrograde 18.1% of
2026 in three runs of 20-24 days, matching the real ~19% in three runs a year.

## 5. Angles and houses

With `RAMC` the right ascension of the Midheaven, `ε` the obliquity of date and
`φ` the geographic latitude:

```
MC  = atan2( sin RAMC, cos RAMC · cos ε )
ASC = atan2( cos RAMC, −( sin RAMC · cos ε + tan φ · sin ε ) )
DSC = ASC + 180°     IC = MC + 180°
```

Sanity anchor used in the tests: at the equator with `RAMC = 0`, the MC is
0° Aries and the Ascendant is exactly 0° Cancer.

**Placidus** (default) trisects the semi-arcs. For a point of declination `δ`
the diurnal semi-arc is `D = acos(−tan φ · tan δ)` and the nocturnal one is
`N = 180° − D`, so:

| Cusp | Right ascension |
| --- | --- |
| 11 | `RAMC + D/3` |
| 12 | `RAMC + 2D/3` |
| 2 | `RAMC + 180° − 2N/3` |
| 3 | `RAMC + 180° − N/3` |

`δ` depends on the cusp being solved for, so each is found by fixed-point
iteration (a handful of steps outside the polar circles). Cusps 5, 6, 8, 9 are
the opposites of 11, 12, 2, 3.

**Placidus is undefined inside the polar circles.** Above |latitude| = 66° the
engine falls back to Whole Sign and reports it: the response carries
`house_system` (what was used), `requested_house_system` (what was asked for)
and a `house_system_fallback` warning. Whole Sign and Equal are implemented;
Koch currently falls back to Placidus geometry and is not yet a separate
system.

## 6. Aspects

Ptolemaic set only: conjunction 0°, sextile 60°, square 90°, trine 120°,
opposition 180°. Orbs are a replaceable policy object, not scattered
constants:

| Aspect | Natal orb | Transit orb |
| --- | --- | --- |
| Conjunction | 8° | 3° |
| Opposition | 8° | 3° |
| Trine | 7° | 3° |
| Square | 6° | 3° |
| Sextile | 4° | 2° |

Modifiers: +2° when the Sun or Moon is involved (+1° for transits), −2° when a
lunar node is (−1° for transits); the floor is 1°. Only the tightest aspect
between a pair is kept. The south node is skipped inside a single chart - it
mirrors the north node and would double every hit.

**Applying vs separating** is computed from both bodies' longitude speeds: the
orb is projected a short step forward, and the aspect is applying when the orb
shrinks. With no speed data the answer is `false` rather than a guess.

## 7. Elements, modalities and dominants

Element and modality counts cover the ten bodies; the nodes are excluded
because they are calculated points, not planets. Both distributions therefore
sum to 10.

The **dominant planet** score is deliberately explicit and testable:

| Contribution | Weight |
| --- | --- |
| Body is the Sun or Moon | +3.0 |
| Body sits in an angular house (1, 4, 7, 10) | +2.0 |
| Per aspect made | +1.0 (+1.5 for a conjunction), scaled by `1 − min(orb, 8)/10` |
| Rules the Sun, Moon or Ascendant sign | +2.0 each |

Dominant element and modality are simply the largest bucket. All three are
pure functions of the chart, so the same birth data always gives the same
answer - no randomness anywhere in the engine.

## 8. Moon phase

Phase is driven by the true Sun-Moon elongation, not by a mean synodic clock:

* `illumination = (1 − cos elongation) / 2`
* `age_days = elongation / 360 × 29.530588853`
* the four quarter points own an 11.25° window each; the rest are the
  crescent/gibbous phases,
* `next_phase_at` is found by bisection on the elongation, to the second.

Verified in tests: consecutive new moons are 29.2-29.9 days apart (true value
29.53), illumination is < 0.01 at the computed new moon and > 0.99 at the full
moon.

## 9. Accuracy and verification

Regression tests check published astronomical events rather than our own
output:

| Event | Published instant (UTC) | Engine result |
| --- | --- | --- |
| March equinox 2026 | 2026-03-20 14:46 | Sun 0.0000° |
| June solstice 2026 | 2026-06-21 08:25 | Sun 90.0003° |
| December solstice 2025 | 2025-12-21 15:03 | Sun 269.9999° |
| Uranus-Neptune conjunction 1993 | 1993-02-02 | separation < 1° |

Plus invariants: synodic month length, Mercury retrograde frequency and run
length, Moon speed 11-15°/day, nodes exactly opposite and always retrograde,
houses spanning exactly 360° with opposite cusps 180° apart.

## 10. Caching

A chart is a pure function of (birth data, house system, engine version), so
the cache key is a SHA-256 of exactly those:

* **Redis**, TTL 30 days, for the hot path;
* **`natal_charts` table**, permanent, so a cold cache after a deploy does not
  re-run the ephemeris for every user.

Changing `ENGINE_VERSION` (new kernel, new algorithm) changes every key, which
retires the old cache without a migration.

## 11. Extending

`AstrologyEngine` (Protocol, `app/services/astrology/engine.py`) is the seam.
Anything implementing `positions`, `natal_chart`, `moon_phase` and
`next_phase_moment` can be dropped in - a Swiss Ephemeris build, a remote
calculation service, or a fixture engine for tests. Transits, synastry,
composite and Davison charts (phases B4-B5) build on the same primitives:
positions at an instant, aspect search between two sets of longitudes, and
root-finding on the orb for exact timings.
