#!/usr/bin/env sh
# Docker smoke test for the background report pipeline.
#
#   queue a job -> the worker claims it -> it completes -> the report reads back
#
# Runs against the compose stack (api + postgres + redis + ai-worker). With the
# fake provider it costs nothing; with a real key it produces one real report.
#
# Usage: sh scripts/smoke_worker.sh [base_url]

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
EMAIL="worker-smoke-$(date +%s)@example.com"

say() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

say "register"
TOKENS=$(curl -s -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Sm0keTestPass!\",\"name\":\"Worker\",
       \"birth_date\":\"1992-05-14\",\"birth_time\":\"14:30:00\",
       \"birth_place\":\"Istanbul\"}")
ACCESS=$(printf '%s' "$TOKENS" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$ACCESS" ] || fail "no access token"
AUTH="Authorization: Bearer $ACCESS"

STATUS=$(curl -s -H "$AUTH" "$API/ai/status")
CONFIGURED=$(printf '%s' "$STATUS" | sed -n 's/.*"configured":\([a-z]*\).*/\1/p')
say "ai configured = $CONFIGURED"

if [ "$CONFIGURED" != "true" ]; then
  # Nothing can be queued without a provider, so what this level can check is
  # that queueing is refused cleanly rather than accepting work nobody can do.
  # A worker meeting an already-queued job without a key is covered by
  # tests/test_ai_hardening.py::test_worker_leaves_jobs_alone_without_a_key,
  # and by the ai_worker_idle_unconfigured line in the worker's own log.
  say "not configured: queueing is refused, nothing is accepted"
  QUEUED=$(curl -s -X POST "$API/ai/reports" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d '{"report_type":"natal","background":true}')
  case "$QUEUED" in
    *ai_not_configured*) printf 'queueing refused with ai_not_configured\n' ;;
    *) fail "expected ai_not_configured, got: $QUEUED" ;;
  esac

  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/ai/report-jobs" \
    -H "$AUTH" -H 'Content-Type: application/json' \
    -d '{"report_type":"natal"}')
  [ "$CODE" = "503" ] || fail "report-jobs should be 503, got $CODE"

  # And the rest of the API is untouched by the AI feature being off.
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "$AUTH" \
    "$API/astrology/natal-chart/me")
  [ "$CODE" = "200" ] || fail "natal chart broken while AI is off ($CODE)"

  printf '\nWORKER SMOKE OK (unconfigured)\n'
  exit 0
fi

say "queue a background report"
QUEUED=$(curl -s -X POST "$API/ai/reports" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"report_type":"transit","background":true}')
printf '%s\n' "$QUEUED"
JOB_ID=$(printf '%s' "$QUEUED" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
[ -n "$JOB_ID" ] || fail "no job id: $QUEUED"
case "$QUEUED" in
  *'"status":"queued"'*) : ;;
  *) fail "job did not start queued: $QUEUED" ;;
esac

say "wait for the worker to claim and finish it"
REPORT_ID=""
SEEN_RUNNING="no"
i=0
while [ "$i" -lt 60 ]; do
  JOB=$(curl -s -H "$AUTH" "$API/ai/report-jobs/$JOB_ID")
  case "$JOB" in
    *'"status":"running"'*) SEEN_RUNNING="yes" ;;
    *'"status":"completed"'*)
      REPORT_ID=$(printf '%s' "$JOB" | sed -n 's/.*"report_id":"\([^"]*\)".*/\1/p')
      break ;;
    *'"status":"failed"'*) fail "job failed: $JOB" ;;
  esac
  i=$((i + 1))
  sleep 1
done

[ -n "$REPORT_ID" ] || fail "job never completed: $JOB"
printf 'job completed after ~%ss (saw running: %s)\n' "$i" "$SEEN_RUNNING"

say "read the report back"
REPORT=$(curl -s -H "$AUTH" "$API/ai/reports/$REPORT_ID")
case "$REPORT" in
  *'"status":"completed"'*) : ;;
  *) fail "report not completed: $REPORT" ;;
esac
case "$REPORT" in
  *'"factor_ids"'*) : ;;
  *) fail "report sections carry no factor ids" ;;
esac
case "$REPORT" in
  *'"prompt_version":"transit_interpretation_v1"'*) : ;;
  *) fail "report has no prompt version" ;;
esac
printf 'grounded report returned\n'

say "the job is idempotent"
AGAIN=$(curl -s -H "$AUTH" "$API/ai/report-jobs/$JOB_ID")
case "$AGAIN" in
  *'"status":"completed"'*) : ;;
  *) fail "job state changed after completion: $AGAIN" ;;
esac

printf '\nWORKER SMOKE OK (configured)\n'
