# Service Orders

What a user bought, on what terms, and what happened to it.

## The price is frozen

An order stores its own amounts, its own commission split, and its own copy of
the service title and duration. Reading the price back through
`expert_services` would be a live number wearing a historical label: an expert
raising their rate tomorrow would appear to have charged more yesterday.

```
subtotal_minor, discount_minor, total_minor, currency
commission_basis_points, platform_fee_minor, expert_net_minor
service_title, service_duration_minutes
```

Tested end to end: an order placed at 10000 still reads 10000 after the
offering moves to 15000, and the next order reads 15000.

## Money and commission

Integer minor units throughout. `Money(1999, "TRY")` is 19.99 lira. No float
touches an amount.

Commission arrives in basis points from `MARKETPLACE_COMMISSION_BPS`
(10000 bp = 100%; default 2000 = 20%) and is never a literal in business
logic. The split is integer arithmetic, and **rounding favours the expert**:

```python
Money(10000, "TRY").split_commission(2000)  # fee 2000, net 8000
Money(999,   "TRY").split_commission(2000)  # fee 199,  net 800
```

The fee truncates and the remainder is the expert's, so `fee + net == gross`
exactly. Nothing is lost to rounding and nothing is invented.

The rate is snapshotted onto the order. Changing the configured rate does not
rewrite what an expert was owed on work already sold.

## Order lifecycle

```
draft
  └─► pending_payment ──(payment)──► paid ──► confirmed
  └─► confirmed                                  │
        │                                        ▼
        ├─► pending / calculating / generating  (automated stages)
        ├─► awaiting_expert ──► in_progress ──► completed
        ├─► cancelled
        ├─► refunded
        └─► failed
```

Automated stages and expert stages share one enum because a **hybrid** order
passes through both: the engine prepares an analysis, then a practitioner
delivers the consultation on top of it.

Terminal states are `completed`, `cancelled`, `refunded` and `failed`. A
terminal order cannot be cancelled or completed again (`409
order_not_cancellable`).

## Payment is a separate state

| Payment status | Meaning |
| --- | --- |
| `not_required` | A free service. Nothing to collect |
| `pending` | Waiting for a verified payment |
| `authorized` | Held, not captured |
| `paid` | A provider or store verified it |
| `failed` | The attempt failed |
| `refund_pending` | A paid order was cancelled; a refund awaits review (B11) |
| `refunded` / `partially_refunded` | A provider said the money went back |

Kept separate from order state on purpose. An order can be `confirmed` while
payment is `not_required`, or `cancelled` while payment is `paid` and a refund
is owed. Collapsing the two would lose exactly the cases that matter.

A **free** offering (`price_minor == 0`) skips the whole question: the order
is created `confirmed` with payment `not_required`.

### Line items and payment groups (B11)

Every order is split into line items, each classified for store policy
(`payment_classification`) and assigned a rail, and the lines are grouped by
rail:

| Group | Satisfied by |
| --- | --- |
| `live_person_to_person` (external) | the external provider's signed webhook |
| `digital_store` (store) | a verified StoreKit / Play credit, consumed for this order |
| `review_required` | nothing - `blocked_review`, payment refused with `payment_policy_review_required` |

`OrderPaymentService.evaluate()` is the only transition from
`pending_payment` to paid: every group satisfied or not required → `paid` +
`confirmed` (automated orders: `pending`), appointment confirmed,
`payment_succeeded` pushed. No endpoint accepts "paid" from a client.

An automated order stays free (as B8 made it) unless a store product is
configured for its service; then it waits for a store credit.

Endpoints: `GET /orders/{id}/payment`, `POST /orders/{id}/payment`
(`external` or `store_credit`), `POST|GET /orders/{id}/refund-requests`. See
[payment_architecture.md](payment_architecture.md).

**No external provider is configured yet**, so a priced live consultation
answers `external_payment_provider_not_configured` at checkout and stays
`pending_payment` - B10 therefore refuses its calls, which is correct.

## Order and appointment are one transaction

`POST /orders` creates the order and, for a service delivered by appointment,
books the slot in the same transaction. Either both exist or neither does.

An order pointing at a booking that does not exist, or an appointment with no
order, are both worse than a clean error. The service layer builds both and
the route commits once.

If the service supports appointments and no `starts_at_utc` is given, the
request is `422` rather than producing an order nobody can attend.

## Idempotency

A mobile client on a flaky connection retries. Without protection, a retry
books a second appointment and charges twice for one intention.

Send `Idempotency-Key`:

* **Same user, same key, same service** → the original order is returned. No
  second booking.
* **Same user, same key, different service** → `409 idempotency_conflict`.
  That is a client bug, and silently returning the wrong order would hide it.

Enforced by `uq_service_orders_idempotency (user_id, idempotency_key)` as well
as by the replay lookup, so a race cannot slip a duplicate past.

## Sources: what an order is about

A hybrid consultation usually builds on work the platform already produced.
`service_order_sources` is one typed table rather than a nullable column per
kind:

```
birth_profile, saved_person, chart, compatibility_report,
horary_question, divination_reading, ai_report
```

Adding a new source kind is a new enum value, not a migration.

**Ownership is verified.** An order may only reference the ordering user's own
material — referencing a stranger's chart returns `404 source_not_found`
(never 403, which would confirm it exists).

**A reference is not an access grant.** An expert seeing that a source exists
is not the same as being allowed to read it; that still needs consent. The
expert order view marks each source `readable: true | false` accordingly.

