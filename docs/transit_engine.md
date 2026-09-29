# Transit, Calendar and Forecast Engine (B4)

Everything the app shows as a number - a transit's strength, the daily
frequency dials, a month's key periods - is produced here, deterministically,
from real ephemeris positions. No randomness, no lookup tables of "lucky
hours", and no LLM anywhere near a score. Astro AI (phase B6) writes prose
*about* these numbers; it never produces them.

---

## 1. How a scan works

A scalar ephemeris call costs ~2.4 ms, a vectorised one ~0.08 ms per instant.
Every search in this package is therefore shaped the same way:

1. **Sample once.** Each body's longitude is sampled on a coarse grid over the
   window in a single vectorised call (grid step per body: Moon 2 h, Mercury
   8 h, Sun/Venus 12 h, Mars 1 d, Jupiter/Saturn 2 d, outer planets 4 d).
2. **Find brackets in numpy.** In-orb stretches, zero crossings and sign
   changes are located on the sampled array - no ephemeris work at all.
3. **Refine in batches.** Every bracket is bisected *together*: one more
   vectorised call per round, not one per bracket. A whole year of transits
   refines in about twenty rounds.

That is the difference between a 90-second yearly scan and a 5-second one; the
numbers are in `reports/backend_b4_performance.md`.

## 2. Transits

Transiting bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus,
Neptune, Pluto. Targets: the ten natal bodies plus the north node, and the
Ascendant and Midheaven. Aspects: conjunction, opposition, trine, square,
sextile (quincunx and semisextile are a later addition; the enum and orb table
are where they will go).

### Windows and passes

A transit is not an instant. For each (body, target, aspect) the engine finds
the **window** where the orb stays inside its limit, and inside that window
every **pass** where the aspect perfects:

```
start_at ──── pass 1 ──── pass 2 (retrograde) ──── pass 3 ──── end_at
```

Saturn trine natal Venus can perfect three times - direct, retrograde, direct -
and astrologers read that as one story with three beats. The engine models it
that way: one `TransitEvent` with three `TransitPass` entries, each with its
own exact instant and direction. Collapsing them into three separate transits,
or into one "exact date", would be wrong both astrologically and in the UI.

Window edges are found by bisecting the orb against its limit; exact passes by
bisecting the longitude against the contact degree. Both to well under a
minute.

`window_clipped` is set when the window runs past the search horizon (Pluto can
hold a 3.6° orb for years). The engine reports the horizon rather than walking
a decade of ephemeris, and says so in the flag.

### Orbs

| Aspect | Base orb |
| --- | --- |
| Conjunction | 3.0° |
| Opposition | 3.0° |
| Square | 2.5° |
| Trine | 2.5° |
| Sextile | 2.0° |

