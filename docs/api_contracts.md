# API Contracts (v1)

Base URL: `{API_BASE_URL}/api/v1`. Machine-readable schema:
`GET /api/v1/openapi.json` (41 paths, 46 operations, 108 schemas), browsable at `/docs`
outside production.

These contracts are written to match the Flutter client's existing models
(`lib/core/astrology/domain/*`), so phase B10 replaces
`MockAstrologyService` with `ApiAstrologyService` without touching any widget.

---

## Conventions

| Rule | Detail |
| --- | --- |
| Time | Every instant is UTC ISO-8601 (`1992-05-14T11:30:00Z`). Birth data also carries `timezone` (IANA) and `utc_offset_hours`. |
| Enums | `snake_case` strings: `north_node`, `whole_sign`, `waxing_gibbous`, `harmonious`. |
| Angles | Longitudes in degrees `0-360`; `degree` (0-29) and `minute` (0-59) are the split inside the sign. |
| Auth | `Authorization: Bearer <access_token>` on everything except `/health`, `/ready` and the `/auth/*` entry points. |
| Tracing | Send `X-Request-Id` to correlate; it is echoed on every response. |
| Errors | Always the envelope below. |

### Error envelope

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect.",
    "details": {}
  }
}
```

| Code | Status | Meaning |
| --- | --- | --- |
| `validation_error` | 422 | Body failed validation; `details.fields[]` lists `loc`, `type`, `message` |
| `unauthenticated` | 401 | Missing or invalid access token |
| `invalid_credentials` | 401 | Wrong email or password |
| `token_expired` / `token_reused` / `token_unknown` / `token_used` | 401 | Refresh or reset token problems; `token_reused` means the session family was revoked |
| `forbidden` / `premium_required` | 403 | Feature needs a premium subscription |
| `not_found` | 404 | Unknown resource |
| `email_in_use` | 409 | Registration conflict |
| `rate_limited` | 429 | `details.limit`, `details.window_seconds` |
| `birth_profile_missing` / `missing_birth_data` | 422 | Chart or forecast requested before birth data exists |
| `astrology_error` | 422 | Chart could not be computed |
| `upstream_error` | 502 | Geocoding or another dependency failed |
| `internal_error` | 500 | Unexpected; details are never leaked |

---

## Auth

### `POST /auth/register` → 201

```json
{
  "email": "nova@example.com",
  "password": "Str0ngPassphrase!",
  "name": "Nova",
  "language": "tr",
  "timezone": "Europe/Istanbul",
  "birth_date": "1992-05-14",
  "birth_time": "14:30:00",
  "birth_place": "Istanbul",
  "house_system": "placidus"
}
```

Birth fields are optional; when `birth_place` is present it is geocoded and the
timezone derived from the coordinates. Password: 8-128 characters, no leading
or trailing whitespace. Rate limit 5/minute.

Response (also returned by `/auth/login` and `/auth/refresh`):

```json
{
  "access_token": "eyJ…",
  "refresh_token": "eyJ…",
  "token_type": "Bearer",
  "expires_at": "2026-09-23T10:15:00Z",
  "refresh_expires_at": "2026-10-23T10:00:00Z"
}
```

### Other auth routes

| Route | Body | Notes |
| --- | --- | --- |
| `POST /auth/login` | `email`, `password` | 10/minute |
| `POST /auth/refresh` | `refresh_token` | **Rotates**: the old token dies. Store the new one. Replaying an old token returns `token_reused` and kills every session in that family - the client must sign the user out. |
| `POST /auth/logout` | `refresh_token` | Idempotent |
| `POST /auth/logout-all` | – | Bearer required |
| `POST /auth/forgot-password` | `email` | Always the same message |
| `POST /auth/reset-password` | `token`, `new_password` | Single use |
| `POST /auth/change-password` | `current_password`, `new_password` | Revokes all sessions |
| `GET /auth/me` | – | Same shape as `/users/me` |

---

## User and birth data

### `GET /users/me` · `PATCH /users/me`

```json
{
  "id": "0b9c…",
  "email": "nova@example.com",
  "name": "Nova",
  "avatar_url": null,
  "language": "tr",
  "timezone": "Europe/Istanbul",
  "subscription_tier": "free",
  "is_email_verified": false,
  "created_at": "2026-09-23T09:12:44Z"
}
```

`PATCH` accepts `name`, `avatar_url`, `language`, `timezone`.
`DELETE /users/me` soft-deletes the account and revokes every session.

### `PUT /birth-profiles/me` · `GET /birth-profiles/me`

```json
{
  "birth_date": "1992-05-14",
  "birth_time": "14:30:00",
  "birth_place": "Istanbul",
  "latitude": 41.0082,
  "longitude": 28.9784,
  "timezone": "Europe/Istanbul",
  "house_system": "placidus",
  "label": null
}
```

Coordinates win over the place name; a missing timezone is derived from the
coordinates. Response adds `id`, `birth_time_known`, `is_primary`,
`utc_offset_hours`, `can_compute_houses`, `updated_at`.

`can_compute_houses` is the flag the UI needs: `false` means the chart comes
back without houses or angles.

### `GET|POST /saved-people`, `DELETE /saved-people/{id}`

Same birth fields plus `name`, `relation`
(`partner|spouse|friend|family|other`) and `note`.

### `GET /geocode?query=Istanbul&limit=5`

```json
{
  "query": "Istanbul",
  "results": [
    {
      "display_name": "İstanbul, Türkiye",
      "latitude": 41.0082,
      "longitude": 28.9784,
      "timezone": "Europe/Istanbul",
      "country_code": "TR",
      "provider": "mock",
      "confidence": 1.0
    }
  ]
}
```

---

## Astrology

### `GET /astrology/natal-chart/me`

Query: `house_system` (`placidus|koch|whole_sign|equal`), `refresh` (bool).

Every chart response carries `kind` and `subject` (the instant and place it was
cast for) alongside `birth_data`. For a natal chart `kind` is `natal` and
`birth_data` is present; for horary, return and event charts (phase B5)
`birth_data` is `null` and `subject.moment_utc` is the moment that matters.
`house_rulers` maps each house number to its traditional ruling planet.
`POST /astrology/natal-chart` takes the same birth fields as a birth profile
and returns the identical shape for any third party.

```json
{
  "engine": "skyfield",
  "engine_version": "1.0.0-de421",
  "computed_at": "2026-09-23T09:14:02Z",
  "house_system": "placidus",
  "requested_house_system": "placidus",
  "birth_data": {
    "birth_date": "1992-05-14",
    "birth_time": "14:30:00",
    "time_known": true,
    "place": "İstanbul, Türkiye",
    "latitude": 41.0082,
    "longitude": 28.9784,
    "timezone": "Europe/Istanbul",
    "utc_datetime": "1992-05-14T11:30:00Z",
    "utc_offset_hours": 3.0
  },
  "planets": [
    {
      "planet": "sun",
      "sign": "taurus",
      "longitude": 53.932,
      "latitude": 0.0,
      "degree": 23,
      "minute": 55,
      "speed_longitude": 0.9663,
      "retrograde": false,
      "house": 9
    }
  ],
  "houses": [
    {"number": 1, "sign": "virgo", "cusp_longitude": 167.3, "degree": 17, "minute": 18}
  ],
  "angles": {
    "ascendant": 167.3, "descendant": 347.3, "midheaven": 75.2, "imum_coeli": 255.2,
    "ascendant_sign": "virgo", "descendant_sign": "pisces",
    "midheaven_sign": "gemini", "imum_coeli_sign": "sagittarius"
  },
  "aspects": [
    {"first": "mercury", "second": "jupiter", "aspect": "trine",
     "nature": "harmonious", "orb": 0.72, "applying": false}
  ],
  "elements": {"fire": 1, "earth": 6, "air": 2, "water": 1},
  "modalities": {"cardinal": 3, "fixed": 4, "mutable": 3},
  "dominant_element": "earth",
  "dominant_modality": "fixed",
  "dominant_planet": "venus",
  "big_three": {"sun": "taurus", "moon": "libra", "ascendant": "virgo"},
  "warnings": []
}
```

`planets` always has 12 entries (10 bodies + both nodes). `houses` has 12 or is
empty. Element and modality counts sum to 10 (nodes excluded).

**`warnings`** is how the client learns something is degraded, instead of
guessing:

| Warning prefix | Meaning |
| --- | --- |
| `birth_time_unknown` | No houses or angles; the Moon may be off by up to 13° |
| `birth_location_unknown` | No houses or angles |
| `house_system_fallback` | Requested system undefined at this latitude; `house_system` says what was used |

### `GET /astrology/positions?moment=`

`{"moment": "...", "positions": [ …same planet objects… ]}` — `house` is
`null`, since positions alone have no chart.

### `GET /astrology/moon-phase?moment=`

```json
{
  "moment": "2026-09-22T22:15:44Z",
  "phase": "waxing_gibbous",
  "illumination": 0.8527,
  "age_days": 11.062,
  "elongation": 134.8546,
  "sign": "aquarius",
  "next_phase": "full_moon",
  "next_phase_at": "2026-09-26T16:49:02Z"
}
```

---

## Transits

### `GET /astrology/transits`

Query: `date` (defaults to today **in the user's timezone**), `range`
(`day` | `tomorrow` | `week` | `month` | `year`), `include_minor`, `refresh`.

```json
{
  "start_at": "2026-09-22T21:00:00Z",
  "end_at": "2026-09-23T21:00:00Z",
  "reference": "2026-09-23T09:12:00Z",
  "timezone": "Europe/Istanbul",
  "range": "day",
  "active": [
    {
      "id": "f02572387e27223505c7b133",
      "transiting_body": "jupiter",
      "target_type": "natal_planet",
      "target_body": "saturn",
      "target_angle": null,
      "target_house": 9,
      "aspect_type": "opposition",
      "nature": "challenging",
      "orb": 0.12,
      "maximum_orb": 3.3,
      "applying": true,
      "start_at": "2026-09-05T04:12:00Z",
      "exact_at": "2026-09-24T02:40:20Z",
      "end_at": "2026-10-14T18:55:00Z",
      "status": "approaching",
      "strength": 56,
      "passes": [
        {"pass_number": 1, "exact_at": "2026-09-24T02:40:20Z",
         "direction": "direct", "speed": 0.0813}
      ],
      "affected_houses": [3, 9],
      "window_clipped": false,
      "engine_version": "1.0.0-de421",
      "scoring_version": "b4.scoring.v1",
      "metadata": {"transiting_house": 3, "pass_count": 1, "peak_orb": 0.0}
    }
  ],
  "approaching": [],
  "upcoming": [],
  "ingresses": [
    {
      "id": "5c1d",
      "planet": "moon",
      "from_house": 5,
      "to_house": 6,
      "entered_at": "2026-09-23T04:11:00Z",
      "estimated_exit_at": "2026-09-25T10:02:00Z",
      "retrograde": false,
      "re_entry": false
    }
  ],
  "engine_version": "1.0.0-de421",
  "scoring_version": "b4.scoring.v1",
  "cached": false
}
```

What the client needs to know:

* **`passes` can hold up to three entries.** A retrograding planet perfects the
  same aspect several times; that is one transit with several beats, not three
  transits. `exact_at` is the pass nearest the reference instant.
* `exact_at` is `null` when an aspect enters orb but never perfects.
* `status`: `approaching` | `exact` (within 12 h of a pass) | `separating`.
* `strength` (0-100) is the transit's **peak** relevance inside the requested
  window, not its orb at one sampling instant.
* `window_clipped: true` means the window runs past the engine's search horizon
  (slow outer planets), so `start_at` / `end_at` are bounds, not real edges.

### `GET /astrology/transits/{id}`

One transit, same object. Ids are stable for a chart and window, so a transit
card can deep-link into its detail screen.

---

## Daily frequency

### `GET /astrology/daily-frequency`

```json
{
  "date": "2026-09-23T00:00:00+03:00",
  "timezone": "Europe/Istanbul",
  "overall": 36,
  "scores": {
    "love": {"area": "love", "score": 40, "trend": "falling",
             "strength": 44, "factor_ids": ["f025", "moon_house_6"]}
  },
  "important_hours": [
    {"start": "2026-09-23T04:38:00Z", "end": "2026-09-23T05:35:00Z",
     "type": "supportive", "strength": 19,
     "reason": "moon conjunction saturn", "factor_ids": ["a91c"]}
  ],
  "influences": [
    {"id": "f025", "kind": "transit", "label": "jupiter opposition saturn",
     "contribution": -0.58, "areas": ["career", "money"],
     "at": "2026-09-24T02:40:20Z", "detail": {"orb": 0.12, "strength": 56}}
  ],
  "message_context": {"moon_house": 6, "moon_sign": "aquarius",
                      "active_transits": 15},
  "engine_version": "1.0.0-de421",
  "scoring_version": "daily_frequency_v1",
  "cached": false
}
```

Areas: `general_energy`, `love`, `relationships`, `career`, `money`,
`health_balance`, `personal_growth`, `luck`, `mood`. `trend` is
`rising` | `steady` | `falling`.

**Every score lists `factor_ids`**, and every id resolves to an entry in
`influences` or to a transit id from `/astrology/transits`. That is what the
"Bu yorumu oluşturan etkiler" section renders: the scores are never a black
box.

Important hours are anchored to real exact aspect times, their width scales
with the contact's strength, and `type` is `supportive` | `demanding` |
`notable`.

---

## Cosmic calendar

### `GET /calendar/events`

Query: `start`, `end` (dates, resolved in the user's timezone), `refresh`.

```json
{
  "start_at": "2026-02-01T00:00:00Z",
  "end_at": "2026-03-31T00:00:00Z",
  "timezone": "Europe/Istanbul",
  "events": [
    {"id": "b71", "type": "full_moon", "exact_at": "2026-03-03T11:32:00Z",
     "planet": "moon", "sign": "virgo", "longitude": 342.8, "degree": 12},
    {"id": "c02", "type": "lunar_eclipse", "exact_at": "2026-03-03T11:32:00Z",
     "planet": "moon", "sign": "virgo", "eclipse_subtype": "total",
     "eclipse_magnitude": 1.15, "node_distance": 3.98},
    {"id": "d13", "type": "station_retrograde",
     "exact_at": "2026-02-26T09:44:00Z", "planet": "mercury", "sign": "pisces"}
  ],
  "engine_version": "1.0.0-de421",
  "cached": false
}
```

Types: `new_moon`, `full_moon`, `first_quarter`, `last_quarter`,
`station_retrograde`, `station_direct`, `solar_eclipse`, `lunar_eclipse`,
`ingress`, `conjunction`, `opposition`, `square`, `trine`, `sextile`.

**`eclipse_subtype` is `null` for solar eclipses by design**: total vs annular
depends on Besselian elements the engine does not compute, and a wrong label is
worse than none. Lunar subtypes (`total` / `partial` / `penumbral`) come from
the shadow geometry and match the published catalogue.

Retrograde windows arrive as `station_retrograde` events carrying `start_at`,
`end_at` and `metadata.days`.

### `GET /calendar/personal`

The same events, seen through the chart:

```json
{
  "events": [
    {
      "event": {"id": "c02", "type": "lunar_eclipse", "exact_at": "..."},
      "affected_house": 7,
      "natal_aspects": [
        {"target_body": "venus", "target_angle": null,
         "aspect": "conjunction", "orb": 1.8}
      ],
      "strength": 92,
      "personal_relevance": "house_7|conjunction_natal_venus",
      "source_factors": ["c02"]
    }
  ]
}
```

---

## Horoscopes and forecasts

| Route | Query | Returns |
| --- | --- | --- |
| `GET /horoscope/daily` | `date`, `refresh` | `HoroscopeResponse`, period `daily` |
| `GET /horoscope/weekly` | `date`, `refresh` | `HoroscopeResponse`, period `weekly` |
| `GET /forecasts/monthly` | `year`, `month`, `refresh` | `MonthlyForecastResponse` |
| `GET /forecasts/yearly` | `year`, `refresh` | `AnnualForecastResponse` |

`HoroscopeResponse` carries `overall_score`, `areas[]` (the nine areas, each
with `factor_ids`), `important_dates[]`, `important_hours[]` (daily only),
`opportunities[]`, `challenges[]`, `major_transits[]`, `moon_events[]`,
`house_activations[]`, `key_periods[]` and `source_factors[]`.

`MonthlyForecastResponse` adds `general_theme[]`, `retrogrades[]` and
`personal_events[]`. `key_periods` are the month's busy stretches, found by
clustering its transits; each names its areas, strength and sources:

```json
{"start_at": "2026-10-12T00:00:00Z", "end_at": "2026-10-19T23:59:59Z",
 "areas": ["personal_growth", "health_balance", "mood"],
 "strength": 65, "label": "personal_growth_health_balance",
 "source_factors": ["a1", "b2"]}
