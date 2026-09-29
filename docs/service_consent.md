# Service Consent

The whole of expert access to user data.

## The rule

**Being an expert grants nothing.**

An expert sees a user's chart only when that user granted that scope, on that
order, and has not revoked it. There is no path in this codebase that reads a
user's material for an expert without finding a live consent row first, and
"they are the expert on this order, so they can see it" is not a rule this
system has.

That is why consent is a table and not a boolean on the order.

## Per order, not per account

A user who shared their natal chart for a career reading in March has not
shared it for a synastry reading in June. Scoping consent to the account would
make "I just wanted help with one thing" impossible to express.

```
service_consents: order_id, user_id, expert_id, scope, granted_at, revoked_at
UNIQUE (order_id, scope)
```

Tested: granting on one order leaves a second order with the same expert
showing no scopes at all.

## Scopes

| Scope | Covers |
| --- | --- |
| `share_birth_profile` | The user's own birth data |
| `share_natal_chart` | A computed chart |
| `share_partner_profile` | A saved person's data |
| `share_synastry` | A compatibility report |
| `share_horary` | A horary question and its analysis |
| `share_forecast` | Forecast output |
| `share_divination_reading` | A tarot, rune or Katina reading |
| `share_previous_readings` | Stored AI reports |

Each source kind maps to exactly one scope. An expert asking to read a
compatibility report needs `share_synastry`, not a general "birth data" grant
— otherwise one tick would open everything.

## Only the user grants

The routes make this structural rather than something a reviewer has to
notice:

```
GET /orders/{id}/consents      the user's own order
PUT /orders/{id}/consents      the user's own order
```

Both are scoped to the caller's own orders, so an expert calling them gets a
`404` — the order is not theirs. There is no expert-facing write path for
consent anywhere, and `assert_expert_cannot_grant` exists as a named guard for
any future one.

## PUT, not toggles

`PUT /orders/{id}/consents` takes the **complete set** of scopes the user is
comfortable sharing. Anything absent is revoked.

```json
{"scopes": ["share_birth_profile", "share_natal_chart"]}
```

A pair of grant/revoke toggles would make "share less than before" several
actions and leave the user unsure what the current state is. A complete set
makes it one obvious action, and the response returns every scope with its
`active` flag so the user can see exactly where they stand.

Re-granting a revoked scope starts a fresh grant: `granted_at` moves and
`revoked_at` clears.

## Revocation is forward-looking

Revoking sets `revoked_at` rather than deleting the row. A user needs to see
what they once granted, and an auditor needs to see when it ended.

It stops **future** reads immediately: the expert order view flips
`readable` to `false` and `granted_consent_scopes` empties, tested end to end.

It **cannot un-see** what an expert already read during a consultation. This
document says so rather than implying otherwise, because the alternative is a
promise the software cannot keep.

## Consent dies with the engagement

`has_consent` joins the order and requires it to be in a live state. A
`cancelled`, `refunded`, `failed` or `draft` order does not carry live
consent, whatever its rows say — an engagement that ended is not an engagement.

## A reference is not permission

`service_order_sources` records what an order is *about*. That row tells an
expert a source exists; it does not let them read it.

`readable_sources()` is the filter that turns a reference list into an access
list, and every expert-facing read must go through it. The expert order view
marks each source:

```json
{"source_kind": "birth_profile", "source_id": "…", "readable": false}
```

Tested: with the source attached and no consent, `readable` is `false` and
`granted_consent_scopes` is empty. After granting, `readable` becomes `true`.
After revoking, it returns to `false`.

## What this phase does not decide

**Expert notes.** A practitioner will want to keep their own notes from a
consultation. That raises a question this phase cannot answer honestly: notes
an expert wrote are arguably *their* professional record, and notes about a
user's life are arguably the user's data. Revocation would mean different
things for each.

`ExpertServiceNote` was considered and deliberately **not built**. A table
first and a retention policy afterwards would mean personal notes accumulating
under rules nobody agreed to. What is needed first:

* Who owns a note — the expert, the user, or both?
* Does revoking consent delete, redact or freeze it?
* Does a completed deliverable survive revocation? (It probably must: a user
  who paid for a written report should keep it.)
* How long is any of it retained?

**Deliverables.** Same question, narrower. A report an expert wrote and
delivered is something the user bought. Revoking access to the *inputs* should
not destroy the *output* — but that needs stating as policy, not inferring
from an implementation.

Both are recorded here as open, which is the honest state.

## Privacy in logs

Consent events log ids and the scope name, never content:

```
consent_granted  order_id=… expert_id=… scope=share_birth_profile
consent_revoked  order_id=… scope=share_birth_profile
consent_denied   order_id=… expert_id=… scope=share_natal_chart
```

Never logged: the data behind a scope, birth details, or any consent payload
beyond the scope identifiers.

## Known limitations

- Revocation cannot undo a read that already happened.
- No consent expiry. A grant lasts until it is revoked or the order leaves a
  live state; a time-boxed grant ("for the next 48 hours") is not modelled.
- No audit trail of expert *reads*. The system records what was permitted, not
  what was looked at.
- No user-facing "everything I have shared, across all orders" view. Consent
  is listed per order, which is correct but not convenient.
- Expert notes and deliverable retention are undecided, as above.
