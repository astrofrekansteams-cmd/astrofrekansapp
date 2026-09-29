# Payment architecture

> **Policy last verified: 2026-09-24.** Store rules change. Re-read the
> sources below before relying on this document, and update
> `POLICY_LAST_VERIFIED` in `app/services/payments/classification.py` when you
> do.

## The three questions, kept apart

| Question | Answered by | Never answered by |
|---|---|---|
| What kind of thing is sold? | `PaymentClassificationService` | the checkout route, the client |
| Who may collect the money? | `PaymentRouter` | a hardcoded "we use provider X" |
| Where did the money go? | the ledger | a mutable `paid` flag |

Every payment bug in a marketplace comes from blurring two of these.

## Store policy, as verified

| Source | What it says (paraphrased) | Category |
|---|---|---|
| Apple App Review Guidelines **3.1.1** | Unlocking features, content, subscriptions in the app must use in-app purchase. | In-App Purchase |
| Apple **3.1.3(d)** Person-to-Person Services | Real-time person-to-person services *between two individuals* may use other purchase methods; one-to-few / one-to-many must use IAP. | Other Purchase Methods |
| Google Play **Payments policy** | Digital items, subscriptions and app functionality must use Play billing; physical goods/services are exempt. | Payments |
| Google Play, *Understanding the Payments policy* | A **1:1 online paid service** is exempt if it is between two individuals **and not available for replay afterwards** (not recorded, cannot be accessed again). | 1:1 online paid services |

Sources:
<https://developer.apple.com/app-store/review/guidelines/> ·
<https://support.google.com/googleplay/android-developer/answer/9858738> ·
<https://support.google.com/googleplay/android-developer/answer/10281818>

## Classification

| Class | Meaning | Rail |
|---|---|---|
| `DIGITAL_STORE` | digital content or functionality used in the app | App Store on iOS, Google Play on Android, nothing on the web |
| `LIVE_PERSON_TO_PERSON` | real-time, exactly two people, never replayable | external marketplace provider |
| `REVIEW_REQUIRED` | not clearly either | **nothing** - fail closed |
| `FREE` | nothing to collect | - |

Rules, in `classify_expert_session`:

* voice or video, 1:1, not replayable → `LIVE_PERSON_TO_PERSON`
* more than two participants → `REVIEW_REQUIRED`
* **replayable → `REVIEW_REQUIRED`.** Replayability is read from the schema:
  if B10's `ck_call_sessions_no_recording` constraint is ever removed to allow
  recording, every live session reclassifies automatically.
* chat → `REVIEW_REQUIRED` (asynchronous, history persists)
* written report → `REVIEW_REQUIRED` (a delivered artefact)
* anything else → `REVIEW_REQUIRED`

## Policy matrix

| Service | Classification | iOS rail | Android rail | Reason | Review required |
|---|---|---|---|---|---|
| Premium subscription | digital | StoreKit | Play Billing | subscription unlocking functionality | no |
| Automated natal / transit / forecast report | digital | StoreKit | Play Billing | digital content used in app | no |
| AI synastry / horary / tarot / rune / katina | digital | StoreKit | Play Billing | digital content used in app | no |
| Live 1:1 voice consultation (not recorded) | live P2P | external eligible | external eligible | Apple 3.1.3(d); Google 1:1 exemption | no |
| Live 1:1 video consultation (not recorded) | live P2P | external eligible | external eligible | Apple 3.1.3(d); Google 1:1 exemption | no |
| Expert text chat | review required | TBD | TBD | asynchronous, persistent | **yes** |
| Written expert report | review required | TBD | TBD | delivered, re-readable | **yes** |
| Hybrid: AI pre-analysis + live video | split | StoreKit + external | Play Billing + external | two line items, two classes | **yes** (policy review of the bundle) |
| Any live session if recording enabled | review required | TBD | TBD | replay breaks Google's exemption | **yes** |

`last_verified_at`: 2026-09-24. The same matrix is `POLICY_MATRIX` in code.

**Region-specific alternative billing** (store-approved external payment for
digital goods in some countries) is **not** assumed anywhere. Supporting one
is an entry in `PaymentRouter.ALTERNATIVE_PROGRAMMES`, keyed by store and
storefront, after the programme's terms are accepted.

## Hybrid orders

A hybrid order is two line items in two payment groups:

```
AI pre-analysis        DIGITAL_STORE           -> store group (a store credit)
45 min live video      LIVE_PERSON_TO_PERSON   -> external group
```

The digital line is **never** paid externally. If no store product is
configured for it, the line is `excluded` - not sold, not delivered - rather
than bundled into the external payment. The order is paid only when every
group is satisfied.

## Flows

**Digital:** device buys with StoreKit / Play Billing → `POST
/billing/{apple,google}/verify` → store verification → purchase attached to
this account → entitlement derived → (Google) acknowledge/consume **after**
commit. See [store_billing.md](store_billing.md).

**Live 1:1:** `POST /orders/{id}/payment` `method=external` → payment intent →
provider checkout hand-off → the provider's **signed webhook** marks it paid →
ledger → order confirmed. See [marketplace_settlement.md](marketplace_settlement.md).

No endpoint accepts "paid" from a client.

## PCI boundary

FastAPI never receives a card number, CVV, expiry or card form. Stores handle
their own payment UI. The external provider, when chosen, must tokenise on its
own hosted page or native SDK; the backend receives an opaque reference and a
signed webhook. This keeps the backend out of card-data scope. The
`ExternalMarketplacePaymentProvider` contract has no method that takes card
data.

## No provider is chosen

`EXTERNAL_PAYMENT_PROVIDER=disabled` by default. Stripe, iyzico and others are
**not** hardcoded; the choice (fees, payouts in the expert's country, merchant
of record, onboarding) is a business decision. Checkout answers `503
external_payment_provider_not_configured` until then.

## Tax

Not calculated. Line items carry `tax_amount_minor` and `tax_source` as a
seam; no rate is invented. Stores act as merchant of record for their sales in
many jurisdictions; the external marketplace's tax obligations depend on the
provider and the country. **NOT VERIFIED - a legal/business decision.**

## Currency

Every amount is integer minor units plus ISO-4217. Store purchases take their
currency from the store transaction; expert sessions from the B8 order
snapshot. Balances are per currency; no journal mixes currencies; nothing
converts.

## Logging

Logged: payment/order/user/purchase ids, provider, product code, status.
Never: purchase tokens, App Store JWS, webhook bodies, credentials, card or
billing details, Firebase tokens. There is a test for it.

## Related

[store_billing.md](store_billing.md) ·
[apple_storekit_backend.md](apple_storekit_backend.md) ·
[google_play_billing_backend.md](google_play_billing_backend.md) ·
[marketplace_settlement.md](marketplace_settlement.md) ·
[refunds.md](refunds.md)