```

`AnnualForecastResponse` is the data layer for the premium yearly report:
`major_transits[]`, `retrograde_periods[]`, `eclipses[]`, `jupiter_movements[]`,
`saturn_movements[]`, `outer_planet_hits[]`, `house_activations[]`,
`key_periods[]`, `important_dates[]`, and `solar_return`:

```json
{"year": 2026, "exact_at": "2026-05-14T17:04:00Z", "ascendant": 212.4,
 "ascendant_sign": "scorpio", "sun_house": 7}
```

All four are **structured data only**, no prose. Astro AI writes the text from
these numbers in phase B6; an expert reads the same numbers in their panel.

Every response carries `cached`, `engine_version` and `scoring_version`. A
forecast is recomputed when the birth data changes (the cache key contains the
chart fingerprint) or when a version is bumped.

---

## Horary

A horary chart is cast for the moment and place the **question** was asked. It
has nothing to do with the querent's birth data, and editing a birth profile
never changes one.

**No verdict is returned.** There is no yes/no field anywhere in the response
by design: the engine reports what the chart contains and the judgement
belongs to the astrologer, or to Astro AI in phase B6 with proper framing.

### `POST /horary/questions` → 201

```json
{
  "question": "Will the contract be signed?",
  "category": "career",
  "latitude": 41.0082,
  "longitude": 28.9784,
  "location_name": "Istanbul",
  "asked_at": "2026-09-23T11:00:00Z",
  "timezone": "Europe/Istanbul",
  "house_override": null
}
```

`asked_at` defaults to now (that is what horary means); `timezone` is derived
from the coordinates when omitted. Coordinates are **required** - without a
place there is no horizon and no houses. Rate limit 30/hour.

```json
{
  "id": "1c6b62df-…",
  "question": "Will the contract be signed?",
  "category": "career",
  "status": "created",
  "asked_at_utc": "2026-09-23T11:00:00Z",
  "timezone": "Europe/Istanbul",
  "latitude": 41.0082,
  "longitude": 28.9784,
  "location_name": "Istanbul",
  "house_override": null,
  "chart_id": null,
  "duplicate_suspected": false,
  "created_at": "2026-09-23T11:00:01Z"
}
```

`duplicate_suspected` is a **hint, never a block**: re-asking is always
allowed, and traditionally a repeated question is judged from the original
chart - which is a decision for a person, not a database constraint.

Status moves `created → calculated → ready`, or `failed`.

### `POST /horary/questions/{id}/calculate`

Casts (or reuses) the chart and returns the question with its `chart_id`.

### `GET /horary/questions/{id}/analysis`

Query: `refresh`. The structured material a judgement is built from:

```json
{
  "question_id": "1c6b62df-…",
  "querent_house": 1,
  "quesited_house": 10,
  "alternative_quesited_houses": [],
  "querent": {
    "role": "querent", "house": 1, "sign": "leo", "planet": "sun",
    "longitude": 180.44, "speed": 0.9829, "retrograde": false, "in_house": 1,
    "essential": {
      "planet": "sun", "sign": "libra", "degree": 0.44,
      "dignities": [], "debilities": ["fall", "peregrine"],
      "triplicity_ruler": "saturn", "term_ruler": "saturn",
      "face_ruler": "moon", "peregrine": true, "score": -9
    },
    "accidental": {
      "planet": "sun", "house": 1, "placement": "angular", "motion": "direct",
      "speed": 0.9829, "speed_ratio": 0.9973,
      "solar_condition": "free", "solar_distance": 0.0, "notes": []
    }
  },
  "quesited": { "role": "quesited", "house": 10, "planet": "venus" },
  "co_significator": { "role": "co_significator", "planet": "moon" },
  "moon": {
    "sign": "aquarius", "degree": 21.4, "house": 6, "speed": 12.4,
    "phase": "waning_gibbous",
    "void_of_course": false,
    "void_definition": "traditional_sign_based_v1",
    "last_aspect": { "aspect": "trine", "second": "mercury", "exact_at": "…" },
    "next_aspect": { "aspect": "square", "second": "mars", "exact_at": "…" },
    "leaves_sign_at": "2026-09-24T02:11:00Z",
    "in_via_combusta": false
  },
  "house_rulers": {"1": "sun", "2": "mercury", "…": "…"},
  "receptions": [
    {"id": "…", "from_planet": "venus", "to_planet": "sun",
     "kind": "triplicity", "mutual": false, "strength": 3}
  ],
  "applying_aspects": [
    {"id": "…", "first": "sun", "second": "venus", "aspect": "conjunction",
     "orb": 4.1, "max_orb": 11.5, "applying": true,
     "exact_at": "2026-10-02T14:10:00Z",
     "perfects_before_sign_change": true, "days_to_exact": 9.13}
  ],
  "separating_aspects": [],
  "perfection_factors": [
    {"id": "…", "kind": "direct_perfection", "planets": ["sun", "venus"],
     "aspect": "conjunction", "exact_at": "…", "days_to_exact": 9.13}
  ],
  "obstruction_factors": [
    {"id": "…", "kind": "prohibition", "planets": ["mercury", "venus"],
     "detail": {"prohibitor": "mercury", "exact_at": "…"}}
  ],
  "dignity_factors": [],
  "warnings": [
    {"code": "void_of_course_moon", "message": "…", "detail": {}}
  ],
  "source_factors": ["…"],
  "is_day_chart": true,
  "not_implemented": ["frustration", "besiegement", "abscission_of_light"],
  "confidence_metadata": {
    "perfection_count": 1, "obstruction_count": 1, "warning_count": 0,
    "moon_void_of_course": false,
    "note": "Structured factors only. This engine does not judge the question."
  },
  "engine_version": "1.0.0-de421",
  "rules_version": "horary_rules_v1",
  "dignity_version": "dignity_rules_v1",
  "cached": false
}
```

Things the client should rely on:

* **`not_implemented`** lists the classical techniques the engine does not
  detect (frustration, besiegement, abscission). Silence about a technique is
  never evidence that it is absent.
* `perfection_factors` kinds: `direct_perfection`, `translation_of_light`,
  `collection_of_light`, `mutual_reception`. `obstruction_factors` kinds:
  `prohibition`, `refranation`, `separating_significators`,
  `significator_combust`, `no_perfection_found`.
* Significators are only ever the seven classical planets - Uranus, Neptune
  and Pluto are in the chart but never rule a house.
* `void_definition` names which void-of-course convention was used.
* Warnings (`early_ascendant`, `late_ascendant`, `saturn_in_seventh`,
  `void_of_course_moon`, `moon_via_combusta`, `significator_combust`,
  `significators_identical`, `question_repeat_suspected`) never suppress the
  analysis.

Analyses are **snapshots**: a stored analysis is returned as produced, so a
newer engine cannot rewrite an answer the user already read. `?refresh=true`
recomputes deliberately.

`GET /horary/questions` lists your questions; questions and analyses are
private to their owner (another account gets 404).

---

## Compatibility

### Identifying the two people

Every compatibility request takes two `PersonRef`s, each of **exactly one**
form:

```json
{"me": true}
{"saved_person_id": "…"}
{"birth_date": "1988-11-02", "birth_time": "03:15:00",
 "birth_place": "Berlin", "label": "Inline person"}
