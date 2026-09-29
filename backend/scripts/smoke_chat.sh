#!/usr/bin/env sh
# Docker smoke test for the Firebase layer.
#
# What this can and cannot check over HTTP, stated plainly:
#
# Without Firebase credentials - the state most deployments boot in first, and
# a supported one - this checks that the API is *degraded, not broken*: health
# and readiness green, capabilities honest, astrology and the marketplace
# unaffected, and every Firebase-backed route answering one controlled
# `firebase_not_configured` rather than a stack trace or a 500.
#
# With credentials (or `FIREBASE_PROVIDER=fake`) it additionally walks the parts
# that need no Firebase ID token: the policy endpoint and device registration.
#
# It cannot drive a full send-a-message flow. That needs a signed Firebase ID
# token, which only a Firebase client SDK can mint - and in fake mode the token
# has to be registered *inside* the process, which no HTTP call can do. The
# end-to-end flow is covered by tests/test_chat_api.py, which drives the same
# routes through the real ASGI app against the doubles.
#
# Usage: sh scripts/smoke_chat.sh [base_url]

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
  # expect_status <what> <expected> <curl args...>
  WHAT="$1"; WANT="$2"; shift 2
  GOT=$(status_of "$@")
  [ "$GOT" = "$WANT" ] || fail "$WHAT: expected $WANT, got $GOT"
  ok "$WHAT -> $GOT"
}

expect_code() {
  # expect_code <what> <error code> <curl args...>
  WHAT="$1"; WANT="$2"; shift 2
  BODY=$(body_of "$@")
  case "$BODY" in
    *"\"code\":\"$WANT\""*) ok "$WHAT -> $WANT" ;;
    *) fail "$WHAT: expected error code $WANT, got: $BODY" ;;
  esac
}

# ------------------------------------------------------------------ probes

say "the process is up and ready"
expect_status "GET /health" 200 "$BASE/health"
expect_status "GET /ready" 200 "$BASE/ready"

say "capabilities are honest about what this server accepts"
CAPS=$(body_of "$API/auth/capabilities")
printf '   %s\n' "$CAPS"
case "$CAPS" in
  *'"accepts_local_jwt":true'*) ok "local JWTs accepted" ;;
  *) fail "capabilities does not accept local JWTs; existing clients would break" ;;
esac
# A key must never appear here. The project id is public configuration; a
# credential is not.
case "$CAPS" in
  *private_key*|*credential*|*secret*|*BEGIN*)
    fail "capabilities leaked something credential-shaped" ;;
  *) ok "no credential material in the response" ;;
esac

case "$CAPS" in
  *'"firebase_configured":true'*) CONFIGURED=1 ;;
  *) CONFIGURED=0 ;;
esac

# ------------------------------------------------------------------ account

say "register a throwaway account"
TOKEN=$(body_of -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"b9-smoke-$STAMP@example.com\",\"password\":\"Sm0keTestPass!\",
       \"name\":\"B9 Smoke\",\"birth_date\":\"1990-04-04\",
       \"birth_time\":\"11:00:00\",\"birth_place\":\"Istanbul\"}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ] || fail "could not register"
AUTH="Authorization: Bearer $TOKEN"
ok "registered, and a local JWT still works"

# The point of hybrid mode: nothing about B9 changed this.
expect_status "GET /auth/me with a local JWT" 200 "$API/auth/me" -H "$AUTH"

# ------------------------------------------------------------------- policy

say "the chat policy is published without needing Firebase"
POLICY=$(body_of "$API/chat/policy" -H "$AUTH")
printf '   %s\n' "$POLICY"
case "$POLICY" in
  *'"writable_order_states"'*) ok "policy returned" ;;
  *) fail "no policy: $POLICY" ;;
esac
# Chat before payment would be a free consultation channel.
case "$POLICY" in
  *'"writable_order_states":["awaiting_expert","confirmed","in_progress","paid"]'*)
    ok "pending_payment is not writable" ;;
  *) fail "writable states changed unexpectedly: $POLICY" ;;
esac

# ------------------------------------------------------------------ devices

say "device registration needs no Firebase credential"
DEVICE_TOKEN="smoke-token-$STAMP-0000000000000000000000000000"
DEVICE=$(body_of -X POST "$API/devices/push" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$DEVICE_TOKEN\",\"platform\":\"android\"}")
case "$DEVICE" in
  *'"token_fingerprint"'*) ok "registered, fingerprint returned" ;;
  *) fail "device registration failed: $DEVICE" ;;
