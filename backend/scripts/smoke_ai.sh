#!/usr/bin/env sh
# Docker smoke test for the Astro AI layer.
#
# Checks the two states that matter in production: a server with no provider
# key (the AI feature degrades, nothing else does) and a server with the fake
# provider wired in (the whole path runs end to end). It never calls a real
# model, so it is safe to run anywhere.
#
# Messages are ASCII on purpose: some shells mangle non-ASCII on the way
# into curl, and a smoke test should fail for real reasons only. Turkish
# routing is covered by the test suite.
#
# Usage: sh scripts/smoke_ai.sh [base_url]

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
EMAIL="smoke-$(date +%s)@example.com"

say() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
json_of() { curl -s "$@"; }

say "health and readiness"
[ "$(status_of "$BASE/health")" = 200 ] || fail "/health not 200"
[ "$(status_of "$BASE/ready")" = 200 ] || fail "/ready not 200"
json_of "$BASE/ready"
printf '\n'

say "register a smoke user"
TOKENS=$(curl -s -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Sm0keTestPass!\",\"name\":\"Smoke\",
       \"birth_date\":\"1992-05-14\",\"birth_time\":\"14:30:00\",
       \"birth_place\":\"Istanbul\"}")
ACCESS=$(printf '%s' "$TOKENS" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$ACCESS" ] || fail "no access token: $TOKENS"
AUTH="Authorization: Bearer $ACCESS"

say "ai status"
STATUS=$(json_of -H "$AUTH" "$API/ai/status")
printf '%s\n' "$STATUS"
case "$STATUS" in
  *'"api_key"'*|*'sk-'*) fail "status leaked credential material" ;;
esac
printf '%s' "$STATUS" | grep -q '"context_version":"context_selection_v1"' \
  || fail "context version missing"
printf '%s' "$STATUS" | grep -q '"astro_chat":"astro_chat_v1"' \
  || fail "prompt versions missing"

CONFIGURED=$(printf '%s' "$STATUS" | sed -n 's/.*"configured":\([a-z]*\).*/\1/p')
say "configured = $CONFIGURED"

CHAT_CODE=$(status_of -X POST "$API/ai/chat" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"message":"How is today?"}')
# `transit` is free; natal/synastry/yearly are sold as credits (checked below).
REPORT=$(curl -s -X POST "$API/ai/reports" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"report_type":"transit"}')

if [ "$CONFIGURED" = "false" ]; then
  say "not-configured path"
  [ "$CHAT_CODE" = 503 ] || fail "chat should be 503 without a key, got $CHAT_CODE"
  printf '%s' "$REPORT" | grep -q 'ai_not_configured' \
    || fail "report should report ai_not_configured: $REPORT"

  # The point of the degraded state: everything else still works.
  [ "$(status_of -H "$AUTH" "$API/astrology/natal-chart/me")" = 200 ] \
    || fail "natal chart broken while AI is unconfigured"
  [ "$(status_of -H "$AUTH" "$API/horoscope/daily")" = 200 ] \
    || fail "daily horoscope broken while AI is unconfigured"
  [ "$(status_of "$BASE/ready")" = 200 ] || fail "readiness degraded"
  printf 'AI degrades alone; the rest of the API is unaffected.\n'
else
  say "configured path"
  [ "$CHAT_CODE" = 200 ] || fail "chat failed: $CHAT_CODE"

  printf '%s' "$REPORT" | grep -q '"status":"completed"' \
    || fail "report not completed: $REPORT"
  printf '%s' "$REPORT" | grep -q '"factor_ids"' \
    || fail "report sections carry no factor ids"
  printf '%s' "$REPORT" | grep -q '"prompt_version":"transit_interpretation_v1"' \
    || fail "report has no prompt version"

  say "a paid report without a credit is refused, whatever the client does"
  PAID=$(status_of -X POST "$API/ai/reports" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"report_type":"natal","consumer_ref":"smoke-no-credit-1"}')
  [ "$PAID" = 402 ] || fail "natal without a credit should be 402, got $PAID"

  say "second request is served from the snapshot"
  AGAIN=$(curl -s -X POST "$API/ai/reports" -H "$AUTH" \
    -H 'Content-Type: application/json' -d '{"report_type":"transit"}')
  printf '%s' "$AGAIN" | grep -q '"cached":true' \
    || fail "report was regenerated instead of cached"

  say "streaming"
  STREAM=$(curl -s -N -X POST "$API/ai/chat/stream" -H "$AUTH" \
    -H 'Content-Type: application/json' -d '{"message":"What about this week?"}')
  printf '%s' "$STREAM" | grep -q 'event: message_start' || fail "no message_start"
  printf '%s' "$STREAM" | grep -q 'event: text_delta' || fail "no text_delta"
  printf '%s' "$STREAM" | grep -q 'event: message_complete' \
    || fail "no message_complete"
  printf '%s' "$STREAM" | grep -q 'response.output_text' \
    && fail "provider event names leaked into the stream"
  printf 'stream contract ok\n'
fi

say "authorisation"
[ "$(status_of "$API/ai/chat" -X POST -H 'Content-Type: application/json' \
      -d '{"message":"hi"}')" = 401 ] || fail "chat is reachable unauthenticated"
[ "$(status_of -H "$AUTH" "$API/ai/reports/00000000-0000-0000-0000-000000000000")" \
  = 404 ] || fail "unknown report id should be 404"

printf '\nSMOKE OK (configured=%s)\n' "$CONFIGURED"