```

A saved person is only ever resolved for the caller who owns it: guessing an
id returns 404, never someone else's birth data.

### `POST /compatibility/synastry`

```json
{
  "report_id": "…",
  "kind": "synastry",
  "overall_score": 67,
  "score_semantics": "astrological compatibility index: how much classical relationship symbolism these two charts contain. Not a probability, not a prediction, and not comparable between different scoring versions.",
  "themes": [
    {"theme": "romance", "score": 68, "strength": 53,
     "positive_factors": ["…"], "challenging_factors": ["…"],
     "factor_ids": ["…"]}
  ],
  "aspects": [
    {"id": "…", "person_a_body": "moon", "person_b_body": "moon",
     "aspect": "trine", "nature": "harmonious", "orb": 1.2, "max_orb": 8.0,
     "weight": 0.76, "themes": ["emotional", "trust"],
     "label": "a_moon trine b_moon"}
  ],
  "overlays_a_in_b": [
    {"id": "…", "direction": "a_to_b", "planet": "venus", "house": 8,
     "longitude": 215.4, "weight": 0.34,
     "themes": ["sexual_chemistry", "trust", "karmic"],
     "label": "a_venus in b_house_8"}
  ],
  "overlays_b_in_a": [],
  "highlights": ["a_moon trine b_moon", "a_mars opposition b_asc"],
  "source_factors": ["…"],
  "warnings": [],
  "engine_version": "1.0.0-de421",
  "scoring_version": "synastry_score_v1",
  "cached": false
}
```

* **`score_semantics` is part of the contract.** The number is an
  astrological factor index, not a probability, and the UI must not present it
  as a forecast.
* Nine themes: `general`, `emotional`, `communication`, `romance`,
  `sexual_chemistry`, `trust`, `long_term`, `conflict`, `karmic`.
* **Overlays are directional.** `overlays_a_in_b` and `overlays_b_in_a` are
  different statements about the relationship; aspects are symmetric, overlays
  are not.
* Every `factor_ids` entry resolves to an `aspects` or overlay id, so "the
  influences behind this reading" is data rather than a guess.
* Uranus/Neptune/Pluto **to each other** are omitted: everyone born in the
  same few years shares them, so they describe a generation, not a couple.

### `POST /compatibility/composite`

A chart of **midpoints** - positions that never existed together in the sky.

```json
{
  "kind": "composite",
  "method": "midpoint_v1",
  "house_method": "midpoint_mc_derived_v1",
  "chart": { "…a full chart object, kind = composite…" },
  "aspects": [{"first": "sun", "second": "moon", "aspect": "square", "orb": 1.4, "nature": "challenging"}],
  "elements": {"fire": 2, "earth": 4, "air": 2, "water": 2},
  "modalities": {"cardinal": 4, "fixed": 3, "mutable": 3},
  "dominant_element": "earth",
  "ambiguous_midpoints": [],
  "warnings": []
}
```

Midpoints are taken along the short arc, so 359° and 1° meet at 0°. Points
that are **exactly opposite** have two equally valid midpoints: one is chosen
deterministically, listed in `ambiguous_midpoints`, and explained in
`warnings`. Composite points carry no speed and are never retrograde - they
are not bodies.

`house_method` is named because astrology software genuinely differs here.

### `POST /compatibility/davison`

A **real** chart for the midpoint in time and place.

```json
{
  "kind": "davison",
  "method": "davison_utc_geodesic_v1",
  "midpoint_utc": "1993-07-02T22:07:30Z",
  "midpoint_latitude": 47.1814,
  "midpoint_longitude": 15.853,
  "chart": { "…a full chart object, kind = davison…" },
  "warnings": []
}
```

The time midpoint is taken **in UTC** (never by averaging local wall clocks,
which breaks across offsets and DST) and the place midpoint on the sphere
(never by averaging coordinates, which puts 179°E and 179°W in Africa).
Antipodal birthplaces have no midpoint; that case returns an
`antipodal_birthplaces` warning instead of a fabricated answer.

### `GET /compatibility/reports` · `GET /compatibility/reports/{id}`

Stored results, newest first, filterable by `kind`. A report is a
**snapshot**: it records the fingerprint of both people's birth data plus the
engine and scoring versions, so editing a saved person later produces a *new*
report instead of rewriting one the user has already read. Reports are private
to their owner.

---

## Catalogue

### `GET /services`

Everything the platform can deliver and how. Filters: `category`,
`fulfillment_mode` (`automated` / `expert` / `hybrid`), `include_inactive`.

```json
{
  "code": "horary_question",
  "name": "Horary Question",
  "category": "horary",
  "fulfillment_modes": ["automated", "expert"],
  "estimated_duration_minutes": 30,
  "requires_birth_data": false,
  "requires_question": true,
  "requires_partner_data": false,
  "supports_chat": true,
  "supports_voice": true,
  "supports_video": true,
  "supports_appointment": true,
  "supports_automated_report": true,
  "requires_premium": false,
  "active": true
}
```

The `requires_*` flags tell the client what to collect before an order can be
created; `fulfillment_modes` tells it whether to offer "instant analysis", "book
an astrologer", or both. `GET /services/{code}` returns one.

---

## Astro AI

Every route needs a bearer token. When the server has no provider key, all of
them answer `503 ai_not_configured` while the rest of the API keeps working -
check `GET /ai/status` before offering the feature.

**The engine computes, the AI explains.** No response here contains an
astrological fact the engine did not produce, and every specific statement
carries the `factor_id`s it rests on. See `ai_architecture.md`.

### `GET /ai/status`

```json
{
  "configured": true,
  "provider": "openai",
  "context_version": "context_selection_v1",
  "prompt_versions": {"astro_chat": "astro_chat_v1", "natal_report": "natal_report_v1"},
  "locales": ["tr", "az", "en"],
  "models": {"low_cost": "…", "standard": "…", "premium": "…"},
  "fallback": {"chat": true, "summary": true, "report": false},
  "diagnostic": null
}
```

`models` names what this server would request, so a misconfiguration is
visible without a key. `fallback` says which calls may be served by a cheaper
model — reports may not, by default. `diagnostic` is set only when
`configured` is false, and never contains anything derived from a credential.

### `POST /ai/conversations` → 201 · `GET /ai/conversations` · `GET /ai/conversations/{id}` · `DELETE /ai/conversations/{id}`

`DELETE` archives rather than deletes, so a thread the user paid attention to
is not destroyed by a mistaken tap; `?include_archived=true` lists them again.
Another user's conversation is `404`, never `403`.

### `GET /ai/conversations/{id}/messages`

```json
[{"id": "…", "role": "user", "content": "…",
  "completion_status": "completed", "created_at": "…"},
 {"id": "…", "role": "assistant", "content": "…",
  "context_type": "natal", "source_factor_ids": ["natal:planet:sun"],
  "completion_status": "completed", "created_at": "…"}]