Scaled per body: Moon ×0.6 (it moves 13°/day - a 3° orb would be "all day,
every day"), inner planets ×1.0, Jupiter/Saturn ×1.1, outer planets ×1.2,
nodes ×0.8. All of it lives in `app/services/astrology/weights.py` under
`ORB_POLICY_VERSION`.

### Strength (0-100)

```
closeness      = (1 - peak_orb / orb_limit) ^ 1.5
strength       = 100 × closeness
                     × aspect_weight
                     × transiting_body_weight
                     × target_weight
                     × (1.10 if applying else 0.90)
                     × (1.15 if the target is an angle)
                     × (1.10 if the transit perfects more than once)
```

* **`peak_orb` is the tightest orb the transit reaches inside the requested
  window**, not the orb at the sampling instant. This matters: judging a Moon
  transit by its orb at midday scores it at zero even when it perfected that
  morning. If the aspect perfects inside the window, `peak_orb` is 0.
* `aspect_weight`: conjunction 1.00, opposition 0.90, trine 0.90, square 0.85,
  sextile 0.70. Deliberately balanced - weighting the hard aspects heavier
  drifts every reading negative.
* `transiting_body_weight`: Moon 0.30 … Saturn 0.95, Pluto 1.00. Slow bodies
  matter more because their transits are rare and long.
* `target_weight`: Sun/Moon 1.00, Venus 0.80, Mercury/Mars 0.75, … outer 0.50;
  Ascendant 1.00, MC 0.95.

The result is stable: same chart, same window, same version → same number.

### House ingress

Transiting bodies are tracked across the natal cusps. Each crossing is its own
record with `from_house`, `to_house`, `entered_at`, an estimated exit and a
`retrograde` flag; a planet that backs out of a house and returns gets a second
record marked `re_entry`. Tested over a full year, which always contains at
least one.

## 3. Cosmic calendar

| Event | How it is found |
| --- | --- |
| New / full moon, quarters | The instant the true Sun-Moon elongation reaches 0°, 90°, 180°, 270°, by batched bisection |
| Stations | Where the longitude speed changes sign - measured, not tabulated |
| Retrograde periods | Station pairs, searched ±200 days outside the window so a retrograde that began earlier still reports its real start |
| Ingresses | Crossings of multiples of 30° |
| Mundane aspects | Exact aspects between Mars and the outer planets (inner-planet pairs would be noise) |

### Eclipses

Not "a full moon near a node". Two steps:

1. **Gate** (cheap): the syzygy must be within 18.6° (solar) or 12.5° (lunar)
   of a lunar node, otherwise no eclipse is geometrically possible. This skips
   the expensive work on ~80% of lunations.
2. **Geometry** (Meeus ch. 54): the syzygy is refined to the instant of least
   angular separation, then apparent semi-diameters, the Moon's horizontal
   parallax and the shadow radii are computed from the real distances.
   * Solar: an eclipse occurs somewhere on Earth when the geocentric
     separation is smaller than `sun_semi + moon_semi + moon_parallax`.
   * Lunar: the Moon's distance from the shadow axis is compared with the
     umbral and penumbral radii → total / partial / penumbral, plus a
     magnitude.

**Solar subtype is deliberately `null`.** Total vs annular vs partial depends
on where the shadow axis lands, which needs Besselian elements this engine does
not compute. A wrong "total eclipse" is worse than no label, so the field stays
null and the reason is in the event metadata.

Validation (in `tests/test_transit_engine.py`, fixtures carry the sources):

| 2026 eclipse | Published (NASA) | Engine |
| --- | --- | --- |
| 17 Feb | annular solar | solar eclipse ✓, subtype null by design |
| 3 Mar | total lunar | lunar eclipse ✓, **total** ✓ |
| 12 Aug | total solar | solar eclipse ✓, subtype null by design |
| 28 Aug | partial lunar | lunar eclipse ✓, **partial** ✓ |

25 lunations in 2026, exactly 4 eclipses, no false positives. Mercury
retrograde windows for 2026 land on the published dates (26 Feb–20 Mar,
29 Jun–23 Jul, 24 Oct–13 Nov), Venus 3 Oct–14 Nov.

## 4. Personal calendar

A global event becomes personal through the chart: which natal house the event
falls in, what it aspects natally (orbs: conjunction/opposition 5°, square/
trine 4°, sextile 3°), and a relevance score:

```
base           eclipse 90/85, full moon 60, new moon 55, station 50/45, ingress 30
+ up to 25     for a tight natal contact  (25 × (1 - orb/5))
+ 10           if it lands in an angular house (1, 4, 7, 10)
+ 5            any other house
```

## 5. Scoring, and why every number is explainable

Each influence becomes a `SourceFactor`: an id, a label, a signed
contribution, and the life areas it touches. Scores are built from those
factors and keep their ids, which is what lets the app show "the influences
behind this reading" and lets an expert or the AI see *why* a number is what
it is.

```
contribution   = (strength / 100) × polarity
polarity       = +1 trine/sextile, -1 square/opposition,
                 conjunction: +1 with Venus/Jupiter, -0.6 with Mars/Saturn/Pluto,
                 +0.4 otherwise
score(area)    = 55 + 34 × tanh( Σ contributions(area) / 2.2 ),  clamped to 12..96
```

`tanh` is the important part: a day with twenty transits cannot pin every
score to the floor. More of the same influence keeps the reading in range
instead of collapsing it, while the ordering between areas is preserved.

Life areas: `general_energy`, `love`, `relationships`, `career`, `money`,
`health_balance`, `personal_growth`, `luck`, `mood`. A transit's areas come
from the natal point it hits, the transiting body, and the houses involved
(house 7 → relationships, house 2 → money, …).

Measured distribution across three charts and four months: mean overall 58,
range 47-77, influences balanced 70 positive / 74 negative - no systematic
drift in either direction.

## 6. Daily frequency

`daily_frequency_v1`. Inputs: the day's transits, the Moon's natal house, the
moon phase, and any active retrograde. Output: a score per life area, an
overall, the influences, and **important hours**.

Important hours are not from a table: each window is anchored to a real exact
aspect that day, its width scales with that contact's strength (45-110
minutes), and it is typed `supportive` / `demanding` / `notable` from the
aspect's polarity. Because the Moon is what makes one hour differ from the
next, and the Moon scores low by design, the threshold for an hour is
deliberately low.

