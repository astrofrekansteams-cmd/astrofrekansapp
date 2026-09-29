# Expert Profiles and Offerings

## The profile

An `Expert` row is a **shop front**, deliberately separate from the `User`
account behind it. Everything on it is meant to be seen by strangers, and
nothing private is copied in: no email, no real name, no birth data. A search
result and a public profile are built from this table alone.

| Field | Notes |
| --- | --- |
| `display_name` | The practising name, not the account name |
| `headline`, `bio`, `avatar_key` | Presentation |
| `languages` | Stable codes: `tr`, `az`, `en` |
| `specialties` | Stable codes, never free text |
| `experience_years` | 0–80 |
| `timezone` | IANA. Availability is stored against it |
| `status` | Lifecycle; only `active` is discoverable |
| `verified` | A moderation flag |
| `rating_average`, `rating_count` | Cache; reviews are the source of truth |

**One profile per account**, enforced by `uq_experts_user` rather than by
application code. A second application returns `409 expert_profile_exists`.

## Specialties and languages are codes

Free text would make search unusable within a month: "tarot", "Tarot", "tarot
okuma" and "tarot reading" would be four different specialties.

```
astrology, natal_chart, transits, synastry, composite, davison,
horary, monthly_forecast, annual_forecast, tarot, rune, katina
```

New entries are additive; existing values never change, because a stored
profile and a client filter both speak them.

Languages are BCP-47-compatible lowercase codes. The supported set is `tr`,
`az`, `en` — an unsupported code is a `422` rather than silently accepted, so
a typo does not produce a profile nobody can find. Display labels are the
client's job; the backend does not hard-code "Türkçe".

## A user cannot promote themselves

`POST /experts/apply` creates the caller's own profile at `pending_review`,
never `active`, never `verified`.

`PATCH /experts/me` refuses:

* `verified`, `rating_average`, `rating_count` → `403`
* `status: active` or `status: suspended` → `403`

A user may move their own profile between `draft`, `pending_review`, `paused`
and `inactive` — pausing when they are on holiday is theirs to decide;
publishing is not.

Activation and verification exist as service methods with **no routes**:

```python
ExpertProfileService.approve(expert_id)
ExpertProfileService.verify(expert_id, verified=True)
ExpertProfileService.suspend(expert_id, reason=...)
ExpertProfileService.reactivate(expert_id)
```

Ready for an admin surface, unreachable by the person being moderated.

## Offerings

An `ExpertService` is one priced offering: an expert's version of a catalogue
service.

| Field | Notes |
| --- | --- |
| `service_definition_id` | The catalogue row. The source of truth |
| `title`, `description` | The expert's own words |
| `delivery_type` | `chat`, `voice`, `video`, `written_report` |
| `duration_minutes` | 5–600; drives slot length |
| `price_minor` + `currency` | Integer minor units, ISO-4217 |
| `active` | Deactivated, never deleted |

### The catalogue constrains the offering

An offering may narrow what a definition allows. It can never widen it.

* A definition whose `fulfillment_modes` contain neither `expert` nor `hybrid`
  cannot be offered at all → `422 service_not_offerable`.
* A definition with `supports_video = false` cannot be sold as a video
  consultation → `422`, listing the channels that *are* supported.
* `requires_birth_data`, `requires_partner_data` and `requires_question` come
  from the definition and are **not overridable**. An expert deciding their
  version of synastry needs no partner data would break every client that
  collects inputs from those flags.

### Effective capabilities

The API returns `supports_chat` / `supports_voice` / `supports_video` as the
**intersection** of the definition's capability and the offering's channel:

```
effective = definition.supports_video AND offering.delivery_type == video
```

The client uses these for button visibility. Computing it as an intersection
means a definition losing video support removes the button immediately,
without an expert having to edit anything.

No chat, voice or video system exists yet. These flags describe what *will* be
possible, and a client can lay out the screen against them today.

### Editing a price does not rewrite history

Changing `price_minor` affects future orders only. Every order carries its own
price snapshot — see `orders.md`. Tested end to end: an order placed at 10000
still says 10000 after the offering moves to 15000, and the next order says
15000.

### Deactivating, not deleting

`DELETE /experts/me/services/{id}` sets `active = false`. Past orders point at
the offering and must keep resolving, so the row stays. A deactivated offering
disappears from search and from the public profile.

## Ownership

There is **no route that takes an expert id for a write**. Every mutating
endpoint is under `/experts/me/**` and the service loads the caller's own
`Expert` row, so an id in a URL can never redirect the write. Another expert's
service id under your own `/me` is simply a `404`.

| Action | User | Owning expert | Other expert |
| --- | --- | --- | --- |
| View public profile | ✅ if active | ✅ | ✅ if active |
| View own profile | — | ✅ | — |
| Edit profile | — | ✅ (non-moderation fields) | ❌ 404 |
| Create/edit/deactivate offering | — | ✅ | ❌ 404 |
| Edit availability | — | ✅ | ❌ 404 |
| Activate / verify | ❌ 403 | ❌ 403 | ❌ 403 |

## Known limitations

- No admin API. Moderation runs through service methods, which today means a
  shell or a script.
- No profile media beyond `avatar_key`; no portfolio, no certificates, no
  identity documents. Verification is a flag with no evidence attached, and a
  real verification workflow is a later decision.
- Specialty and language filtering happens in Python, not SQL, because JSON
  containment is not portable between SQLite and Postgres. Bounded, and
  revisited when the expert count makes it matter.
- One currency per offering, and no conversion. An expert lists in the
  currency they charge in.
- No per-expert commission override; the platform rate applies to everyone.