```

`completion_status` is `completed`, `cancelled` or `partial`. A stream the
client dropped leaves real text behind and it is kept — deleting it would make
the thread lie about what happened — but it is not a finished answer and
should not be rendered as one.

### `POST /ai/chat`

```json
{"message": "Bugün nasıl bir gün?", "conversation_id": null,
 "locale": "tr", "context_mode": null, "saved_person_id": null}
```

`context_mode` pins the material (`natal`, `daily`, `transit`, …); without it
the message is routed by deterministic rules (`intent_rules_v1`).

```json
{
  "conversation_id": "…",
  "answer": "…",
  "context_type": "daily",
  "intent": "today",
  "source_factor_ids": ["daily:score:overall", "transit:moon:trine:venus:2026-09-23"],
  "context_note": null,
  "warnings": ["birth_time_unknown: …"],
  "metadata": {
    "model": "…", "model_requested": "…", "fallback_reason": null,
    "prompt_version": "astro_chat_v1", "context_version": "context_selection_v1",
    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
    "latency_ms": 0, "provider": "openai"
  }
}
```

`source_factor_ids` only ever contains ids the backend supplied, so the client
can link a sentence back to the transit or aspect card it came from.

### `POST /ai/chat/stream`

Same request body. Server-Sent Events in a provider-independent contract:

| Event | Payload |
| --- | --- |
| `message_start` | `conversation_id`, `context_type`, `intent` |
| `text_delta` | `text` |
| `metadata` | `warnings`, `available_factor_ids` |
| `message_complete` | `conversation_id`, `model`, token counts, `latency_ms` |
| `error` | `code`, `message` |

Provider event names never reach the client. Disconnecting cancels the
generation; whatever was produced first is still stored as the turn, marked
`completion_status: "cancelled"`, so a dropped connection leaves a real
conversation rather than a gap — and nothing downstream mistakes it for a
finished answer. When such a turn is replayed to the model it is labelled as
unfinished.

### `POST /ai/reports`

```json
{"report_type": "natal", "source_id": null, "locale": "tr",
 "refresh": false, "background": false, "consumer_ref": "natal-5f2c9a1e"}
