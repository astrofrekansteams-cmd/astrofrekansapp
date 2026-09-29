# Google Play Billing backend

Verified against Google's current reference on 2026-09-24. REST calls with a
service account (`google-auth`, scope `androidpublisher`); no extra Google
client library.

## API surface

| Purpose | Method |
|---|---|
| subscription state | `purchases.subscriptionsv2.get` - `GET /applications/{pkg}/purchases/subscriptionsv2/tokens/{token}` |
| one-time purchase state | `purchases.productsv2.getproductpurchasev2` - `GET /applications/{pkg}/purchases/productsv2/tokens/{token}` |
| acknowledge subscription | `purchases.subscriptions.acknowledge` |
| acknowledge one-time | `purchases.products.acknowledge` |
| consume consumable | `purchases.products.consume` |

The v1 subscription `get` is not used.

## Verification

`POST /billing/google/verify` `{product_code, purchase_token}` → the API is
asked; the client's own view of the purchase is never used. The token must
map to the requested product, not be a test purchase in production, carry
this account's `obfuscatedExternalAccountId` if present, and not belong to
another account.

`obfuscatedAccountId` is an HMAC of the user id with a server-derived key -
Google asks for a one-way hash, not the id.

## Pending purchases

`PENDING` never entitles and is never acknowledged. When it completes, the
next verify, restore or RTDN picks it up.

## Acknowledge / consume

Google refunds a purchase not acknowledged within three days. The backend
acknowledges subscriptions and non-consumables, and consumes consumables -
**after** the entitlement is committed. If the store call fails, the
entitlement stands and the next verification, restore or RTDN retries.
Acknowledging before recording would risk a paid purchase with nothing
granted if the process died in between.

## RTDN

`POST /webhooks/google/play` - a Pub/Sub push.

1. **Authenticated:** the `Authorization: Bearer` OIDC JWT is verified with
   `google.oauth2.id_token.verify_oauth2_token` (signature, `aud`, `exp`),
   then `iss` ∈ {accounts.google.com}, `email` = the configured push service
   account, `email_verified` = true. Anything else is 401 and nothing is read.
2. The message's `packageName` must be ours.
3. `messageId` is recorded - a replay is `duplicate`.
4. **RTDN is a pointer, not state.** Google's reference says so explicitly.
   The token is fetched from the Developer API and *that* is applied. A test
   sends "renewed" while the API says expired: the result is expired.
5. A voided-purchase notification (authenticated, Google's statement that a
   refund happened) marks the purchase revoked; the purchase is still
   fetched.
6. A token no client has verified is `unassociated` - the obfuscated account
   id is a one-way hash, so the client's next verify or restore attaches it.

Configure: `GOOGLE_PUBSUB_PUSH_AUDIENCE`, `GOOGLE_PUBSUB_PUSH_SERVICE_ACCOUNT`.

## Upgrades

A `linkedPurchaseToken` names the purchase it replaces; that purchase is
marked expired so it stops entitling.

## Prices

Google's purchase APIs do not report a price. A Google charge is recorded
with `amount_minor = NULL` and posts nothing to the ledger; store revenue is
reconciled from Play's financial reports - a separate job, not built.

## Test purchases

`testPurchase` / `testPurchaseContext` → `environment=sandbox`. Refused in
production unless `GOOGLE_ACCEPT_TEST_PURCHASES_IN_PRODUCTION=true`.

## Tests

`FakeGooglePlayProvider` returns raw Developer API JSON through the same
normalisation as the real adapter, and signs Pub/Sub tokens with a throwaway
RSA key checked by the same claim validation. Tested: verified, pending,
cancel-until-expiry, expiry, hold, pause, grace, RTDN authoritative fetch,
duplicate RTDN, forged/wrong-audience/wrong-account/unverified-email push,
wrong package, wrong product, other-account token, acknowledge after
processing and retry after a failed acknowledge, consume, test purchase in
production.

**NOT VERIFIED:** a live Play Console service account, real Pub/Sub push
tokens, real purchases.