esac
# The token must never come back. A device list that echoes tokens is a way to
# harvest them.
case "$DEVICE" in
  *"$DEVICE_TOKEN"*) fail "the push token was echoed back" ;;
  *) ok "the token itself was not returned" ;;
esac

LIST=$(body_of "$API/devices/push" -H "$AUTH")
case "$LIST" in
  *"$DEVICE_TOKEN"*) fail "GET /devices/push returned a raw token" ;;
  *) ok "the device list carries no raw token" ;;
esac

say "registering the same token again is idempotent"
DEVICE_ID=$(printf '%s' "$DEVICE" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
AGAIN=$(body_of -X POST "$API/devices/push" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$DEVICE_TOKEN\",\"platform\":\"android\"}")
case "$AGAIN" in
  *"$DEVICE_ID"*) ok "same row" ;;
  *) fail "a re-registration created a second device" ;;
esac

say "a short token is refused"
expect_status "POST /devices/push with a 5-character token" 422 \
  -X POST "$API/devices/push" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"token":"short","platform":"web"}'

# -------------------------------------------------------- degraded or live

if [ "$CONFIGURED" = "0" ]; then
  say "no Firebase on this deployment: degraded, not broken"

  # Each of these is a controlled 503 with one error code - not a 500, not a
  # hang, not a stack trace.
  expect_status "POST /conversations" 503 \
    -X POST "$API/conversations" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"order_id":"00000000-0000-0000-0000-000000000000"}'
  expect_code "POST /conversations" firebase_not_configured \
    -X POST "$API/conversations" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"order_id":"00000000-0000-0000-0000-000000000000"}'

  expect_status "GET /conversations" 503 "$API/conversations" -H "$AUTH"

  expect_status "POST /auth/firebase/session" 503 \
    -X POST "$API/auth/firebase/session" \
    -H 'Content-Type: application/json' \
    -d '{"id_token":"not-a-real-token-but-long-enough"}'
  expect_code "POST /auth/firebase/session" firebase_not_configured \
    -X POST "$API/auth/firebase/session" \
    -H 'Content-Type: application/json' \
    -d '{"id_token":"not-a-real-token-but-long-enough"}'

  say "and the rest of the API does not care"
  expect_status "GET /astrology/natal-chart/me" 200 \
    "$API/astrology/natal-chart/me" -H "$AUTH"
  expect_status "GET /services" 200 "$API/services" -H "$AUTH"
  expect_status "GET /experts" 200 "$API/experts" -H "$AUTH"
else
  say "Firebase is configured: checking the token path rejects rubbish"

  # A malformed token must be a clean 401, never a 500 out of the SDK.
  expect_status "POST /auth/firebase/session with a junk token" 401 \
    -X POST "$API/auth/firebase/session" \
    -H 'Content-Type: application/json' \
    -d '{"id_token":"eyJhbGciOiJub25lIn0.e30.not-a-signature"}'
  expect_code "POST /auth/firebase/session with a junk token" \
    invalid_firebase_token \
    -X POST "$API/auth/firebase/session" \
    -H 'Content-Type: application/json' \
    -d '{"id_token":"eyJhbGciOiJub25lIn0.e30.not-a-signature"}'

  say "a junk bearer token is not a session"
  expect_status "GET /auth/me with a junk bearer" 401 \
    "$API/auth/me" -H 'Authorization: Bearer eyJhbGciOiJub25lIn0.e30.nope'

  say "an unknown conversation is 404, not 403"
  expect_status "GET /conversations/{unknown}" 404 \
    "$API/conversations/00000000-0000-0000-0000-000000000000" -H "$AUTH"

  printf '\n   NOTE: sending a message needs a signed Firebase ID token, which\n'
  printf '   only a client SDK can mint. tests/test_chat_api.py covers the full\n'
  printf '   flow against the doubles.\n'
fi

# ------------------------------------------------------------------ cleanup

say "clean up"
if [ -n "$DEVICE_ID" ]; then
  expect_status "DELETE /devices/push/{id}" 200 \
    -X DELETE "$API/devices/push/$DEVICE_ID" -H "$AUTH"
fi

printf '\nPASS: the Firebase layer behaves as designed on this deployment.\n'
