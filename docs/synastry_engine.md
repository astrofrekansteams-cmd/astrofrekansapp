# Synastry Engine (B5)

Two natal charts in, structured relationship factors out. Every score carries
the ids of the factors that produced it, so the app can show "the influences
behind this reading" and an expert can see why a number is what it is.

**What the score is not.** `overall_score` is an *astrological compatibility
index*: how much classical relationship symbolism the two charts contain. It is
not a probability, not a prediction, and not a ranking of people. The API says
so in `score_semantics` on every response, because a bare percentage next to
two names reads as a forecast, and this one is not.

Version: `synastry_score_v1`. Every weight lives in
`app/services/astrology/synastry_weights.py`.

---

## 1. What is computed

| Piece | Note |
| --- | --- |
| Inter-aspects | Every body of chart A against every body of chart B |
| Angle contacts | Each person's planets to the other's Ascendant and Midheaven |
| House overlays | **Directional**: A's planets in B's houses *and* B's planets in A's houses |
| Theme scores | Nine categories, each with its factor ids |

Bodies: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune,
Pluto, North Node, South Node.

### Directionality

Aspects are symmetric - if her Venus trines his Mars, his Mars trines her
Venus. House overlays are **not**: "her Venus in his 7th" and "his Venus in her
7th" are different statements about the relationship, and averaging them away
throws out what makes synastry worth reading. The API returns
`overlays_a_in_b` and `overlays_b_in_a` separately, and swapping the two people
swaps the two lists (tested).

### Generational pairs are excluded

Uranus, Neptune and Pluto move so slowly that everyone born within a few years
shares the same aspects between them. Uranus square Neptune says something
about a generation, not about a couple, so pairs where **both** bodies are
generational are skipped - as is node-to-node. A generational planet contacting
a *personal* planet still counts, because that is a real contact.

## 2. Orbs

| Aspect | Orb |
| --- | --- |
| Conjunction | 8° |
| Opposition | 7° |
| Trine | 6° |
| Square | 6° |
| Sextile | 4° |

Modifiers: +1° per luminary involved, +1° for an angle contact, −1° per lunar
node, floor 1°. Wider than transit orbs (an inter-aspect is a standing
condition, not a passing one), tighter than natal orbs for the minor pairs.

## 3. Aspect weight

```
weight = (1 − orb / orb_limit) × aspect_weight × pair_weight
```

| Aspect | Weight | | Selected pairs | Weight |
| --- | --- | --- | --- | --- |
| Conjunction | 1.00 | | Sun–Moon | 1.00 |
| Trine | 0.85 | | Venus–Mars | 0.95 |
| Opposition | 0.75 | | Moon–Moon | 0.90 |
| Square | 0.70 | | Moon–Venus | 0.80 |
| Sextile | 0.55 | | Saturn–Sun / Moon / Venus | 0.75 |
| | | | Mercury–Mercury | 0.70 |
| | | | North Node–Sun / Moon | 0.70 |
| | | | anything else | 0.35 |

Angle contacts use their own table: Ascendant 0.90, Midheaven 0.70, multiplied
by the planet's weight (Sun and Moon 1.00, Venus 0.95, Mars 0.85, …).

House overlays are scaled to 0.45 of an aspect's weight and combine the house
(7th 0.95, 5th 0.85, 1st and 8th 0.80, …) with the planet (Moon 1.00, Venus
0.95, Sun 0.90, …).

## 4. Themes

Nine categories: `general`, `emotional`, `communication`, `romance`,
`sexual_chemistry`, `trust`, `long_term`, `conflict`, `karmic`.

A pair contributes to the themes it symbolises: Venus–Mars to romance and
sexual chemistry, Mercury–Mercury to communication, Saturn–Moon to the long
term and the emotional, node contacts to the karmic. Overlays contribute
through the house: the 7th to long-term and general, the 8th to sexual
chemistry, trust and karmic, the 5th to romance.

Pairs outside the table are still returned as aspects - they are real contacts
and the client may want them - but they move no score. Letting every
Jupiter–Neptune contact feed "general" would saturate that theme for every
couple and destroy its discriminating power.

### Polarity depends on the theme

A square is not simply "bad". It is the charge. So the sign of a contribution
depends on which theme is being scored:

| Theme | Harmonious | Challenging | Conjunction |
| --- | --- | --- | --- |
| general | +1.0 | −0.7 | +0.8 |
| emotional | +1.0 | −0.6 | +0.9 |
| communication | +1.0 | −0.6 | +0.9 |
| romance | +1.0 | −0.4 | +1.0 |
| **sexual_chemistry** | +0.8 | **+0.7** | +1.0 |
| trust | +1.0 | −0.9 | +0.6 |
| long_term | +1.0 | −0.8 | +0.7 |
| **conflict** | −0.6 | **+1.0** | +0.4 |
| karmic | +0.8 | +0.6 | +1.0 |

## 5. Normalisation

```
score(theme) = 50 + 34 × tanh( Σ contributions / 2.6 ),  clamped to 10..95
```

`tanh` again: a couple with forty contacts cannot pin every theme to the
ceiling, and the ordering between themes survives.

The overall score is the weighted mean of the themes (general and long-term
1.2, emotional and romance 1.1, trust 1.0, communication 0.9, sexual chemistry
0.8, conflict 0.7, karmic 0.6) with **conflict inverted first** - a high
conflict index is not a high compatibility index, and letting it inflate the
average would be quietly dishonest.

Measured across 20 ordered pairs from five charts: overall 60-69, with the
discriminating themes spreading properly (emotional 49-75, romance 48-78,
long-term 62-82, trust 55-76).

## 6. Explainability

Every `ThemeScore` carries `positive_factors`, `challenging_factors` and
`factor_ids`; every id resolves to an entry in `aspects` or one of the overlay
lists (tested). `highlights` lists the strongest contacts in plain labels
(`a_moon trine b_moon`).

## 7. Reports and snapshots

Each run is stored in `compatibility_reports` with the fingerprint of both
people's birth data plus the engine and scoring versions. **Editing a saved
person later never rewrites an existing report** - the new input produces a new
fingerprint and a new report. That matters once a report has been read, paid
for, or shared with an expert.

Redis caches the result for a week under the same fingerprint.

## 8. Privacy and authorisation

A saved person is only ever resolved for the caller who owns it: guessing an id
returns 404, never someone else's birth data (tested). Reports are private to
their owner. Partner names, dates, times and places never reach the logs - only
ids.

## 9. Known limitations

* Ptolemaic aspects only; no quincunx, semisextile or minor aspects.
* No declination work (parallels and contraparallels).
* Composite and Davison have their own document:
  [`composite_davison.md`](composite_davison.md).
* The weights encode one reading of the tradition. They are configuration, and
  changing them means bumping `synastry_score_v1` - which retires every cached
  report rather than silently changing old numbers.
