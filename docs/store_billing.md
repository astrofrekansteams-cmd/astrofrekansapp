# Store billing: purchases and entitlements

## Source of truth

```
store_purchases    facts the store verified          (written only after verification)
      ↓
user_entitlements  what those facts grant            (derived, idempotently)
      ↓
subscriptions      the tier projection User.tier reads (the B4 table, reused)
```

The client's "purchase successful" writes none of them. The B4 `subscriptions`
table is kept and reused as the projection, so every existing `User.tier`
check - including `require_premium` - now follows verified entitlements
without being rewritten.

## Catalogue

`store_products`: `code`, `product_type` (consumable / non_consumable /
subscription), `entitlement_code`, `apple_product_id`, `google_product_id`,
`active`. **No price** - the stores own prices per storefront; the client
shows StoreKit's / Play's localised price.

Codes are in code (`app/services/payments/catalog.py`); store product ids are
configuration (`STORE_PRODUCT_IDS` JSON), because they are App Store Connect /
Play Console decisions. A code with no id on a store is not sold there.
`GET /billing/products?platform=ios|android` lists what is.

| Code | Type | Entitlement |
|---|---|---|
| `premium_monthly`, `premium_yearly` | subscription | `premium` |
| `natal_report` | consumable | `natal_report_credit` |
| `synastry_report` | consumable | `synastry_report_credit` |
| `annual_forecast_report` | consumable | `annual_forecast_credit` |
| `ai_pre_analysis` | consumable | `pre_analysis_credit` (the hybrid digital line) |

No virtual currency. A credit is one unit of one consumable, used once.

## Verification

`POST /billing/apple/verify` `{product_code, signed_transaction | transaction_id}`
`POST /billing/google/verify` `{product_code, purchase_token}`

Checked, in order: the store's signature / API answer → environment → the
store's product id maps to a catalogue product **and** equals the requested
code (`product_mismatch` otherwise: a cheap purchase cannot unlock a dear one)
→ the account the app stamped on the purchase (`appAccountToken` /
`obfuscatedAccountId`) is this account (`purchase_account_mismatch`) → the
purchase is not already another account's (`purchase_owned_by_another_account`).

Get the stamps from `GET /billing/account-tokens` and pass them to StoreKit /
Play Billing at purchase time.

## Ownership

`store_purchases` is unique on `(provider, purchase_key)`:

* Apple subscription → `originalTransactionId` (renewals keep it)
* Apple one-time → `transactionId`
* Google → SHA-256 of the purchase token

A purchase is never moved between accounts. Firebase account linking (B9)
has nothing to do with purchase ownership.

## Idempotency and races

`apply()` is the single write path for client verification, restore, Apple
notifications and Google RTDN. The purchase row is locked `FOR UPDATE`;
entitlements are unique per `(purchase, unit)`; charges per `(provider, store
transaction id, type)`; ledger journals per key. Proven on Postgres
(`scripts/payment_concurrency_check.py`): 10 concurrent verifications → 1
purchase, 1 entitlement, 1 charge, 1 journal; 5 verifications racing 5 App
Store notifications → the same.

## State mapping

| Normalised | Apple | Google (subscriptionsv2) | Access |
|---|---|---|---|
| `active` | status 1 / not expired | `ACTIVE` | yes |
| `cancelled_pending_expiry` | auto-renew off, not expired | `CANCELED`, expiry in future | **yes, until expiry** |
| `grace_period` | status 4 / billing retry with grace date | `IN_GRACE_PERIOD` | yes (`PREMIUM_DURING_GRACE_PERIOD`, default true) |
| `on_hold` | status 3 / billing retry without grace | `ON_HOLD` | no |
| `paused` | - | `PAUSED` | no |
| `expired` | status 2 / past `expiresDate` | `EXPIRED`, `CANCELED` past expiry | no |
| `revoked` | `revocationDate` set / status 5 / `REFUND`, `REVOKE` | voided purchase notification | no |
| `pending` | - | `PENDING`, `UNSPECIFIED` | **never entitles** |
| `cancelled` | - | `PENDING_PURCHASE_CANCELED`; one-time `CANCELLED` | no |

