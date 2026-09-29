# Composite and Davison Charts (B5)

Two techniques that get confused constantly, and one arithmetic trap each.

| | Composite | Davison |
| --- | --- | --- |
| What it is | A chart of **midpoints** | A **real** chart |
| Did the sky look like this? | No - these positions never existed together | Yes, at the midpoint instant |
| Built from | Midpoint of each pair of planets | Midpoint in time + midpoint in place |
| Version tag | `midpoint_v1` | `davison_utc_geodesic_v1` |
| Chart kind | `ChartKind.COMPOSITE` | `ChartKind.DAVISON` |

---

## 1. Circular midpoints

359° and 1° meet at **0°**, not 180°. Naive averaging gets this wrong, and it
is wrong in a way that survives review because most pairs of planets are not
near the wrap.

```python
difference = signed_separation(second, first)   # short arc, (-180, 180]
midpoint    = normalize(first + difference / 2)
```

Test cases (all in `tests/fixtures/b5_reference_cases.json`, all checkable by
hand):

| A | B | Midpoint |
| --- | --- | --- |
| 359° | 1° | **0°** |
| 350° | 20° | 5° |
| 300° | 60° | 0° |
| 10° | 30° | 20° |
| 100° | 200° | 150° |

### Exactly opposite points

When two positions are exactly 180° apart there are **two** equally valid
midpoints and no principled way to prefer one. The engine picks the point 90°
ahead of the first position - deterministically, so the same input always gives
the same chart - and then **says so**: the point is listed in
`ambiguous_midpoints` and a warning explains why. Silently choosing one of two
answers and presenting it as *the* answer would be the wrong call.

## 2. Composite points

Midpoints are taken for the Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn,
Uranus, Neptune, Pluto and both nodes, plus the Ascendant and Midheaven.

Composite points have **no speed**: they are not bodies, nothing is moving, so
`speed_longitude` is 0 and nothing is ever reported as retrograde. Inventing a
motion for a midpoint would be fiction with a decimal point on it.

### Houses: `midpoint_mc_derived_v1`

Software genuinely differs here - some derive Placidus cusps from the composite
Midheaven and a mean latitude, others use equal houses from the composite
Ascendant. This engine takes the midpoint Ascendant and Midheaven and builds
equal houses from the Ascendant.

The method is **named in every response** (`house_method`), so a comparison
with another program is a conversation about conventions rather than a bug
report. If the product later needs to match a particular program's output, a
second method can be added alongside with its own version tag.

Aspects are then computed from the composite positions with the ordinary natal
aspect engine, and verified in tests against those same positions.

## 3. Davison: the time midpoint

Both births are converted to **UTC first**, then the instant exactly halfway
between them is taken.

Averaging local wall-clock times is wrong twice over: the two births usually
have different UTC offsets, and one of them may sit on a DST transition, so the
"average" can be a time that never existed. Example from the fixtures:

```
1992-05-14 14:30 Europe/Istanbul  →  1992-05-14 11:30 UTC
1994-08-21 09:45 Europe/London    →  1994-08-21 08:45 UTC
midpoint                          →  1993-07-02 22:07:30 UTC
```

A DST case is in the fixtures too: `2026-03-08 01:30 −05:00` and
`2026-03-08 04:30 −04:00` (either side of the US spring-forward) are
unambiguous once both are in UTC, and their midpoint is `07:30 UTC`.

## 4. Davison: the geographic midpoint

Averaging latitude and longitude puts the midpoint of 179°E and 179°W at 0°
longitude - in the Gulf of Guinea, about as far from the truth as the globe
allows. The engine converts both places to unit vectors, averages the vectors,
and converts back:

```
x = cos φ₁ cos λ₁ + cos φ₂ cos λ₂
y = cos φ₁ sin λ₁ + cos φ₂ sin λ₂
z = sin φ₁ + sin φ₂
latitude  = atan2(z, √(x² + y²))
longitude = atan2(y, x)
```

Tested cases: the date line (179°E / 179°W → 180°, not 0°), a plain equatorial
pair, a northern/southern pair that cancels to the equator, and a Tokyo/Hawaii
pair that must stay in the Pacific.

### Antipodal births

If the two places are (nearly) opposite points on the globe, every point on a
great circle is equidistant and there is **no** midpoint. The vector sum
collapses to zero, the engine detects it, falls back to a defined point and
raises an `antipodal_birthplaces` warning telling the reader the houses should
be treated with caution. It does not pretend to have an answer.

## 5. Davison is a real chart

Because the midpoint instant and place are real, the chart is cast with the
ordinary chart primitive: the planets really were at those degrees, the houses
are Placidus for that place, and the test verifies the positions directly
against the ephemeris at the midpoint instant. Timezone is not needed for the
maths - a UTC instant plus coordinates is sufficient - so it is left null and a
display zone can be derived later for presentation.

## 6. Storage

Composite and Davison charts are written to the `charts` table like any other
chart (`chart_kind` = `composite` / `davison`) and referenced from the report
as `derived_chart_id`. Planet positions are never duplicated across tables.

## 7. Known limitations

* One composite house method; others can be added with their own version tag.
* Composite aspects use natal orbs, which is the common convention but is not
  universal.
* No composite-to-natal or Davison-to-transit work yet (a later phase).
* The Davison chart's display timezone is not derived; the API returns the UTC
  instant and the coordinates.
