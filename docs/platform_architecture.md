# Platform Architecture — Automated, Expert and Hybrid

Astrofrekans is not only an automated astrology app. Every service can be
delivered three ways, and that distinction is a load-bearing part of the
backend rather than a label on a screen:

| Mode | Who delivers | Example |
| --- | --- | --- |
| `automated` | Engine + Astro AI, no human | Daily personalised horoscope |
| `expert` | A real astrologer in the app | 30-minute horary consultation |
| `hybrid` | Engine pre-analysis, expert consults on top | Synastry session where the astrologer opens a pre-computed report |

This document is the forward-compatible design. Phases B1-B3 are built; the
rest is specified here so the tables, enums and seams that later phases need
already exist or can be added without reshaping what is live.

---

## 1. Domains

```
Identity          users, credentials, sessions
UserProfile       display data, preferences, birth profiles, saved people
Astrology         engine, charts of every kind, aspects, moon
Forecast          daily / weekly / monthly / annual, transits
Horary            questions and the charts cast for them
Compatibility     synastry, composite, Davison
Divination        tarot, rune, katina
AstroAI           context builder, providers, conversations
Catalog           what can be sold or generated, and how
Experts           astrologer profiles, specialties, availability
Marketplace       expert services and search
Appointments      booking, rescheduling, cancellation
Messaging         conversations, messages, read state
Calls             audio/video sessions and their tokens
Media             attachments in object storage
Orders            service orders across all three fulfillment modes
Payments          providers, commission, refunds, payouts
Subscriptions     Astrofrekans Premium entitlements
Notifications     push events and preferences
History           everything the user has received
```

Each is a package under `app/services/` with its own repositories and (when it
has an HTTP surface) a router under `app/api/v1/`. Nothing reaches into
another domain's tables directly; they talk through services.

## 2. What is already built for the new scope

| Piece | Where | Why it had to be early |
| --- | --- | --- |
| `ChartSubject` + `Chart.kind` | `app/domain/astrology.py` | A horary chart is cast for the moment a **question** was asked, a solar return for the moment the Sun returns. Modelling "chart" as "birth chart" would have needed a rewrite later. |
| `chart_for()` / `horary_chart()` | `app/services/astrology/skyfield_engine.py` | One primitive serves natal, horary, return, relocation and event charts. |
| `house_rulers` | `Chart` | Horary judgement is almost entirely ruler-based (querent = ruler of house 1). |
| `charts` table with `chart_kind`, `moment_utc` | migration `0002` | One cache for every chart kind. Renaming a populated `natal_charts` table later would have been a data migration. |
| `service_definitions` + catalogue seed | `app/services/catalog/` | Orders, expert offerings and automated generators all reference a service. 28 services seeded, including the ones not shipped yet (`active=false`) so their codes are stable. |
| `Money`, commission split | `app/domain/marketplace.py` | Money is integer minor units, never floats; commission arrives in basis points from configuration, never hard-coded. |
| State vocabularies | `app/domain/marketplace.py` | Order, payment, appointment, call, message, payout and consent states are fixed now, because the client and the tables will speak them. |

## 3. Service catalogue

`GET /api/v1/services` returns the catalogue: what each service is, its
`fulfillment_modes`, and the `requires_*` flags the client uses to know what to
collect before an order can be created (birth data, partner data, a question).

Highlights of the seeded catalogue:

* Horary: `requires_question`, **not** `requires_birth_data`.
* Synastry / composite / Davison: `requires_partner_data`.
* Daily and weekly horoscopes: automated only, but still `requires_birth_data`
  — they are personalised from the user's chart, not sun-sign templates.
* Planned services (progressions, solar arc, profections, astrocartography,
  relocation, electional) are seeded inactive so their codes never change.

## 4. Personalised horoscope, not sun-sign text

The main product is the **personalised** horoscope. Inputs, all computed by the
engine before any language is generated:

```
natal chart + transits to natal + Moon (phase, sign, house) +
house activation + major aspects  →  structured forecast  →  Astro AI prose
```

Endpoints (B4): `/horoscope/daily`, `/horoscope/weekly`,
`/forecasts/monthly`, `/forecasts/yearly`. A generic sun-sign horoscope can be
added later as a separate, clearly-labelled service code; it is not the system.

`MonthlyForecast` and `AnnualForecast` are stored objects, not ephemeral text:
themes per life area, important and challenging dates, active transits, moon
events, retrogrades, house activations, and for the year additionally the solar
return chart and the major outer-planet transits. The AI writes about those
numbers; it never produces them.

## 5. Horary

A horary chart is cast for `asked_at` + the asker's coordinates. The backend
stores the exact timestamp (UTC plus the IANA zone), because re-deriving it
later would change the chart.