```

`horary` needs a question id; `synastry`, `composite` and `davison` need a
compatibility report id, and the type must match the source kind. A source
belonging to another user is `404` - checked before any payment.
`background: true` returns **202 with the job** rather than a report.

Response: see `ai_reports.md` for the full shape. `cached: true` means the
stored snapshot was returned without a provider call; `refresh: true` writes a
new report and leaves the old one readable at its own id.

#### Paid reports (payment enforced by the backend)

`ReportAccessPolicy` (`app/services/ai/report_access.py`) decides:

| Report type | Access |
| --- | --- |
| `natal` | credit `natal_report_credit` (product `natal_report`) |
| `synastry` | credit `synastry_report_credit` (product `synastry_report`) |
| `yearly` | credit `annual_forecast_credit` (product `annual_forecast_report`) |
| everything else | free |

When `PAID_REPORTS_INCLUDED_IN_PREMIUM=true` **and** the caller has a verified
premium entitlement (expiry, grace and revocation as `EntitlementPolicyService`
judges them), the three paid types are included and need no credit. The
default is `false`: no product decision says premium includes them.
`GET /billing/entitlements` → `capabilities.premium_reports` tells the client
which applies. A client cannot claim premium or payment in the body.

A credit-paid request **must** carry `consumer_ref` (8-100 chars,
`[A-Za-z0-9._:-]`): a client-generated id for this purchase attempt, reused on
every retry of it.

In one transaction the backend authorises the source, reserves one verified
credit and creates a durable job; the report is generated after that commit;
the credit is consumed in the same commit that completes the report. So a
credit is never consumed without its report, and a report is never delivered
without its credit.

| Situation | Response |
| --- | --- |
| delivered | `200` report (sync) / `202` job (background, or sync while another request runs it) |
| same `consumer_ref` again | the same job/report - never a second credit, never a second job |
| same `consumer_ref`, different type/source/locale/refresh | `409 report_credit_conflict` |
| no `consumer_ref` | `422 report_consumer_ref_required` |
| no available credit | `402 report_payment_required` `{product_code, entitlement_code}` |
| generation failed | sync: `502` with `details.job_id`; the credit stays reserved - retry with the same `consumer_ref` re-runs the job at no charge |
| transient failure (timeout, rate limit) | sync: `202` job; a worker retries on the same reservation |
| credit refunded before delivery | job `failed` `report_credit_unavailable`; replay → `409 report_credit_unavailable` |

**Cache.** A snapshot this user already paid for is returned again (new
`consumer_ref`, `refresh: false`) without a second charge. A snapshot that was
never paid for (made before enforcement) does not count: the request needs a
credit, and is then delivered from that snapshot without regenerating.

**Refresh.** `refresh: true` on a paid type is a new paid delivery: a new
`consumer_ref` and a new credit. Under included premium it is free, like any
premium report.

**Background / `POST /ai/report-jobs`.** The same gate. A queued premium job is
judged again when it runs - premium that lapsed in between delivers nothing.

### `GET /ai/reports` · `GET /ai/reports/{id}`

Newest first, filterable by `report_type`. Private to their owner.

### `POST /ai/report-jobs` → 202 · `GET /ai/report-jobs/{id}` · `POST /ai/report-jobs/{id}/cancel`

Durable jobs for long reports: `queued → running → completed | failed`, or
`cancelled`. The job row carries `attempt`, `error_code` and `report_id`.
Same body and payment rules as `POST /ai/reports` with `background: true`; a
replayed `consumer_ref` whose report is complete answers `200` with the report.
Cancelling a paid job keeps its reservation; the same `consumer_ref` runs it
again.

### Errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `ai_not_configured` | 503 | No provider key on this server |
| `ai_rate_limited` | 429 | Upstream or per-user limit |
| `ai_timeout` | 504 | Generation took too long |
| `ai_context_too_large` | 422 | Too much material for one interpretation |
| `ai_invalid_output` | 502 | Unusable output after one retry |
| `generation_failed` | 502 | Grounding or safety check rejected the result |
| `generation_in_progress` | 502 | The same report is already being generated |
| `birth_profile_missing` | 422 | Nothing to interpret yet |
| `report_consumer_ref_required` | 422 | A credit-paid report without `consumer_ref` |
| `report_payment_required` | 402 | No available credit for this paid report |
| `report_credit_conflict` | 409 | The `consumer_ref` was used for a different report |
| `report_credit_unavailable` | 409 | The reserved credit was refunded/revoked |

`ai_rate_limited` covers both our per-user quota and the provider's own
throttling — the client's response is the same either way. A 429 carries a
`Retry-After` header, and `details.scope` (`ai_chat`, `ai_stream`,
`ai_report`) says which limit was hit. Quotas are keyed by user, not by IP.

---

## Divination

Tarot, Elder Futhark runes and Katina. Every route needs a bearer token and
every reading is private to its owner; another user's reading is `404`.

**Drawing and interpreting are separate calls.** The draw needs no AI, so a
user gets their cards even when the interpretation service is unconfigured or
down. See `divination_architecture.md`.

### `GET /divination/decks`

```json
[{
  "deck_type": "katina",
  "deck_version": "katina_v1",
  "item_count": 65,
  "optional_item_count": 0,
  "reversal_supported": false,
  "locales": ["tr"],
  "back_asset_key": "katina_back",
  "content_note": "All 65 meanings are PRODUCT-DEFINED, not traditional. …",
  "spread_codes": ["single_card", "three_card", "relationship", "seven_card", "nine_card"]
}]
```

`content_note` is not decoration: it states whether a deck's meanings follow a
documented tradition or were written by Astrofrekans, and the client should
show it.

### `GET /divination/decks/{deck_type}/spreads`

```json
[{
  "deck_type": "tarot", "spread_code": "celtic_cross",
  "spread_version": "tarot_celtic_cross_v1",
  "name": "Kelt Haçı", "origin": "traditional",
  "card_count": 10, "allow_reversed": true,
  "positions": [
    {"index": 1, "key": "significator", "title": "Mevcut Durum",
     "role": "The heart of the matter as it stands."}
  ]
}]
```

`origin` is `traditional` or `product_defined` — never guessed. All five
Katina spreads are `product_defined`.

### `GET /divination/decks/{deck_type}/items`

The whole deck for browsing. `?include_optional=true` adds the blank rune.

### `POST /divination/readings` → 201

```json
{"deck_type": "tarot", "spread_code": "celtic_cross",
 "locale": "tr", "question": "…", "include_optional_items": false}
```

The question is optional and **untrusted**: the cards are dealt before it is
read, so nothing in it can influence the draw. Max 500 characters. It is
stored but never logged.

`include_optional_items` applies to the rune deck only (the blank "Odin"
rune, which is not part of the canonical 24).

```json
{
  "id": "…", "deck_type": "tarot", "deck_version": "tarot_v1",
  "spread_code": "celtic_cross", "spread_version": "tarot_celtic_cross_v1",
  "spread_name": "Kelt Haçı", "locale": "tr",
  "question": "…", "repeat_reading": false, "repeat_of_id": null,
  "rng_source": "system_csprng", "drawn_at": "…", "status": "drawn",
  "has_interpretation": false,
  "items": [{
    "draw_order": 1, "position_index": 1, "position_key": "significator",
    "position_title": "Mevcut Durum", "position_role": "The heart of the matter…",
    "item_id": "tarot:major:16:kule", "display_name": "Kule",
    "canonical_name": "The Tower", "orientation": "reversed",
    "image_asset_key": "kule", "keywords": ["…"], "meaning": "…",
    "content_status": "traditional"
  }]
}
```

`image_asset_key` is a **stem**, not a path: the client composes
`assets/tarot/cards/kule.webp` from its own manifest.

`rng_source` is `system_csprng` for a real deal. Anything else is a seeded
test deal and must not be presented as a reading.

`repeat_reading` marks the same question, same deck, asked again within six
hours. It is recorded, never blocked.

### `GET /divination/readings` · `GET /divination/readings/{id}` · `DELETE /divination/readings/{id}`

Readings are **immutable**: the same cards in the same positions, however long
afterwards they are opened. Listing is filterable by `deck_type`. Delete is a
soft delete, like every other user-owned record.

### `POST /divination/readings/{id}/interpret`

```json
{"locale": "tr", "refresh": false, "background": false}
```

Returns the B6 report shape (see `ai_reports.md`). `cached: true` means the
stored interpretation was returned with no provider call. `refresh: true`
produces a new interpretation — **the draw never changes**, only the reading
of it. `background: true` returns `202` with a job.

`503 ai_not_configured` when no provider is set up. The reading itself is
unaffected.

Every section's `factor_ids` point at cards that were actually drawn:

```
tarot:major:16:kule:reading:{reading_id}:position:2:reversed
```

A citation the draw did not produce is rejected, so the model cannot name a
card that was not dealt, claim a reversal that did not happen, or invent a
position.

### `GET /divination/readings/{id}/interpretation`

The stored interpretation, or `404` if the reading has not been interpreted.

### Errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `unknown_spread` | 404 | No such spread for that deck |
| `deck_too_small` | 422 | The spread needs more items than the deck holds |
| `rate_limited` | 429 | Draw quota (`divination_draw`) |
| `ai_rate_limited` | 429 | Interpretation quota (`divination_interpret`) |
| `ai_not_configured` | 503 | No provider; the reading still exists |
| `generation_failed` | 502 | Grounding or safety rejected the interpretation |

---

## Marketplace

Expert profiles, offerings, availability and slots. Every route needs a bearer
token. Search and public profiles carry the shop front only - no email, no
real name, no birth data.

### `POST /experts/apply` -> 201

```json
{"display_name": "Nova Astro", "headline": "Natal and synastry",
 "bio": "...", "languages": ["tr", "en"],
 "specialties": ["astrology", "synastry"],
 "experience_years": 15, "timezone": "Europe/Istanbul"}
```

Creates the caller's own profile at `pending_review`, never `active` or
`verified`. Activation and verification are moderation decisions with **no
routes**. `409 expert_profile_exists` for a second application.

### `GET /experts`

Filters: `specialty`, `language`, `service_code`, `delivery_type`,
`min_price_minor`, `max_price_minor`, `currency`, `verified`, `rating_min`.
Sorts: `rating`, `review_count`, `price`, `experience`, `newest`. Pagination
(`limit`, `offset`) is mandatory.

```json
{
  "items": [{
    "id": "...", "display_name": "Nova Astro", "headline": "...",
    "languages": ["tr", "en"], "specialties": ["astrology", "synastry"],
    "experience_years": 15, "verified": true,
    "rating_average": 4.8, "rating_count": 36,
    "from_price": {"amount_minor": 10000, "currency": "TRY"},
    "is_favorite": false
  }],
  "total": 1, "limit": 20, "offset": 0
}
```

Money is **integer minor units** plus an ISO-4217 code. `10000 TRY` is 100.00
lira. Formatting is the client's job.

### `GET /experts/me` / `PATCH /experts/me`

The caller's own profile. `PATCH` refuses `verified`, `rating_*`, and
`status: active | suspended` with `403`.

### `GET /experts/{id}` / `GET /experts/{id}/services`

Active profiles only; anything else is `404`, because the status of somebody's
application is not public. The raw weekly schedule is deliberately absent -
bookable times come from `/slots`.

Each offering reports its **effective** capabilities: the catalogue's support
AND the channel it is sold through.

```json
{"id": "...", "service_code": "synastry", "title": "60-minute consultation",
 "delivery_type": "video", "duration_minutes": 60,
 "price": {"amount_minor": 10000, "currency": "TRY"},
 "supports_chat": false, "supports_voice": false, "supports_video": true,
 "requires_birth_data": true, "requires_partner_data": true,
 "supports_appointment": true}
