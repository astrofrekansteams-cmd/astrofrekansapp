# Marketplace Architecture (B8)

Expert profiles, offerings, availability, appointments and orders.

## The two invariants

Everything in this phase is shaped by two rules.

**An expert never gets access to an account.** They get exactly the consent
scopes a user granted, for exactly one order, checked on every read. There is
no "they are the expert on this order, so they can see the chart" path
anywhere in the code — which is why consent is a table rather than a boolean.
See `service_consent.md`.

**A slot belongs to one appointment.** Two people booking the same minute
costs an expert their morning and a user their trust. It is prevented in
Postgres with an exclusion constraint over a time range, not by an
application-level check that a race walks straight through. See
`appointments.md`.

## The chain

```
User
 └─ ServiceDefinition        the catalogue (B3+), source of truth
     └─ ExpertService        an expert's priced version of it
         └─ Expert           the practitioner
             ├─ ExpertAvailability (+ exceptions)
             │   └─ generated slots
             │       ├─ SlotHold        brief claim while ordering
             │       └─ Appointment     the booking
             └─ ServiceOrder            what was bought, on what terms
                 ├─ ServiceOrderSource  what it is about
                 ├─ ServiceConsent      what the expert may read
                 └─ ExpertReview         after completion
```

The catalogue was built in B3+ and is **reused, not replaced**. There is no
second "service types" table. An offering references a `service_definitions`
row and may only narrow what it allows.

## Fulfilment modes

| Mode | Who delivers | Order shape |
| --- | --- | --- |
| `automated` | engine + Astro AI | no expert, no appointment |
| `expert` | a practitioner | expert service, usually an appointment |
| `hybrid` | engine pre-analysis, expert consultation on top | expert service plus source references |

A hybrid order is the interesting one. It carries `ServiceOrderSource` rows
pointing at material the platform already produced — a chart, a compatibility
report, a horary question, a divination reading, an AI report — so an expert
walks into the consultation with the analysis already done. This phase does
not trigger that generation automatically; the linkage exists and is
authorised, and wiring the trigger is a later decision.

`preconsultation_report_id` on the order is the slot for a generated AI
briefing. Nothing writes it yet.

## The catalogue is the source of truth

An `ExpertService` may narrow what a `ServiceDefinition` allows. It can never
widen it:

* A definition whose `fulfillment_modes` are automated-only cannot be offered
  by an expert at all.
* A definition with `supports_video = false` cannot be sold as a video
  consultation.
* `requires_birth_data`, `requires_partner_data` and `requires_question` come
  from the definition. An offering does not override them, because an expert
  deciding their version of synastry needs no partner data would break every
  client that collects inputs from those flags.

Effective channel capability is the **intersection**: the definition supports
it *and* the offering is sold through it. A definition losing video support
removes the button immediately, without an expert editing anything.

## Money

Integer minor units and an ISO-4217 code, everywhere. `Money(1999, "TRY")` is
19.99 lira. No float ever touches an amount, no amount is stored as a
formatted string, and formatting is the client's job.

Commission arrives in basis points from configuration
(`MARKETPLACE_COMMISSION_BPS`, 10000 bp = 100%) and is never a literal in
business logic. The split is integer arithmetic and **rounding favours the
expert**: the platform fee truncates, the remainder is theirs. `999` at 2000 bp
is a fee of 199 and a net of 800 — nothing is lost or invented.

See `orders.md` for the price snapshot.

## Expert lifecycle

```
draft ─┐
       ├─► pending_review ──(moderation)──► active ──► paused / inactive
       │                                       │
       └───────────────────────────────────────┴──► suspended (moderation)
```

Only `active` is discoverable. A user may move their own profile between
`draft`, `pending_review`, `paused` and `inactive`; `active` and `suspended`
are moderation decisions, and `verified` is one too.

There is **no route** that activates or verifies. `approve`, `verify`,
`suspend` and `reactivate` exist as service methods for a future admin
surface. An applicant who can publish themselves is not an applicant, and the
API refuses it with a `403` rather than relying on a reviewer noticing.

A profile that is not `active` is a `404` even by direct id: the status of
somebody's application is not public information.

## Search

`GET /experts` returns active profiles with mandatory pagination. Filters:
specialty, language, service code, delivery type, price range, currency,
verified, minimum rating. Sorts: rating, review count, price, experience,
newest.

Results carry the shop front — display name, headline, languages, specialties,
ratings, a "from" price — and nothing from the underlying `users` row. No
email, no real name, no birth data.

Free text (`q`: name, headline, bio, specialty names in Turkish or English),
specialty, language and "available today" are filtered in Python rather than
in SQL, because JSON containment and Turkish case-folding are not portable
between SQLite (tests) and Postgres (production).

**Technical debt (Phase 3).** The candidate set used to be capped at 500
experts, which silently dropped every match that sorted after the 500th - a
test with 521 experts proved it. The cap was replaced by a batched scan to the
end of the active experts (`SEARCH_SCAN_BATCH = 500` per query), so results are
now correct at any size, and every sort ends with `Expert.id` so page
boundaries are stable. The cost is linear in the number of active experts on
each filtered search. When that number grows into the thousands, move `q` to
Postgres full-text search (a `tsvector` over name/headline/bio with a
`simple`+unaccent configuration) and specialty/language to `jsonb` containment
with GIN indexes; unfiltered searches already page in SQL.

## Ratings

`rating_average` and `rating_count` on the expert are a **cache**. Reviews are
the source of truth, and the aggregate is *recomputed* from them rather than
incremented — an increment loses one update under concurrency and the cached
number quietly stops matching the rows it claims to summarise.

Float is fine here and would not be for money: a rating is a display value
with no arithmetic downstream.

## Rate limits

Separate buckets, keyed by user:

| Scope | Default | Why |
| --- | --- | --- |
| `marketplace_search` | 120/hour | Cheap reads, browsed often |
| `expert_mutation` | 60/hour | Profile and offering edits |
| `appointment_booking` | 20/hour | Writes that hold real time |
| `order_create` | 30/hour | Writes that will involve money |
| `review_create` | 10/hour | The abuse surface |

## What this phase deliberately does not do

- **No payment provider.** `payment_status` is a real typed state and priced
  orders sit at `pending_payment`. Nothing marks a priced order paid; mocking
  it would produce a flow that works in development and fails the first time
  money is involved. The boundary is `orders.md`.
- **No chat, voice or video.** `conversation_id` and `call_session_id` columns
  exist on orders and appointments so the later phase is an insert rather than
  a migration. Nothing writes them. No LiveKit dependency was added.
- **No Firebase.** Not touched.
- **No admin surface.** The moderation transitions exist; the routes do not.
- **No refund policy.** Cancellation records *who* cancelled
  (`CancellationActor`) and why, because that is what a refund rule will need
  and it is only knowable at the time. No amount is computed.
- **No expert notes.** `ExpertServiceNote` was considered and not built — see
  `service_consent.md` for why it needs a retention decision before it needs a
  table.

## Related documents

- `expert_services.md` — profiles, offerings, catalogue validation
- `appointments.md` — availability, slots, DST, double booking
- `orders.md` — state machine, price snapshot, commission, idempotency
- `service_consent.md` — the whole of expert data access
- `api_contracts.md` — request and response shapes
