#!/usr/bin/env sh
# Docker smoke test for payments (B11).
#
# Without store credentials and without an external provider - the state this
# stack boots in, and a supported one - this checks that billing is degraded,
# not broken: status honest (booleans only), store verification and webhooks
# a controlled 503, external checkout a controlled 503, entitlements readable
# (and empty), and the rest of the product unaffected.
#
# The full purchase, notification, ledger and refund flows run against the
# store doubles in tests/test_payments.py and, for races, on Postgres in
# scripts/payment_concurrency_check.py.
#
# Usage: sh scripts/smoke_billing.sh [base_url]

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
STAMP="$(date +%s)"

say() { printf '\n== %s\n' "$1"; }
ok() { printf '   ok: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
body_of() { curl -s "$@"; }
expect_status() {
  WHAT="$1"; WANT="$2"; shift 2
  GOT=$(status_of "$@")
  [ "$GOT" = "$WANT" ] || fail "$WHAT: expected $WANT, got $GOT"
  ok "$WHAT -> $GOT"
}
expect_code() {
  WHAT="$1"; WANT="$2"; shift 2
  BODY=$(body_of "$@")
  case "$BODY" in
    *"\"code\":\"$WANT\""*) ok "$WHAT -> $WANT" ;;
    *) fail "$WHAT: expected $WANT, got: $BODY" ;;
  esac
}

say "the process is up"
expect_status "GET /health" 200 "$BASE/health"
expect_status "GET /ready" 200 "$BASE/ready"

say "register"
TOKEN=$(body_of -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"b11-smoke-$STAMP@example.com\",\"password\":\"Sm0keTestPass!\",\"name\":\"B11\",
       \"birth_date\":\"1990-04-04\",\"birth_time\":\"11:00:00\",\"birth_place\":\"Istanbul\"}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ] || fail "could not register"
AUTH="Authorization: Bearer $TOKEN"
ok "registered"

say "billing status: booleans only"
STATUS=$(body_of "$API/billing/status" -H "$AUTH")
printf '   %s\n' "$STATUS"
case "$STATUS" in
  *key*|*secret*|*http*|*bundle*|*package*) fail "status leaked configuration" ;;
  *'"apple_configured":false'*'"google_configured":false'*'"external_marketplace_configured":false'*) ok "honest: nothing configured" ;;
  *) ok "status returned" ;;
esac

say "store rails without credentials: controlled 503"
expect_code "POST /billing/apple/verify" store_provider_not_configured -X POST "$API/billing/apple/verify" \
  -H "$AUTH" -H 'Content-Type: application/json' -d '{"product_code":"premium_monthly","signed_transaction":"a.b.c"}'
expect_code "POST /billing/google/verify" store_provider_not_configured -X POST "$API/billing/google/verify" \
  -H "$AUTH" -H 'Content-Type: application/json' -d '{"product_code":"premium_monthly","purchase_token":"token-0000000000"}'
expect_status "POST /webhooks/apple/app-store" 503 -X POST "$API/webhooks/apple/app-store" \
  -H 'Content-Type: application/json' -d '{"signedPayload":"x"}'
expect_status "POST /webhooks/google/play" 503 -X POST "$API/webhooks/google/play" \
  -H 'Content-Type: application/json' -d '{}'
expect_code "POST /webhooks/payments/external" external_payment_provider_not_configured \
  -X POST "$API/webhooks/payments/external" -H 'Content-Type: application/json' -d '{}'

say "reads work without any provider"
ENT=$(body_of "$API/billing/entitlements" -H "$AUTH")
case "$ENT" in
  *'"tier":"free"'*'"premium":false'*) ok "entitlements: free, no premium" ;;
  *) fail "unexpected entitlements: $ENT" ;;
esac
expect_status "GET /billing/products?platform=ios" 200 "$API/billing/products?platform=ios" -H "$AUTH"
PRODUCTS=$(body_of "$API/billing/products?platform=ios" -H "$AUTH")
case "$PRODUCTS" in
  *price*) fail "a price was returned" ;;
  *) ok "no prices in the catalogue response" ;;
esac
expect_status "GET /billing/account-tokens" 200 "$API/billing/account-tokens" -H "$AUTH"

say "no endpoint accepts 'paid' from a client"
expect_status "POST /orders/{unknown}/payment" 404 -X POST \
  "$API/orders/00000000-0000-0000-0000-000000000000/payment" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"method":"external","idempotency_key":"smoke-0001"}'

say "a normal user has no payout surface"
CODE=$(status_of "$API/expert/payouts" -H "$AUTH")
case "$CODE" in 403|404) ok "GET /expert/payouts -> $CODE" ;; *) fail "expert payouts returned $CODE" ;; esac

say "the rest of the product does not care"
expect_status "GET /astrology/natal-chart/me" 200 "$API/astrology/natal-chart/me" -H "$AUTH"
expect_status "GET /experts" 200 "$API/experts" -H "$AUTH"
expect_status "GET /calls/status" 200 "$API/calls/status" -H "$AUTH"

printf '\nPASS: billing behaves as designed on this deployment.\n'