```

### `POST /experts/me/services` / `PATCH` / `DELETE`

Validated against the catalogue: `422 service_not_offerable` when the
definition is automated-only or does not support the channel. `DELETE`
deactivates rather than deletes - past orders point at the offering.

Changing a price never changes an existing order.

### `GET|POST|DELETE /experts/me/availability`

```json
{"weekday": 0, "start_local_time": "09:00:00",
 "end_local_time": "12:00:00", "timezone": "Europe/Istanbul"}
```

Local time plus a zone, not UTC: "Mondays 09:00 in Istanbul" has to stay 09:00
across a daylight-saving change. `weekday` is 0 = Monday. A window crossing
midnight is entered as one window per local day.

### `GET|POST|DELETE /experts/me/availability/exceptions`

`vacation`, `busy`, `manual_block` remove time; `extra_availability` adds it.
Stored in UTC.

### `GET /experts/{id}/slots?service_id=&from=&to=&timezone=`

```json
{
  "expert_id": "...", "expert_service_id": "...", "duration_minutes": 60,
  "display_timezone": "Europe/Istanbul",
  "slots": [{
    "starts_at_utc": "2026-10-01T06:00:00Z",
    "ends_at_utc": "2026-10-01T07:00:00Z",
    "starts_at_local": "2026-10-01T09:00:00+03:00",
    "ends_at_local": "2026-10-01T10:00:00+03:00",
    "display_timezone": "Europe/Istanbul"
  }],
  "generated_at": "..."
}
```

UTC is canonical; the local times are for display. Generated from the weekly
schedule, exceptions, existing appointments and live holds, with buffers,
minimum notice and the booking horizon applied. A time that was never offered
cannot be booked.

### `POST /experts/{id}/hold` -> 201

Claims a slot briefly while an order is placed, so two people filling in the
same form do not both believe they have it. Expires on its own
(`SLOT_HOLD_TTL_SECONDS`).

### `POST|DELETE /experts/{id}/favorite` / `GET /favorites/experts`

### `GET /experts/{id}/reviews`

```json
{"items": [{"id": "...", "rating": 5, "comment": "...", "created_at": "..."}],
 "total": 36, "rating_average": 4.8, "rating_count": 36,
 "distribution": {"1": 0, "2": 1, "3": 2, "4": 8, "5": 25}}
```

---

## Orders and appointments

### `POST /orders` -> 201

```json
{"expert_service_id": "...", "starts_at_utc": "2026-10-01T06:00:00Z",
 "display_timezone": "Europe/Istanbul",
 "sources": [{"source_kind": "compatibility_report", "source_id": "..."}],
 "notes": "..."}
```

Creates the order and, for a service delivered by appointment, books the slot
**in the same transaction**. Send `Idempotency-Key` and a retry returns the
original order instead of booking twice; the same key with a different service
is `409 idempotency_conflict`.

A source must belong to the ordering user (`404 source_not_found`), and
referencing one is **not** an access grant.

```json
{
  "id": "...", "service_code": "synastry", "fulfillment_mode": "hybrid",
  "delivery_type": "video",
  "status": "pending_payment", "payment_status": "pending",
  "expert_id": "...", "expert_display_name": "Nova Astro",
  "service_title": "60-minute consultation", "service_duration_minutes": 60,
  "subtotal": {"amount_minor": 10000, "currency": "TRY"},
  "total": {"amount_minor": 10000, "currency": "TRY"},
  "commission": {"gross_amount_minor": 10000, "platform_fee_minor": 2000,
                 "expert_net_minor": 8000, "commission_basis_points": 2000},
  "appointment": {"id": "...", "starts_at_utc": "...", "status": "pending"},
  "sources": [{"source_kind": "compatibility_report", "source_id": "..."}],
  "granted_consent_scopes": []
}
```

The price, the split and the service title are a **snapshot**: an expert
raising their rate later does not change this order.

**No payment provider is integrated.** A priced order is created at
`pending_payment` and stays there. A free offering is created `confirmed` with
payment `not_required`.

### `GET /orders` / `GET /orders/{id}` / `POST /orders/{id}/cancel`

Cancelling also cancels any live appointment and records the actor
(`user`, `expert`, `admin`, `system`, `technical_failure`) and the reason.
`payment_status` keeps its value - an order cancelled while paid still says a
refund is owed. No refund amount is computed in this phase.

### `POST /appointments` / `GET /appointments` / `GET|POST /appointments/{id}[/cancel]`

Direct booking, for a free or already-paid engagement. Most bookings go
through `POST /orders`.

### `GET /expert/orders` / `GET /expert/orders/{id}` / `GET /expert/appointments` / `POST /expert/appointments/{id}/cancel`

The expert workspace. An expert sees only orders placed with them; another
expert's is `404`. Each referenced source reports `readable: true | false`
according to consent - a reference is not permission.

---

## Consent

### `GET /orders/{id}/consents` / `PUT /orders/{id}/consents`

```json
{"scopes": ["share_birth_profile", "share_natal_chart"]}
```

The **complete set**: anything absent is revoked, which makes "share less than
before" one action. Only the user whose data it is may call these - they live
under the user's own order, so an expert gets `404`.

```json
[{"scope": "share_birth_profile", "granted_at": "...",
  "revoked_at": null, "active": true}]