```
POST /api/v1/horary/questions              question + location + asked_at
GET  /api/v1/horary/questions/{id}         question + chart + rulers
POST /api/v1/horary/questions/{id}/automated-analysis
```

Re-asking is never blocked. The API flags a recent identical question
(`duplicate_suspected`) and the analysis raises `question_repeat_suspected`, so
the astrologer can follow the tradition of judging from the original chart -
a decision for a person, not for a database constraint.

Built in B5: the question store, the chart, and the full structured analysis
(significators, essential and accidental dignity, receptions, perfection and
obstruction factors, the Moon's condition, radicality warnings). See
[`horary_engine.md`](horary_engine.md).

## 6. Expert marketplace

```
experts                user_id, display name, bio, languages, specialties,
                       experience, rating, review_count, status, verified, timezone
expert_services        expert_id, service_definition_id, title, description,
                       delivery_type (chat|voice|video|written_report),
                       duration_minutes, price_minor + currency, active
expert_availability    expert_id, day_of_week, start_time, end_time, timezone
availability_exception  vacation | busy | manual_block, date range
appointments           user_id, expert_id, expert_service_id, scheduled_at (UTC),
                       timezone, duration, status, payment_status
reviews                appointment_id (unique), rating, comment
favorites              user_id, expert_id
```

An expert is a **role on a user account**, not a separate login: one `users`
table, an `experts` row when approved. Slots are generated in the expert's
timezone and returned as UTC instants plus the local rendering, so DST never
shifts a booking.

Search filters: specialty, language, rating, price range, available today,
online now.

## 6b. Compatibility (B5)

Synastry, composite and Davison are built and documented in
[`synastry_engine.md`](synastry_engine.md) and
[`composite_davison.md`](composite_davison.md). Two properties matter for the
marketplace phases:

* a `CompatibilityReport` is a **snapshot** - it stores the fingerprint of both
  people's birth data and the engine and scoring versions, so a report shown to
  an expert or paid for never changes underneath anyone,
* the score travels with `score_semantics` stating that it is an astrological
  factor index rather than a probability, which is what keeps a number next to
  two names from reading as a forecast.

The same structured result feeds all three fulfillment modes: automated (B6
prose), expert (the astrologer reads the factors), hybrid (pre-consultation
report).

## 6c. Astro AI (B6)

Astro AI is the interpretation layer of the **automated** fulfillment mode,
and the drafting aid behind **hybrid**. It is not a second astrologer.

- The engine computes; the AI explains. No astrological fact reaches a user
  that the B3-B5 engines did not produce and verify.
- Every specific statement cites the `factor_id`s it rests on, and the
  backend rejects any citation it did not supply. An interpretation can
  therefore be traced back to the transit card the app already shows.
- The model has no tools - no web, no shell, no database - so the context the
  backend assembled is the only material in scope.
- Automated reports are snapshots with their engine, context and prompt
  versions recorded, which is what makes them safe to sell, to keep, and
  later to hand to an expert.

Where it fits the three modes:

| Mode | Astro AI's role |
| --- | --- |
| automated | Produces the reading end to end, from engine output. |
| hybrid | Produces the draft an expert reviews before delivery. The expert's edits are the deliverable; the draft's provenance stays recorded. |
| expert | None. An expert's own words are the product. |

Deliberately outside B6: no marketplace, no expert chat, no voice or video, no
payments, no tarot, rune or katina, and no Flutter work.

## 6d. Divination (B7)

Tarot, Elder Futhark runes and Katina, behind one draw engine. Another
**automated** service, on the same boundary as the astrology layer: the
backend deals, the AI explains.

- The backend owns the deck, the randomness (OS CSPRNG), the orientation and
  the positions. The model cannot pick a card, flip an orientation or move an
  item - none of those has a factor id it is allowed to cite.
- Drawing and interpreting are separate endpoints, so a paid reading survives
  an AI outage. An AI failure costs an explanation, never the deal.
- A reading is an immutable snapshot with its deck, spread and meaning
  versions recorded - which is what makes it safe to sell and to keep.
- Provenance is stated rather than implied: every meaning and every spread
  says whether it is `traditional` or `product_defined`. All 65 Katina
  meanings and all 5 Katina spreads are product-defined, because no
  documented Katina tradition could be verified.

Deliberately outside B7: no marketplace, no expert involvement in readings, no
payments, no Flutter work, and no new imagery - the decks were built against
the already-audited production assets.

## 7. Hybrid consultations

The differentiator. Before a hybrid appointment starts, the system:

1. computes the charts involved (both charts for synastry, the question chart
   for horary, the solar return for an annual reading),
2. runs the same aspect/score engine the automated product uses,
3. asks Astro AI for a short pre-analysis,
4. attaches the result to the appointment as a **pre-consultation report**.

The astrologer opens that report in their panel; the user gets a human
consultation informed by it. Same pipeline for natal, horary, monthly and
annual work.

## 8. Expert access to user data — consent, not trust

An expert never gets the account. Each order or appointment carries explicit
consent scopes (`ConsentScope`): `share_birth_profile`, `share_natal_chart`,
`share_partner_profile`, `share_previous_readings`. Every expert-facing read
checks (a) that the expert is a party to that engagement, (b) that the scope
was granted, and (c) that the engagement is still in its access window. This is
authorisation logic in the service layer, and it gets its own tests —
"expert cannot read another user's chart" is a test case, not an assumption.

## 9. Messaging, calls and media (B9)

Built, and not the way section 9 originally planned it. The plan was a
WebSocket chat and S3-compatible storage; B9 uses Firebase instead, because the
client needed offline-tolerant realtime and presence with `onDisconnect`, and
neither is something a bespoke socket layer gets right cheaply.

**The governing rule: FastAPI + PostgreSQL is the source of truth. Firebase is
a transport and a credential.** No business foreign key points at a Firebase
uid, and no security rule decides a business question.

**Chat.** Clients read Firestore through a listener and write nothing; every
message goes through `POST /conversations/{id}/messages`. Firestore is the
canonical message store; Postgres holds authorisation, audit metadata,
attachments and counters. Chat exists because an order does - a user cannot open
a thread with an arbitrary astrologer - and eligibility comes from the order
state, the catalogue's `supports_chat` and the delivery type. `pending_payment`
is not writable. A completed consultation stays writable for a 30-day grace
period and then becomes read-only; history is never withdrawn. Backend-mediated
writes reduce the Firestore rules to "members may read, nobody writes", which is
small enough to be obviously right. See
[chat_architecture.md](chat_architecture.md).

**Presence and typing** live in Realtime Database, written by the client, because
`onDisconnect` can only be armed by a connected socket - the backend cannot know a
phone went into a tunnel. The backend writes two projections the rules consult:
membership per conversation, and presence visibility per user. There is
deliberately no endpoint that reads presence by uid. See
[presence.md](presence.md).

**Media** is Firebase Storage. Uploads go directly to a server-derived path
(`chat/{conversationId}/{attachmentId}/original.jpg`) after the backend
authorises them, then finalisation inspects the stored object - the claimed
content type is not the content type. SVG, HTML and executables are refused
whatever the allow-list says. No permanent public URL is ever issued. See
[media_attachments.md](media_attachments.md).

**Identity** is hybrid: the backend accepts both its own JWTs and Firebase ID
tokens, so existing accounts keep working. No backend JWT is minted for a
Firebase session. Adopting an existing account because a token carries a matching
email is off by default - it is an account-takeover primitive. See
[firebase_auth.md](firebase_auth.md).

**Calls** (B10) are LiveKit, behind a `RealtimeCommunicationProvider` seam.
FastAPI authorises and mints a short-lived join token; LiveKit carries the
media; Postgres holds `call_sessions`, `call_participants` and
`call_provider_events`. A call exists because a paid, scheduled order does,
and every token - including every reissue - re-runs the whole chain: membership,
order, expert, offering, payment, channel, appointment window, call state. One
live call per order is a partial unique index. Tokens are least-privilege: no
data channel, no admin grants, and `canPublishSources` limited to the call type
- an audio consultation cannot publish a camera, enforced by the LiveKit server.
Only provider webhooks (signature-verified, idempotent by event id, reconciled
against the room when they go missing) can make a call ACTIVE. Rooms and
identities are opaque random strings. No recording, no transcription, no media
through FastAPI. Incoming-call push reuses the B9 outbox. Verified against a
real local LiveKit 1.13.7. See [call_architecture.md](call_architecture.md).

## 10. Orders, payments, commission (B11)

Built - with one deliberate gap: no external payment provider is chosen.

**Classification decides the rail.** Store policy was verified on
2026-09-24 (Apple 3.1.1 / 3.1.3(d); Google Play Payments policy and its 1:1
exemption): digital content and subscriptions go through StoreKit / Play
Billing; live 1:1 voice/video with no replay may use an external provider;
chat and written expert reports fail closed as `REVIEW_REQUIRED` until someone
decides. A hybrid order is split into line items and payment groups, and the
digital part is never paid externally. See
[payment_architecture.md](payment_architecture.md).

**Stores.** Apple via Apple's own `app-store-server-library` (JWS verified to
Apple's roots; Server Notifications V2); Google via `subscriptionsv2` /
`productsv2`, acknowledge/consume after commit, RTDN as a pointer with the
purchase fetched from the Developer API. Entitlements derive only from
verified purchases; the B4 `subscriptions` table is reused as the tier
projection. See [store_billing.md](store_billing.md).

**External provider.** An abstraction with `disabled` (default) and a test
fake; Stripe/iyzico are not hardcoded. FastAPI never sees card data.

**Accounting.** Immutable `payment_transactions`, a double-entry per-currency
ledger that Postgres itself keeps balanced and append-only, B8's commission
snapshot carried through, expert pending → available after a configurable
hold (no default), admin-only payouts, and refunds where the policy advises
and a person decides. See [marketplace_settlement.md](marketplace_settlement.md)
and [refunds.md](refunds.md).

## 11. Notifications (B9)

Delivery is built, on FCM, through a transactional outbox.

`PushEvent` fixes the vocabulary in use: new chat message, appointment booked /
cancelled / reminder, order status changed, and since B10 incoming call, call
cancelled and call missed. The rest of the intended set - payment success or
failure, report ready, forecast ready, important transit, full and new moon -
reuses the same outbox and arrives with the phases that raise those events.

A request writes an outbox row in the same transaction as the business change and
returns; a worker (`python -m app.workers.notification_worker`) claims rows with
`FOR UPDATE SKIP LOCKED` and delivers them. So FCM being down never rolls back an
order somebody paid for, and `dedupe_key` being a unique constraint means one
event produces one notification however many times it is retried. Reminders are
scheduled outbox rows, which is why there is no separate scheduler: the worker's
"what is due" query is the scheduler.

**A payload carries an id and a generic line, never content.** A lock screen is a
public surface. No message body, no birth data, no horary question, no amount.
The app fetches the detail after the user opens it and has authenticated.

Device tokens are unique across the table (a shared handset moves rather than
duplicating), never returned to a client, never logged in the clear, and raw
device identifiers are stored only as a hash. A token FCM reports as dead is
retired rather than retried. See
[push_notifications.md](push_notifications.md).

Per-user, per-event-group preferences are still to come; today the granularity is
per device.

**Call pushes are their own transport (B12C.1).** Android: data-only,
HIGH-priority FCM with a TTL bound to B10's ring timeout, for ring, answered,
cancelled and missed. iOS: a separate PushKit VoIP credential
(`POST /devices/voip`) and direct APNs `voip` pushes for `incoming_call` only;
cancellation follows Apple's rule (no second push - the app ends the CallKit
call itself). One logical delivery per device, delivered at least once: a
per-device lease means a worker that dies mid-send is taken over, and the rare
duplicate is suppressed on the device by `call_id` + `event_version`. An
expired ring is skipped, never sent late. A push is a presentation hint, never
call authorisation. See [mobile_call_delivery.md](mobile_call_delivery.md).

