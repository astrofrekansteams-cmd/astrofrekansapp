#!/usr/bin/env sh
# Docker smoke test for voice and video calls.
#
# Without LiveKit credentials - a supported configuration - this checks that
# the API is degraded, not broken: health and readiness green, call status
# honest, every call route answering one controlled
# `call_provider_not_configured`, and the rest of the product unaffected.
#
# With LiveKit configured it checks what needs no real order: status, a forged
# webhook refused, an unknown call a 404. The full flow - create, join, both
# parties connecting, webhooks driving the state - is scripts/e2e_livekit.py
# against a local LiveKit, and tests/test_calls_api.py against the doubles.
#
# Usage: sh scripts/smoke_calls.sh [base_url]

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
    *) fail "$WHAT: expected error code $WANT, got: $BODY" ;;
  esac
}

say "the process is up and ready"
expect_status "GET /health" 200 "$BASE/health"
expect_status "GET /ready" 200 "$BASE/ready"

say "register a throwaway account"
TOKEN=$(body_of -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"b10-smoke-$STAMP@example.com\",\"password\":\"Sm0keTestPass!\",
       \"name\":\"B10 Smoke\",\"birth_date\":\"1990-04-04\",
       \"birth_time\":\"11:00:00\",\"birth_place\":\"Istanbul\"}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ] || fail "could not register"
AUTH="Authorization: Bearer $TOKEN"
ok "registered"

say "call status says configured and provider, nothing else"
STATUS=$(body_of "$API/calls/status" -H "$AUTH")
printf '   %s\n' "$STATUS"
case "$STATUS" in
  *wss://*|*ws://*|*http*|*secret*|*key*) fail "status leaked configuration: $STATUS" ;;
  *) ok "no URL, key or secret in the response" ;;
esac
case "$STATUS" in
  *'"configured":true'*) CONFIGURED=1 ;;
  *) CONFIGURED=0 ;;
esac

if [ "$CONFIGURED" = "0" ]; then
  say "no LiveKit on this deployment: degraded, not broken"
  expect_status "POST /calls" 503 -X POST "$API/calls" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"order_id":"00000000-0000-0000-0000-000000000000","call_type":"audio"}'
  expect_code "POST /calls" call_provider_not_configured -X POST "$API/calls" \
    -H "$AUTH" -H 'Content-Type: application/json' \
    -d '{"order_id":"00000000-0000-0000-0000-000000000000","call_type":"audio"}'
  expect_status "POST /calls/{id}/join" 503 -X POST \
    "$API/calls/00000000-0000-0000-0000-000000000000/join" -H "$AUTH"
  expect_status "POST /webhooks/livekit" 503 -X POST "$API/webhooks/livekit" \
    -H 'Content-Type: application/webhook+json' -d '{}'
  # History needs no provider: an empty list, not an error.
  expect_status "GET /calls" 200 "$API/calls" -H "$AUTH"

  say "and the rest of the API does not care"
  expect_status "GET /astrology/natal-chart/me" 200 "$API/astrology/natal-chart/me" -H "$AUTH"
  expect_status "GET /experts" 200 "$API/experts" -H "$AUTH"
  expect_status "GET /chat/policy" 200 "$API/chat/policy" -H "$AUTH"
else
  say "LiveKit configured: forged webhooks are refused"
  BODY='{"event":"participant_joined","id":"EV_forged","room":{"name":"call_x"},"participant":{"identity":"p_x"}}'
  expect_status "webhook without a signature" 401 -X POST "$API/webhooks/livekit" \
    -H 'Content-Type: application/webhook+json' -d "$BODY"
  expect_code "webhook with a junk signature" invalid_webhook -X POST \
    "$API/webhooks/livekit" -H 'Content-Type: application/webhook+json' \
    -H 'Authorization: eyJhbGciOiJIUzI1NiJ9.e30.forged' -d "$BODY"

  say "an unknown call is 404, not 403"
  expect_status "GET /calls/{unknown}" 404 \
    "$API/calls/00000000-0000-0000-0000-000000000000" -H "$AUTH"
  expect_status "POST /calls/{unknown}/join" 404 -X POST \
    "$API/calls/00000000-0000-0000-0000-000000000000/join" -H "$AUTH"

  say "a call needs an order"
  expect_status "POST /calls for an unknown order" 404 -X POST "$API/calls" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"order_id":"00000000-0000-0000-0000-000000000000","call_type":"video"}'
fi

printf '\nPASS: calls behave as designed on this deployment.\n'
