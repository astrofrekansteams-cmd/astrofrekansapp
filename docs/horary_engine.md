# Horary Engine (B5)

Horary answers a question from the chart of the moment it was asked. It is the
one part of the product that has nothing to do with the user's birth data, and
the backend enforces that: the instant, the coordinates and the timezone are
captured with the question and never re-read from a profile afterwards.

**The engine does not judge the question.** There is no yes/no field anywhere
in the output. It produces the structured material a judgement is made from -
significators, dignities, receptions, perfection and obstruction factors, the
Moon's condition, the classical warnings - and the judgement belongs to the
astrologer (expert mode) or to Astro AI in phase B6, with proper framing. A
backend that returned "yes, you will get the job" would be making a claim
neither the astrology nor the product can stand behind.

---

## 1. Conventions and versions

Everything follows William Lilly, *Christian Astrology* (1647), the reference
text for modern traditional horary. Every rule is configuration, not scattered
code:

| Version tag | What it covers | Where |
| --- | --- | --- |
| `horary_rules_v1` | category→house map, orbs, radicality thresholds, search horizons | `app/services/astrology/horary_rules.py` |
| `dignity_rules_v1` | rulership, exaltation, triplicity, term, face, accidental dignity | `app/services/astrology/dignities.py` |
| `traditional_sign_based_v1` | the void-of-course definition | same |

Where practitioners genuinely disagree, the choice is named rather than
hidden - see the health house and void of course below.

## 2. The chart

`ChartKind.HORARY`, cast with the ordinary chart primitive for
`asked_at` + the asker's coordinates, Placidus houses.

Tested consequences:

* a question asked an hour later is a **different chart** (the Ascendant moves
  roughly a sign an hour),
* the same question from Tokyo and Istanbul has the **same planets** and
  **different houses**,
* editing the querent's birth profile changes **nothing**.

## 3. Rulership and significators

| Sign | Ruler | Sign | Ruler |
| --- | --- | --- | --- |
| Aries | Mars | Libra | Venus |
| Taurus | Venus | Scorpio | Mars |
| Gemini | Mercury | Sagittarius | Jupiter |
| Cancer | Moon | Capricorn | Saturn |
| Leo | Sun | Aquarius | Saturn |
| Virgo | Mercury | Pisces | Jupiter |

* **Querent** = ruler of the 1st house cusp sign. The **Moon** is always the
  co-significator.
* **Quesited** = ruler of the house of the matter.

Uranus, Neptune and Pluto appear in the chart but are **never significators**.
The classical scheme gives them no rulership, and inventing one would change
the judgement. This is enforced in code and tested.

## 4. Question houses

`horary_rules_v1` maps a category to a house; an astrologer can always
override it, and the override wins.

| Category | House | Category | House |
| --- | --- | --- | --- |
| relationship, marriage, legal | 7 | children, pregnancy, love | 5 |
| career, job, business | 10 | home, property, family | 4 |
| money, personal finance, lost object | 2 | debt | 8 |
| health, illness | 6 | education, long travel, spiritual | 9 |
| short travel | 3 | friend | 11 |
| enemy | 12 | general | 1 |

Two are conventions rather than universals, and both ship their alternative in
`alternative_quesited_houses`:

* **health** → the 6th (the illness). Lilly judges the querent's body from the
  1st and the disease from the 6th; the 1st is offered as the alternative.
* **lost object** → the 2nd (moveable goods of the querent), with the 4th as
  the alternative for objects in the home.

### Derived (turned) houses

`derive_house(base, offset)` counts the Nth house *from* another house, with
the house itself as the first: the partner's money is `derive_house(7, 2) = 8`,
the partner's career `derive_house(7, 10) = 4`, a child's partner
`derive_house(5, 7) = 11`. Deterministic, wraps around the wheel, and tested.

## 5. Essential dignity (`dignity_rules_v1`)

| Dignity | Source | Score |
| --- | --- | --- |
| Domicile | Ptolemy / Lilly | +5 |
| Exaltation | Ptolemy / Lilly (with degree) | +4 |
| Triplicity | **Dorothean** day/night rulers, as Lilly uses them | +3 |
| Term | **Egyptian** terms, Lilly's table | +2 |
| Face | **Chaldean** decans, Lilly's table | +1 |
| Detriment | opposite the domicile | −5 |
| Fall | opposite the exaltation | −4 |
| Peregrine | no essential dignity at all | −5 |