`preconsultation_report_id` is the slot for a generated AI briefing. Nothing
writes it in this phase.

## Cancellation

```json
POST /orders/{id}/cancel  {"reason": "Changed my mind"}
```

Cancels the order and any live appointment with it, and records:

| Actor | Meaning |
| --- | --- |
| `user` | the client |
| `expert` | the practitioner |
| `admin` | moderation |
| `system` | automated |
| `technical_failure` | the platform's fault |

`payment_status` deliberately keeps its value. An order cancelled while
payment is `paid` means a refund is owed, and overwriting that to `refunded`
would claim money moved when nothing did.

**No refund amount is computed.** Refund policy needs the actor, the notice
period and the service — the actor and the timing are captured here, when they
are knowable; the policy is a later decision.

## Cancellation: one path (Phase 1)

`POST /orders/{id}/cancel`, `POST /appointments/{id}/cancel` and
`POST /expert/appointments/{id}/cancel` all go through
`services/marketplace/cancellation.py`. An appointment that belongs to an
order cancels **the order**, so the door does not change the money:

1. the order row is locked (Postgres); calls stop; the appointment is
   cancelled and both parties notified;
2. open payment intents (`created`/`pending`/`authorized`) are closed;
3. a paid order becomes `refund_pending` with **one** refund request
   (`idempotency_key = cancel:{order_id}`, status `manual_review`). If a
   refund request already covers the payment, none is added; if it covers
   part, the rest is requested;
4. a payment that arrives after cancellation is recorded and opens the same
   refund review.

Repeating a cancel returns the cancelled order unchanged (`200`), never a
second refund. Another terminal state (`completed`) is still `409
order_not_cancellable`. A denied refund returns `payment_status` to `paid`.

## Completion (Phase 1)

`services/marketplace/completion.py` decides when `OrderService.complete`
may run:

| Service | Who | When |
| --- | --- | --- |
| Live (`chat`/`voice`/`video`) | `POST /orders/{id}/complete` (user) or `POST /expert/orders/{id}/complete` | paid or free, not terminal, appointment live and its start time passed |
| Written (`written_report`) | `POST /expert/orders/{id}/deliver` with the analysis text | paid or free, not terminal |

Ending a call still never completes anything. Completion opens the review and
calls `SettlementService.release_order`, which releases the expert's share only
once `EXPERT_SETTLEMENT_HOLD_DAYS` is set and has passed.

## Read model (Phase 1)

`OrderResponse` adds derived, never-stored fields: `lifecycle` (`pending`,
`paid`, `scheduled`, `awaiting_completion`, `completed`, `cancelled`,
`refund_review`, `refunded`), `actions` (`can_cancel`, `can_complete`,
`can_deliver`, `review_eligible`), `completion_block`, the latest `refund`,
`cancellation` (what cancelling now would mean for money), `delivery` and a
`timeline` assembled from existing timestamps. `OrderSummary` carries
`lifecycle`.

`POST /orders` accepts `selected_local_date` + `selected_utc_offset_minutes`;
a slot not on that local day is `422 slot_date_mismatch`.

## Ownership

| Resource | Owner | Owning expert | Other user | Other expert |
| --- | --- | --- | --- | --- |
| `GET /orders/{id}` | ✅ | ❌ 404 | ❌ 404 | ❌ 404 |
| `GET /expert/orders/{id}` | ❌ 404 | ✅ | ❌ 404 | ❌ 404 |
| `POST /orders/{id}/cancel` | ✅ | ❌ 404 | ❌ 404 | ❌ 404 |
| `PUT /orders/{id}/consents` | ✅ | ❌ 404 | ❌ 404 | ❌ 404 |
| `POST /orders/{id}/review` | ✅ | ❌ 404 | ❌ 404 | ❌ 404 |

Always `404`, never `403`: a wrong guess must not confirm that a row exists.

## Reviews

A review is anchored to a transaction, because a rating anybody can leave
about anybody is free to manufacture.

* The order must be the caller's, must have an expert, and must be
  `completed` → otherwise `409 review_not_allowed`.
* **One review per order**, enforced by `uq_review_order`.
* An expert cannot review their own service (`self_review`).
* Rating is an integer 1–5; anything else is `422`.

`rating_average` and `rating_count` on the expert are **recomputed** from the
reviews after every change — not incremented. An increment loses one update
under concurrency and the cached number quietly stops matching the rows it
summarises. Deleting a review updates the aggregate the same way.

## Privacy in logs

An order log line carries ids and structure, never content:

```
order_created  order_id=… user_id=… expert_id=… fulfillment_mode=expert
               total_minor=10000 currency=TRY status=pending_payment
```

Never logged: the `notes` field, birth data, consent payloads, payment
details. Tested: booking with a note containing a birth date and a city
produces a log line with neither.

## Known limitations

- No production external payment provider (only `fake` for tests and
  `disabled`): live 1:1 sessions cannot be collected in production yet.
- No refund calculation and no cancellation-window policy: every cancellation
  refund is a manual review.
- Automated orders carry no price. Pricing for those arrives with
  subscriptions and entitlements; an order with a made-up amount would be
  worse than one with none.
- No discount or coupon mechanism; `discount_minor` exists and is always 0.
- No payout: `expert_net_minor` is recorded per order, but there is no
  balance, no payout run and no provider.
- No dispute step after completion, and no automatic completion after a
  session's end time: a session nobody marks completed stays
  `awaiting_completion`.
- No invoices, receipts or tax handling.