```

Revocation stops future reads immediately. It cannot un-see what an expert
already read. See `service_consent.md`.

---

## Reviews

### `POST /orders/{id}/review` -> 201 / `PATCH|DELETE /reviews/{id}`

Only a **completed** order with an expert can be reviewed, once
(`409 review_not_allowed`, `409 review_exists`). Rating is 1-5; anything else
is `422`. An expert cannot review their own service.

The expert's `rating_average` and `rating_count` are recomputed from the
reviews after every change.

### Marketplace errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `expert_profile_exists` | 409 | One profile per account |
| `invalid_expert_data` | 422 | Bad language, specialty or experience |
| `invalid_timezone` | 422 | Not an IANA zone |
| `service_not_offerable` | 422 | The catalogue does not allow it |
| `slot_not_offered` | 422 | That time was never available |
| `slot_unavailable` | 409 | Taken, or held by someone else |
| `slot_range_too_large` | 422 | Longer than slots are generated for |
| `idempotency_conflict` | 409 | Same key, different request |
| `source_not_found` | 404 | Not the ordering user's material |
| `order_not_cancellable` | 409 | Already terminal |
| `appointment_not_cancellable` | 409 | Not in a live state |
| `consent_required` | 403 | The user has not shared that |
| `review_not_allowed` / `review_exists` / `self_review` | 409 | Review rules |
| `invalid_search` | 422 | Unknown sort or bad pagination |

---

## Firebase authentication (B9)

`AUTH_MODE=hybrid`: the backend accepts **both** its own JWTs and Firebase ID
tokens as the bearer token. Existing accounts keep working unchanged. No backend
JWT is minted for a Firebase session - the Firebase SDK owns the session on the
client, and wrapping one token in another would mean two lifetimes and two
revocation stories.

### `GET /auth/capabilities`

Unauthenticated. Lets a client decide whether to initialise Firebase at all.

```json
{
  "auth_mode": "hybrid",
  "accepts_local_jwt": true,
  "accepts_firebase_token": true,
  "firebase_configured": true,
  "firebase_project_id": "astrofrekans-prod"
}
```

`firebase_project_id` is public configuration. No key of any kind is returned.

### `POST /auth/firebase/session`

```json
{"id_token": "<Firebase ID token>"}
```

Optional - the same mapping happens on any authenticated request.

```json
{
  "user_id": "...", "firebase_uid": "...", "email": "...",
  "email_verified": true, "is_new_account": false,
  "provider_id": "google.com", "auth_mode": "hybrid"
}
```

`is_new_account` is true only when this sign-in **created** the local account.
Linking an identity to an account that already existed is not signing up.

### `POST /auth/firebase/link` / `DELETE /auth/firebase/link`

The safe linking path: the caller is already signed in, which is the proof of
ownership a matching email address is not. This is how a password account adds
Google or Apple sign-in.

Unlinking is refused with `last_sign_in_method` when the account has no password.

### Auth errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `firebase_not_configured` | 503 | No service account on this deployment |
| `firebase_auth_disabled` | 503 | `AUTH_MODE=local_jwt` |
| `invalid_firebase_token` | 401 | Signature, audience or issuer |
| `firebase_token_expired` | 401 | Refresh and retry |
| `firebase_token_revoked` | 401 | Signed out elsewhere |
| `firebase_account_disabled` | 401 | Disabled in the Firebase console |
| `account_link_required` | 409 | That email has an account; sign in and link |
| `identity_already_linked` | 409 | That credential belongs to another account |
| `last_sign_in_method` | 409 | Set a password before unlinking |

See `firebase_auth.md`.

---

## Chat (B9)

**Send over HTTPS, receive over a Firestore listener.** Clients read
`conversations/{firebaseConversationId}/messages` directly, ordered by
`createdAt`, and write nothing. Authorisation depends on order state, expert
suspension, a completion grace period and the catalogue - none of which a
security rule can see. See `chat_architecture.md`.

### `GET /chat/policy`

The rules as data, so a client can explain a closed thread without hard-coding
the reasons.

```json
{
  "writable_order_states": ["awaiting_expert", "confirmed", "in_progress", "paid"],
  "readable_order_states": ["...", "cancelled", "completed", "refunded"],
  "chat_delivery_types": ["chat", "video", "voice"],
  "read_only_after_completion_days": 30,
  "message_max_length": 4000,
  "attachments_per_message": 4,
  "attachment_max_bytes": 8388608,
  "attachment_allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
}
```

`pending_payment` is absent from the writable set. Chat before payment would be a
free consultation channel.

### `POST /conversations` -> 201

```json
{"order_id": "..."}
```

Idempotent - one conversation per order is a database constraint, so a retry
returns the original thread.

```json
{
  "id": "...", "order_id": "...", "appointment_id": "...",
  "status": "active",
  "provisioning_status": "active",
  "my_role": "user",
  "counterpart_display_name": "Nova Astro",
  "expert_id": "...",
  "permission": {"can_read": true, "can_write": true, "reason": "ok"},
  "firebase_conversation_id": "...",
  "message_count": 0, "last_message_at": null,
  "closed_at": null, "created_at": "..."
}
```

`provisioning_status` is `failed` when Firebase was unavailable. **The
conversation still exists** - an order somebody paid for does not roll back
because Firestore blinked - and the next read retries the projection.
`firebase_conversation_id` is the Firestore document to subscribe to.

### `GET /conversations` / `GET /conversations/{id}` / `POST /conversations/{id}/close`

Reading one conversation also reconciles its status against its order, which is
why a completed consultation becomes read-only with no scheduler. Closing stops
new messages; history survives, and a later read does not reopen it.

### `POST /conversations/{id}/messages` -> 201

```json
{"text": "Merhaba", "client_message_id": "uuid-from-the-client"}
```

or `{"attachment_id": "..."}`, with optional `text` as a caption.

Resending the same `client_message_id` returns the original message. The same id
with **different** content is `409 message_conflict` - silently returning the
wrong message would hide a client bug.

```json
{
  "message_id": "...", "conversation_id": "...",
  "sender_role": "user", "message_type": "text",
  "text": "Merhaba", "attachment_id": null,
  "client_message_id": "...",
  "created_at": "2026-09-23T18:00:00Z", "deleted_at": null
}
```

`created_at` is a server timestamp. A client clock is never canonical.

### `GET /conversations/{id}/messages?limit=&before=`

A page of history, newest first. Pass the previous page's `next_cursor` as
`before`. A client with a live listener only needs the newest page.

### `DELETE /conversations/{id}/messages/{message_id}`

Soft delete, **only the sender's own**. A conversation either party can edit on
the other's behalf is not a record of anything.

### `GET /conversations/{id}/presence`

```json
[{"firebase_uid": "...", "online": true, "last_changed": "..."}]
```

Only for people the caller shares this conversation with. There is no endpoint
that reads presence by uid - a global lookup would let any account watch any
other. See `presence.md`.

### Attachments

`POST /conversations/{id}/attachments` -> 201 authorises one upload:

```json
{"mime_type": "image/jpeg", "size_bytes": 2048, "original_filename": "photo.jpg"}
```

```json
{
  "attachment": {"id": "...", "status": "pending"},
  "upload": {
    "storage_key": "chat/{conversationId}/{attachmentId}/original.jpg",
    "bucket": "...", "max_bytes": 8388608,
    "allowed_mime_types": ["image/jpeg"]
  }
}
```

The path is **server-derived**; the client's filename is display metadata and
never reaches it. Upload directly to Storage, then
`POST /attachments/{id}/finalize`, which inspects the stored object and rejects a
type or size mismatch - the claimed content type is not the content type. Only a
`ready` attachment may be referenced by a message. See `media_attachments.md`.

### Chat errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `chat_not_available` | 409 | The order does not entitle anybody to a thread |
| `chat_read_only` | 409 | History yes, new messages no |
| `message_conflict` | 409 | Same `client_message_id`, different content |
| `message_rejected` | 422 | Empty, too long, or a bad attachment reference |
| `firebase_identity_required` | 409 | Chat needs a Firebase identity |
| `mime_type_forbidden` | 422 | SVG, HTML or an executable |
| `mime_type_not_allowed` | 422 | Not in the allow-list, or not what was claimed |
| `attachment_too_large` | 422 | Declared or actual |
| `attachment_missing` | 422 | Finalised before the upload arrived |
| `attachment_not_ready` | 422 | Referenced while still pending |
| `attachment_already_used` | 422 | Already sent |
| `attachment_quota_exceeded` | 429 | Too many in-flight intents |
| `firebase_not_configured` | 503 | Chat needs Firebase |

**Opening a chat grants no data access.** B8 consent is unchanged: an expert may
hold a conversation and still have no right to read the user's chart.

---

## Push devices (B9)

### `POST /devices/push` -> 201

```json
{"token": "<FCM token>", "platform": "android", "device_id": "...", "app_version": "1.0.0"}
```

Idempotent on the token. Registering a token that belongs to another account
**moves** it - a shared handset should not keep notifying the previous user.

```json
{
  "id": "...", "platform": "android",
  "token_fingerprint": "a1b2c3d4e5f6...",
  "app_version": "1.0.0", "enabled": true,
  "disabled_reason": null, "last_seen_at": "...", "created_at": "..."
}
```

The token is **never returned**, only a fingerprint. Echoing every token back
would turn a device list into a way to harvest them.

### `GET /devices/push` / `DELETE /devices/push/{id}`

Your own devices only; another account's is a `404`. Deletion is a real delete.
Lists FCM tokens only - never a VoIP credential.

### `POST /devices/voip` -> 201 (iOS PushKit)

```json
{"token": "<PushKit token, hex>", "environment": "production",
 "device_id": "optional, stored hashed", "app_version": "1.4.0"}
```

A **separate credential** from the FCM token (`PKPushRegistry`, type
`.voIP`), used only to ring incoming calls through APNs `voip` and CallKit.
`environment` must equal the server's `APNS_ENVIRONMENT`
(`422 voip_environment_mismatch`). Not hex, or already registered as an FCM
token: `422 invalid_push_token`. Idempotent on the token; another account's
token moves. Response `{id, token_fingerprint, environment, app_version,
enabled, disabled_reason, last_seen_at, created_at}` - never the token.

### `GET /devices/voip` / `DELETE /devices/voip/{id}`

Own credentials only (`404` otherwise). Delete on sign-out and when PushKit
invalidates the token (`didInvalidatePushTokenFor`); register the new token
from `didUpdate pushCredentials`.

### Call push payload (FCM data / APNs VoIP)

```json
{"event": "incoming_call|call_answered|call_cancelled|call_missed",
 "call_id": "…", "call_type": "audio|video",
 "event_version": "<int>", "expires_at": "<unix seconds, incoming_call only>"}
