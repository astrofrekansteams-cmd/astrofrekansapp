# App Store (StoreKit 2) backend

Built on Apple's official **`app-store-server-library==3.1.2`**, read from
the installed source (verified 2026-09-24).

## What the library does, and what that means here

| Library behaviour | Consequence |
|---|---|
| `SignedDataVerifier` checks the x5c chain to an Apple root, Apple's marker OIDs `1.2.840.113635.100.6.11.1` (leaf) and `…6.2.1` (intermediate), ES256, bundle id, environment | used for every transaction, renewal info and notification |
| In `Environment.XCODE` / `LOCAL_TESTING`, **signature verification is skipped** | those environments are not configurable (`APPLE_ENVIRONMENT` accepts only Production / Sandbox; the verifier constructor refuses others) |
| Production verification requires the numeric App Apple ID | `APPLE_APP_APPLE_ID` required; `assert_production_ready` checks it |
| Optional OCSP revocation checks | on (`APPLE_ENABLE_ONLINE_CHECKS=true`) |
| Root certificates are supplied by the caller | `APPLE_ROOT_CERTIFICATES_PATH`: a directory of Apple's `.cer` files, downloaded by the operator from apple.com/certificateauthority - public, not committed |

The legacy `verifyReceipt` flow is not used anywhere.

## Verification

`POST /billing/apple/verify`:

* with `transaction_id` and the App Store Server API configured → **Apple's
  server is asked** (`get_transaction_info`); a client JWS, if also sent,
  must name the same transaction;
* with only `signed_transaction` (StoreKit 2 `jwsRepresentation`) → verified
  to Apple's root; genuine, though possibly older than Apple's current view;
* for subscriptions with the API configured → refreshed via
  `get_all_subscription_statuses` (status + signed renewal info).

Then the product, environment, `appAccountToken` and ownership checks in
[store_billing.md](store_billing.md).

## App Store Server Notifications V2

`POST /webhooks/apple/app-store` `{"signedPayload": "…"}`

1. The outer JWS is verified; bundle id, App Apple ID and environment must be
   ours. Anything else is `401 invalid_provider_notification`, logged without
   the payload.
2. `notificationUUID` is recorded under a unique constraint - a replay is
   `duplicate` and changes nothing.
3. `signedTransactionInfo` and `signedRenewalInfo` are each verified again.
4. The purchase is attached to its existing owner, or - if no client has
   verified it yet - to the account named by `appAccountToken` (our user id);
   otherwise `unassociated`, and the client's next verify or restore attaches
   it.
5. `apply()` - the same idempotent path as client verification.

V1 notifications are not supported.

Handled by state, not by type: `SUBSCRIBED`, `DID_RENEW`, `DID_CHANGE_RENEWAL_STATUS`,
`DID_FAIL_TO_RENEW` (grace / billing retry), `EXPIRED`, `GRACE_PERIOD_EXPIRED`,
`REFUND`, `REVOKE`, `REFUND_REVERSED` (the only thing that may un-revoke) - the
signed transaction and renewal info are the state; the type is recorded.

## appAccountToken

The app passes the user's id (a random UUID, no personal data) as StoreKit's
`appAccountToken`. Apple signs it into every transaction. A transaction
stamped for another account is refused.

## Sandbox

Production refuses sandbox transactions unless
`APPLE_ACCEPT_SANDBOX_IN_PRODUCTION=true` (App Review), and then they are
recorded `environment=sandbox`.

## Prices

The JWS carries `price` in milliunits and `currency`. Converted to minor
units by ISO-4217 exponent (`milliunits_to_minor`) and posted as gross store
revenue. Apple's commission is not posted: it is not the platform's
commission, is not known per transaction, and is not guessed.

## Tests

`FakeAppleStoreProvider` signs genuine ES256 JWS with a throwaway root
certificate carrying Apple's marker OIDs; Apple's real `SignedDataVerifier`
checks them. Forged signature, wrong bundle, sandbox-in-production,
other-account reuse, wrong product, refund, duplicate notification and the
notification/verification race are all tested.

**NOT VERIFIED:** a live App Store Connect key, real Apple root certificates
with OCSP, real notifications.