## 12. Privacy

Birth date, birth time, birth location, private chat, uploaded images,
consultation history and partner data are the sensitive set. They are never
logged (the redaction processor drops them by key), never placed in query
strings, and never readable across users. Expert access is scoped by consent;
admin access is audited.

The same rule holds towards the AI provider. An AI context carries chart
*facts* and no identity: no name, email, birth date, birth time, birth place
or coordinates, and no saved-person name. Provider-side request metadata is
technical only (context type, versions, locale). The `ai_generations` table
records what a call cost - tokens, latency, model, status - and never the
prompt, the context or the answer. The provider API key lives in the server
environment alone and is never returned by any endpoint.

## 13. Phase plan

| Phase | Scope | State |
| --- | --- | --- |
| B1 | Bootstrap, config, logging, errors, DB, Redis, Docker, probes | done |
| B2 | Auth, users, birth profiles, saved people, geocoding, timezone | done |
| B3 | Astrology engine, natal chart, houses, aspects, moon phase | done |
| B3+ | Chart generalisation, horary primitive, service catalogue, money | done |
| B4 | Transits, cosmic calendar, daily/weekly/monthly/annual horoscope, solar return | done |
| B5 | Horary service, synastry, composite, Davison | done |
| B6 | Astro AI: context builder, providers, chat, automated reports | done |
| B7 | Tarot, rune, katina, draw engine and grounded interpretation | done |
| B8 | Expert marketplace, availability, appointments, orders, consent | done |
| B9 | Firebase auth, real-time chat, presence, storage, push | done |
| B10 | LiveKit voice and video calls, call lifecycle, webhooks | done |
| B11 | Payments, store billing, entitlements, ledger, settlement | done |
| B12 | Flutter production integration (Firebase, B5-B11 APIs, LiveKit, store billing, marketplace UI) | next |
| B13 | Notifications and background jobs (remaining) | planned |