Cancelling does not revoke: a cancelled subscription is paid up to its expiry.
Grace follows both stores' intent (access continues while payment is retried)
and is one setting if the business decides otherwise.

A refund is never undone by a stale client verification; only Apple's
`REFUND_REVERSED` may restore a revoked purchase.

## Consumables

```
purchase → verify → credit → POST /ai/reports {report_type, consumer_ref}
         → [one transaction] credit RESERVED + durable job
         → generation → [one commit] report completed + credit CONSUMED
```

Paid reports spend their credit themselves (see `api_contracts.md` →
"Paid reports"). The client never calls a separate consume step for them, and
`POST /billing/credits/consume` refuses report credits
(`credit_reserved_for_reports`) so an older client cannot pay twice. A
reserved credit is not available to anything else; a refund revokes it like
any unused credit, and the report is then not delivered.

`POST /billing/credits/consume` remains for other credits
(`pre_analysis_credit`). Consumption is idempotent per `consumer_ref`: a
network retry gets the same credit back. On Postgres, concurrent
consumers of the same reference are serialised with a transaction-scoped
advisory lock (found by the concurrency check: without it, nine of ten
retries were told "no credit" while the first was still committing).

A refunded consumable revokes unused credits; a credit already used stays
consumed (the report exists) and the purchase row shows the refund.

## Restore

`POST /billing/reconcile` `{apple: [...], google: [...]}` - what StoreKit's
current entitlements / Play's `queryPurchasesAsync` report on the device,
re-verified one by one. Rate-limited (`billing_reconcile`). Each item
succeeds or fails independently.

## Entitlements endpoint

`GET /billing/entitlements` → tier, premium, expiry, unused credits per code,
capabilities, and each entitlement with an `active` flag computed by
`EntitlementPolicyService`. Never a JWS or token. Not cached: webhooks change
entitlements at any moment and a cached "premium" would outlive a refund.

## Capabilities and tiers

`EntitlementPolicyService.capabilities(tier)` is the one place premium's
contents are defined. AI quotas use `TieredUserRateLimit` (the B6 seam): the
premium quota is `AI_CHAT_RATE_LIMIT_PREMIUM` / `AI_REPORT_RATE_LIMIT_PREMIUM`,
**unset by default** - the product has not chosen numbers, so premium gets the
free quota until it does.

## Completion semantics

* **Google:** acknowledge (subscriptions, non-consumables) or consume
  (consumables) within 3 days or Google refunds. Done **after** our commit; a
  failure is retried by the next verify, restore or RTDN. Never for PENDING.
* **Apple:** StoreKit 2's `Transaction.finish()` is a client call; the
  contract for the Flutter phase is to call it only after
  `POST /billing/apple/verify` succeeds.

## Environments

Stored per purchase and entitlement (`production` / `sandbox`). In
production, Apple sandbox and Google test purchases are refused unless
`APPLE_ACCEPT_SANDBOX_IN_PRODUCTION` / `GOOGLE_ACCEPT_TEST_PURCHASES_IN_PRODUCTION`
is set, and then they are recorded as sandbox. Fake providers are refused in
production.

## Storage policy

* Google purchase tokens: **not stored.** Only a SHA-256 for lookup and
  uniqueness. RTDN and the client both bring the token when it is needed.
* App Store JWS: **not stored.** Decoded, verified, discarded.
* Provider events: id, type, opaque refs, SHA-256 of the body - not the body.

## Flutter phase contract

iOS: StoreKit 2 purchase with `appAccountToken`, then
`POST /billing/apple/verify` with `jwsRepresentation` (and `transactionId`),
then `finish()`. Android: Play Billing with `obfuscatedAccountId`, then
`POST /billing/google/verify` with the purchase token; the backend
acknowledges. On launch, `POST /billing/reconcile` with the device's current
entitlements. Premium UI reads `GET /billing/entitlements`.