```

Keep the highest `event_version` per `call_id`. A push is a presentation hint:
answering is `GET /calls/{id}` → `POST /calls/{id}/join`. See
`mobile_call_delivery.md`.

**A notification payload carries an id and a generic line, never content.** A
lock screen is a public surface. See `push_notifications.md`.

---

## Calls (B10)

LiveKit voice and video. FastAPI authorises; LiveKit carries the media. See
`call_architecture.md`, `call_authorization.md`, `call_lifecycle.md`.

### `GET /calls/status`

```json
{"configured": true, "provider": "livekit"}
```

Only these two fields. Never a URL, a key or a secret.

### `POST /calls` -> 201 (new) / 200 (already live)

```json
{"order_id": "...", "appointment_id": "... (optional)", "call_type": "video"}
```

Either party may open it. While a call for the order is live, both get the same
session. Before the join window it is `scheduled` (no room yet); inside it,
`waiting`.

```json
{
  "id": "...", "order_id": "...", "appointment_id": "...", "conversation_id": "...",
  "call_type": "video", "status": "waiting", "my_role": "user",
  "scheduled_start_at": "...", "scheduled_end_at": "...",
  "join_opens_at": "...", "join_closes_at": "...",
  "ringing_at": null, "started_at": null, "ended_at": null,
  "end_reason": null, "duration_seconds": null,
  "participants": [
    {"role": "expert", "status": "invited", "is_me": false, "first_joined_at": null, "last_left_at": null},
    {"role": "user", "status": "invited", "is_me": true, "first_joined_at": null, "last_left_at": null}
  ],
  "recording_enabled": false,
  "created_at": "..."
}
```

No token, no room name, no LiveKit identity - of either party.

If the room cannot be created: `503 call_provider_unavailable` with
`details.call_id` of the FAILED attempt. The order is untouched; opening again
is a new attempt.

### `POST /calls/{id}/join`

Re-authorises everything, every time. Sent `Cache-Control: no-store`.

```json
{
  "call_id": "...",
  "call_type": "video",
  "livekit_url": "wss://...",
  "token": "...",
  "token_expires_at": "...",
  "participant_identity": "p_3f9c...",
  "role": "user",
  "room_options": {"audio": true, "video": true}
}
```

The token admits one opaque identity to one room, for at most
`CALL_TOKEN_TTL_SECONDS` and never past the window. It may publish only the
sources the call type allows (`microphone`, or `camera` + `microphone`), may not
publish data, and has no admin grant. Expiry matters only for a *new*
connection; LiveKit refreshes a connected client. Call again to reissue.

### `GET /calls/{id}` · `GET /calls?limit=&before=`

Member-only; others get `404`. The status here is the one to trust: it comes
from provider events and the clock, not from clients. The list covers calls on
either side, newest first; pass `next_cursor` as `before`.

### `POST /calls/{id}/end`

Either party. `active` -> `ended`; anything earlier -> `cancelled`. Idempotent
and final.

### `POST /webhooks/livekit`

For LiveKit, not clients. The raw body is verified against the JWT in
`Authorization` (our key, SHA-256 of the body). Anything else is
`401 invalid_webhook`. Applied once per event id.

```json
{"status": "ok", "outcome": "applied"}
```

`outcome` is one of `applied`, `duplicate`, `stale`, `replaced`, `noted`,
`unknown_room`, `intruder`, `late_join_removed`, `unknown_participant`.

### Call errors

| Code | HTTP | Meaning |
| --- | --- | --- |
| `call_provider_not_configured` | 503 | No LiveKit on this deployment |
| `call_provider_unavailable` | 503 | LiveKit did not answer |
| `call_token_failed` | 503 | A token could not be minted |
| `call_not_found` | 404 | Not a call you are in |
| `call_not_allowed` | 403 | `details.reason` says why (payment, order state, expert, appointment...) |
| `call_too_early` | 409 | Before the join window (`details.opens_at`) |
| `call_window_closed` | 409 | After it |
| `call_already_ended` | 409 | Terminal; open a new call if the consultation allows it |
| `call_type_not_supported` | 422 | The order's channel does not include that call |
| `call_participant_limit` | 409 | Reserved |
| `invalid_webhook` | 401 | Signature did not verify |

---

## Billing (B11)

No response here ever contains an App Store JWS, a Google purchase token, a
provider payload, a card detail or a secret. See `payment_architecture.md`.

### `GET /billing/status`

```json
{"apple_configured": false, "google_configured": false, "external_marketplace_configured": false}
```

Booleans only.

### `GET /billing/products?platform=ios|android`

```json
{"platform": "ios", "items": [{"code": "premium_monthly", "product_type": "subscription",
  "entitlement_code": "premium", "store_product_id": "..."}]}
```

No prices - show StoreKit's / Play's localised price. Only products with an
id on that store; `web` returns none.

### `GET /billing/account-tokens`

`{"apple_app_account_token": "<uuid>", "google_obfuscated_account_id": "<hash>"}`
- pass to StoreKit (`appAccountToken`) / Play Billing (`obfuscatedAccountId`).

### `POST /billing/apple/verify` · `POST /billing/google/verify`

```json
{"product_code": "premium_monthly", "signed_transaction": "<jwsRepresentation>", "transaction_id": "..."}
{"product_code": "premium_monthly", "purchase_token": "..."}
```

```json
{"purchase_id": "...", "product_code": "premium_monthly", "status": "active",
 "environment": "production", "expires_at": "...", "entitlements": { ... }}
```

Idempotent. Errors: `store_provider_not_configured` 503,
`store_provider_unavailable` 503, `store_verification_failed` 422,
`store_environment_rejected` 422, `unknown_store_product` 422,
`product_mismatch` 422, `purchase_account_mismatch` 409,
`purchase_owned_by_another_account` 409.

### `POST /billing/reconcile`

Restore: `{"apple": [...verify bodies], "google": [...]}` (max 20 each) →
`{"verified": n, "failed": [{"store", "product_code", "code"}], "entitlements": {...}}`.

### `GET /billing/entitlements`

```json
{"tier": "premium", "premium": true, "premium_expires_at": "...",
 "credits": {"natal_report_credit": 1},
 "capabilities": {"tier": "premium", "ai_chat_rate_limit": "40/hour", "premium_reports": true, "advanced_forecasts": true},
 "items": [{"entitlement_code": "premium", "kind": "subscription", "status": "cancelled_pending_expiry",
            "active": true, "environment": "production", "expires_at": "..."}]}
```

### `POST /billing/credits/consume`

`{"entitlement_code": "pre_analysis_credit", "consumer_ref": "<idempotency key>"}` -
idempotent per `consumer_ref`; `402 no_credit_available` when none.

**Not for reports.** Report credits (`natal_report_credit`,
`synastry_report_credit`, `annual_forecast_credit`) answer
`409 credit_reserved_for_reports`: `POST /ai/reports` spends them itself,
atomically with the report. A `consumer_ref` starting `ai_report:` is refused
(`422 consumer_ref_reserved`).

### Orders

* `GET /orders/{id}/payment` - lines, groups, `payable_externally`,
  `blocked_by_policy_review`.
* `POST /orders/{id}/payment` `{"method": "external" | "store_credit", "idempotency_key"}` -
  external returns `client_handoff` (the provider's hosted page / SDK hand-off,
  never card data). Errors: `payment_policy_review_required` 409,
  `external_payment_provider_not_configured` 503, `order_not_payable` 409.
* `POST|GET /orders/{id}/refund-requests` `{"reason", "amount_minor"?, "idempotency_key"}` -
  owner only; `refund_amount_invalid` 422, `nothing_to_refund` 409. The
  `decision` field is the policy's advice; a person decides.

### Expert

* `GET /expert/earnings` - per currency `pending_minor`, `available_minor`
  (may be negative), `paid_minor`; `settlement_hold_days` (null = not decided).
* `GET /expert/payouts` - own payouts, read-only.

### Webhooks

| Route | Verification |
| --- | --- |
| `POST /webhooks/apple/app-store` | App Store Server Notifications V2 JWS, Apple's library |
| `POST /webhooks/google/play` | Pub/Sub push OIDC JWT (`aud`, `iss`, `email`, `email_verified`) |
| `POST /webhooks/payments/external` | the external provider's signature |

Unverified → `401 invalid_provider_notification`, nothing changes. Applied
once per event id. Rate-limited per IP.

---

## System

| Route | Purpose |
| --- | --- |
| `GET /health` | Liveness. Always 200 while the process runs. |
| `GET /ready` | Readiness: `checks.database`, `checks.cache`, `checks.ephemeris`. 503 when the database or ephemeris is unavailable. |

---

## Flutter mapping (phase B10)

| Dart model | Endpoint | Notes |
| --- | --- | --- |
| `NatalChart`, `PlanetPosition`, `HousePosition`, `NatalAspect` | `/astrology/natal-chart/me` | Field names already line up; `isMock` becomes `false` and `warnings` drives the UI notes |
| `MoonPhase` | `/astrology/moon-phase` | |
| `BirthData` | `/birth-profiles/me` | Client keeps local date/time, server owns the UTC conversion |
| `AuthRepository` | `/auth/*` | Store both tokens in `flutter_secure_storage`; on 401 refresh once, on `token_reused` sign out |
| `AstrologyService` | `/astrology/*` | `ApiAstrologyService` implements the existing interface; `MockAstrologyService` stays for offline and tests |

`/ai/*` (B6), `/divination/*` (B7), the marketplace routes (B8), the
Firebase, chat and push routes (B9), the call routes (B10) and billing (B11)
are live and have no Flutter binding yet - the client work is B12. Still
ahead: `/history/*`.