## 7. Periods and clusters

Monthly and annual forecasts group days into **key periods**:

1. every day gets the summed weight of the transits in orb that day,
2. the cutoff is `max(0.35, mean + 0.75 × standard deviation)` - **relative**
   to the period itself, so a month under three slow transits does not become
   one long cluster,
3. days above the cutoff are grouped, one-day gaps are bridged, runs shorter
   than two days are dropped,
4. each cluster reports its three strongest life areas and the factor ids
   behind them.

Deterministic by construction - the same month always produces the same
clusters.

## 8. Returns

A solar return is the instant the transiting Sun comes back to its **exact**
natal longitude, found by root search - never "the birthday at noon", which is
off by up to a day and would put the wrong Ascendant on the chart. The return
chart is then built with the ordinary chart primitive
(`ChartKind.SOLAR_RETURN`), optionally relocated. Lunar returns use the same
code path (~27.3 days apart, verified in tests).

## 9. Caching

| Layer | What | TTL |
| --- | --- | --- |
| Redis | transits (day/week/month/year), daily frequency, horoscopes, calendar, personal calendar | 6 h … 14 d |
| Redis | individual transits by id, so the detail endpoint never rescans | 3 d |
| Postgres `forecast_snapshots` | monthly and annual forecasts | until superseded |
| Postgres `charts` | natal and other charts | until superseded |

Every key contains `engine_version : orb_policy_version : scoring_version` and
the **chart fingerprint** (which includes the birth data). Consequences:

* editing birth data changes the fingerprint, so a stale reading can never be
  served - no invalidation sweep needed,
* changing a weight means bumping `SCORING_VERSION`, which retires every
  cached forecast at once.

## 10. Timezones

Date-only queries resolve in the **user's** timezone: "today" is their today,
and a day window is 23 or 25 hours across a DST transition (tested for
America/New_York, March and November 2026). Everything is stored and computed
in UTC; the local rendering metadata travels with the response.

## 11. Known limitations

* Quincunx and semisextile are not implemented (enum and orb table ready).
* Mean lunar nodes, not true nodes (~1.5° difference).
* Solar eclipse subtype is null by design (see above).
* Mundane aspects cover Mars and the outer planets only.
* An annual forecast takes seconds on a cold cache; it is cached for 14 days
  and persisted as a snapshot. The `ForecastJob` seam for moving it to a
  background worker arrives with B11.
* The reference chart values in the fixtures are this engine's own output and
  are marked `verified_independently: false` - comparing them against a second
  calculator is a pre-launch task.
