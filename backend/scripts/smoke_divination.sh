#!/usr/bin/env sh
# Docker smoke test for the divination layer.
#
#   draw -> the cards are stored -> AI interprets them -> grounded report
#
# Runs against the compose stack with real Postgres and Redis. With the fake
# provider it costs nothing. Messages are ASCII on purpose: some shells mangle
# non-ASCII on the way into curl, and a smoke test should fail for real
# reasons only.
#
# Usage: sh scripts/smoke_divination.sh [base_url]

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
EMAIL="divination-smoke-$(date +%s)@example.com"

say() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

say "register"
TOKENS=$(curl -s -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Sm0keTestPass!\",\"name\":\"Diviner\",
       \"birth_date\":\"1992-05-14\",\"birth_time\":\"14:30:00\",
       \"birth_place\":\"Istanbul\"}")
ACCESS=$(printf '%s' "$TOKENS" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$ACCESS" ] || fail "no access token"
AUTH="Authorization: Bearer $ACCESS"

say "deck catalogue"
DECKS=$(curl -s -H "$AUTH" "$API/divination/decks")
for expected in '"deck_type":"tarot"' '"deck_type":"rune"' '"deck_type":"katina"'; do
  case "$DECKS" in *"$expected"*) : ;; *) fail "missing deck: $expected" ;; esac
done
# The audited counts, straight from the API.
case "$DECKS" in
  *'"item_count":78'*) : ;; *) fail "tarot is not 78 cards" ;;
esac
case "$DECKS" in
  *'"item_count":24'*) : ;; *) fail "rune is not 24 runes" ;;
esac
case "$DECKS" in
  *'"item_count":65'*) : ;; *) fail "katina is not 65 cards" ;;
esac
printf '78 tarot / 24 rune / 65 katina\n'

say "asset mapping"
for deck in tarot rune katina; do
  ITEMS=$(curl -s -H "$AUTH" "$API/divination/decks/$deck/items")
  MISSING=$(printf '%s' "$ITEMS" | grep -o '"image_asset_key":""' | wc -l)
  [ "$MISSING" = "0" ] || fail "$deck has items with no asset key"
  case "$ITEMS" in
    *'"image_asset_key":"assets/'*) fail "$deck returned a path, not a stem" ;;
    *) : ;;
  esac
done
printf 'every item carries an asset stem, no paths\n'

say "invalid spread is refused"
CODE=$(status_of -X POST "$API/divination/readings" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"deck_type":"rune","spread_code":"celtic_cross"}')
[ "$CODE" = "404" ] || fail "rune+celtic_cross should be 404, got $CODE"
printf 'a tarot spread cannot be dealt from the rune deck\n'

interpret_deck() {
  deck="$1"; spread="$2"; want="$3"

  say "$deck: draw $spread"
  READING=$(curl -s -X POST "$API/divination/readings" -H "$AUTH" \
    -H 'Content-Type: application/json' \
    -d "{\"deck_type\":\"$deck\",\"spread_code\":\"$spread\",
         \"question\":\"What should I pay attention to?\"}")
  READING_ID=$(printf '%s' "$READING" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
  [ -n "$READING_ID" ] || fail "no reading id: $READING"

  COUNT=$(printf '%s' "$READING" | grep -o '"draw_order"' | wc -l)
  [ "$COUNT" -eq "$want" ] || fail "$deck dealt $COUNT items, expected $want"

  # Unique items: as many distinct item_ids as positions.
  UNIQUE=$(printf '%s' "$READING" | grep -o '"item_id":"[^"]*"' | sort -u | wc -l)
  [ "$UNIQUE" -eq "$want" ] || fail "$deck dealt a duplicate ($UNIQUE unique)"

  case "$READING" in
    *'"rng_source":"system_csprng"'*) : ;;
    *) fail "$deck was not dealt with the production RNG" ;;
  esac
  printf '%s items, all distinct, system CSPRNG\n' "$COUNT"

  say "$deck: snapshot holds"
  AGAIN=$(curl -s -H "$AUTH" "$API/divination/readings/$READING_ID")
  FIRST_A=$(printf '%s' "$READING" | grep -o '"item_id":"[^"]*"' | head -1)
  FIRST_B=$(printf '%s' "$AGAIN" | grep -o '"item_id":"[^"]*"' | head -1)
  [ "$FIRST_A" = "$FIRST_B" ] || fail "$deck reading changed between reads"
  printf 'same cards on re-read\n'

  say "$deck: interpret"
  REPORT=$(curl -s -X POST "$API/divination/readings/$READING_ID/interpret" \
    -H "$AUTH" -H 'Content-Type: application/json' -d '{}')
  case "$REPORT" in
    *'"status":"completed"'*) : ;;
    *) fail "$deck interpretation failed: $REPORT" ;;
  esac
  case "$REPORT" in
    *'"source_type":"divination_reading"'*) : ;;
    *) fail "$deck report has the wrong source type" ;;
  esac
  case "$REPORT" in
    *"${deck}_interpretation_v1"*) : ;;
    *) fail "$deck report used the wrong prompt" ;;
  esac
  case "$REPORT" in
    *'"factor_ids"'*) : ;;
    *) fail "$deck report sections carry no factor ids" ;;
  esac
  printf 'grounded report, prompt %s_interpretation_v1\n' "$deck"

  say "$deck: interpretation is cached, the draw is unchanged"
  CACHED=$(curl -s -X POST "$API/divination/readings/$READING_ID/interpret" \
    -H "$AUTH" -H 'Content-Type: application/json' -d '{}')
  case "$CACHED" in
    *'"cached":true'*) : ;;
    *) fail "$deck interpretation was regenerated instead of cached" ;;
  esac

  FINAL=$(curl -s -H "$AUTH" "$API/divination/readings/$READING_ID")
  FIRST_C=$(printf '%s' "$FINAL" | grep -o '"item_id":"[^"]*"' | head -1)
  [ "$FIRST_A" = "$FIRST_C" ] || fail "$deck cards changed after interpretation"
  printf 'cached, and the cards are the same\n'

  LAST_READING_ID="$READING_ID"
}

interpret_deck tarot celtic_cross 10
interpret_deck rune five_rune_cross 5
interpret_deck katina nine_card 9

say "ownership"
OTHER=$(curl -s -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"intruder-$(date +%s)@example.com\",
       \"password\":\"An0therStrongPass!\",\"name\":\"Intruder\"}")
OTHER_ACCESS=$(printf '%s' "$OTHER" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$OTHER_ACCESS" ] || fail "second account not created"

CODE=$(status_of -H "Authorization: Bearer $OTHER_ACCESS" \
  "$API/divination/readings/$LAST_READING_ID")
[ "$CODE" = "404" ] || fail "another user could read the reading ($CODE)"

CODE=$(status_of -X POST "$API/divination/readings/$LAST_READING_ID/interpret" \
  -H "Authorization: Bearer $OTHER_ACCESS" -H 'Content-Type: application/json' \
  -d '{}')
[ "$CODE" = "404" ] || fail "another user could interpret the reading ($CODE)"
printf "another user's reading is 404, never 403\n"

say "unauthenticated"
CODE=$(status_of "$API/divination/decks")
[ "$CODE" = "401" ] || fail "decks reachable unauthenticated ($CODE)"

printf '\nDIVINATION SMOKE OK\n'