These tables are tested against the published values recorded in
`tests/fixtures/b5_reference_cases.json`, not against our own output.

## 6. Accidental dignity

| Factor | Convention |
| --- | --- |
| Angular / succedent / cadent | houses 1,4,7,10 / 2,5,8,11 / 3,6,9,12 |
| Cazimi | within 17′ of the Sun - a *strengthening* condition |
| Combust | within 8°30′ of the Sun |
| Under the beams | within 17° of the Sun and not combust |
| Retrograde / direct / stationary | measured from the longitude speed; "stationary" is under 5% of mean motion |
| Swift / slow | speed compared with the body's mean daily motion |

## 7. Reception

Reception is recorded per dignity (`domicile`, `exaltation`, `triplicity`,
`term`, `face`) with a direction: "Jupiter receives Venus by triplicity". When
each significator receives the other, **both entries are marked `mutual`** -
and mutual reception is reported as a perfection factor in its own right,
because traditionally it can bring a matter about without an aspect.

## 8. Perfection and obstruction

Implemented and tested:

| Factor | Definition used |
| --- | --- |
| `direct_perfection` | An applying Ptolemaic aspect between the significators that perfects **before either changes sign** |
| `translation_of_light` | A faster planet separating from one significator and applying to the other |
| `collection_of_light` | A slower planet both significators apply to |
| `mutual_reception` | Each receives the other by an essential dignity |
| `prohibition` | A third planet perfects with a significator **before** the significators perfect |
| `refranation` | A significator stations before the aspect perfects |
| `no_perfection_found` | Nothing above applies - reported explicitly, never left as silence |
| `significator_combust` | A significator within 8°30′ of the Sun |

**Deliberately not implemented**, and declared in every response under
`not_implemented`: `frustration`, `besiegement`, `abscission_of_light`. The
definitions vary between authors, and a technique reported as absent when the
engine simply cannot see it would be a lie by omission.

Aspect orbs use **Lilly's moieties** (half-orbs summed per pair): Sun 7.5°,
Moon 6°, Mercury 3.5°, Venus 4°, Mars 3.75°, Jupiter and Saturn 4.5°. The
perfection search runs 30 days ahead, and both bodies move during it - a
fixed-target search would mis-time contacts and mis-call void of course.

## 9. The Moon

Reported: sign, degree, house, speed, phase, last aspect, next aspect, the
instant it leaves its sign, and whether it is in the via combusta (15 Libra to
15 Scorpio).

**Void of course** uses `traditional_sign_based_v1`: *the Moon makes no further
Ptolemaic aspect to a classical planet before it leaves its current sign.* The
alternative "no aspect within orb" definition gives different answers and is
not used. The test does not trust the engine's bookkeeping - it walks the Moon
forward in half-hour steps and re-derives the claim from the positions.

## 10. Radicality - warnings, never refusals

Lilly's considerations before judgement are reported as structured warnings and
the analysis is always returned in full:

`early_ascendant` (first 3°), `late_ascendant` (past 27°), `saturn_in_seventh`,
`void_of_course_moon`, `moon_via_combusta`, `significator_combust`,
`significators_identical`, `question_repeat_suspected`.

The system never blocks a question. Re-asking is allowed and flagged, so the
astrologer can follow the tradition of judging from the original chart if they
choose - a decision for a person, not for a database constraint.

## 11. Storage and privacy

`horary_questions` holds the question, its instant and its place;
`horary_analyses` holds the structured result with its version tags; the chart
itself lives in `charts` like every other chart. Analyses are **snapshots**: a
stored analysis is returned as it was produced, because re-running a newer
engine over an old question would change an answer the user has already read.
`?refresh=true` recomputes explicitly.

Questions are private to their owner - another account gets 404, not a
redacted record. The question text, the coordinates and the birth-adjacent
fields never reach the logs.

## 12. Performance

Cold analysis ≈ 1.2 s (Docker), warm ≈ 15 ms from the stored snapshot. The cost
is the forward search for perfections, which samples both bodies; it is paid
once per question.

## 13. Known limitations

* Frustration, besiegement and abscission are not detected (declared).
* Antiscia, fixed stars, Arabic parts and profections are not implemented.
* Planetary hours and the Part of Fortune are not yet computed.
* Only the seven classical planets act as significators - intentionally.
* The engine offers no judgement, by design; that is B6 and the expert panel.
