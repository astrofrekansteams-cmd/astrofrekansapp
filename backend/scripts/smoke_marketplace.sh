#!/usr/bin/env sh
# Docker smoke test for the expert marketplace.
#
#   apply -> activate -> offer -> schedule -> slots -> order+book
#     -> consent -> complete -> review -> favourite
#
# Plus the two things that must fail: a second user taking the same slot, and
# another expert reading the order.
#
# Needs real Postgres (the exclusion constraint lives there) and Redis. No
# payment provider. Messages are ASCII on purpose: some shells mangle
# non-ASCII on the way into curl.
#
# Usage: sh scripts/smoke_marketplace.sh [base_url]

set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"
STAMP="$(date +%s)"

say() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
# The FIRST occurrence of a key, not the last. A greedy `.*` in sed walks past
# the order's own id and returns a nested one - which then looks like a
# missing order rather than a broken helper.
field() {
  printf '%s' "$1" | grep -o "\"$2\":\"[^\"]*\"" | head -1 \
    | sed 's/.*:"//; s/"$//'
}

register() {
  RESPONSE=$(curl -s -X POST "$API/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"Sm0keTestPass!\",\"name\":\"$2\",
         \"birth_date\":\"1990-04-04\",\"birth_time\":\"11:00:00\",
         \"birth_place\":\"Istanbul\"}")
  printf '%s' "$RESPONSE" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

say "register an expert and two clients"
EXPERT_TOKEN=$(register "mk-expert-$STAMP@example.com" Expert)
CLIENT_TOKEN=$(register "mk-client-$STAMP@example.com" Client)
RIVAL_TOKEN=$(register "mk-rival-$STAMP@example.com" Rival)
OTHER_EXPERT_TOKEN=$(register "mk-other-$STAMP@example.com" Other)
[ -n "$EXPERT_TOKEN" ] && [ -n "$CLIENT_TOKEN" ] || fail "registration failed"

EXPERT_AUTH="Authorization: Bearer $EXPERT_TOKEN"
CLIENT_AUTH="Authorization: Bearer $CLIENT_TOKEN"
RIVAL_AUTH="Authorization: Bearer $RIVAL_TOKEN"
OTHER_AUTH="Authorization: Bearer $OTHER_EXPERT_TOKEN"

say "apply to become an expert"
APPLIED=$(curl -s -X POST "$API/experts/apply" -H "$EXPERT_AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Smoke Astro","languages":["tr","en"],
       "specialties":["astrology","synastry"],"experience_years":10,
       "timezone":"Europe/Istanbul"}')
EXPERT_ID=$(field "$APPLIED" id)
[ -n "$EXPERT_ID" ] || fail "no expert id: $APPLIED"
case "$APPLIED" in
  *'"status":"pending_review"'*) : ;;
  *) fail "an application must start pending_review: $APPLIED" ;;
esac
case "$APPLIED" in
  *'"verified":true'*) fail "an applicant verified themselves" ;;
  *) : ;;
esac
printf 'application created pending_review, unverified\n'

say "an applicant cannot publish themselves"
CODE=$(status_of -X PATCH "$API/experts/me" -H "$EXPERT_AUTH" \
  -H 'Content-Type: application/json' -d '{"status":"active"}')
[ "$CODE" = "403" ] || fail "self-activation returned $CODE, expected 403"
printf 'self-activation refused\n'

say "activate through the moderation service method (no route exists)"
docker compose exec -T api python - "$EXPERT_ID" <<'PY'
import asyncio, sys, uuid

from app.db.session import get_session_factory
from app.services.marketplace.experts import ExpertProfileService


async def main(expert_id: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        service = ExpertProfileService(session)
        await service.approve(uuid.UUID(expert_id))
        await service.verify(uuid.UUID(expert_id), verified=True)
        await session.commit()
    print("activated")


asyncio.run(main(sys.argv[1]))
PY

say "the expert is now discoverable"
SEARCH=$(curl -s -H "$CLIENT_AUTH" "$API/experts?specialty=synastry&language=tr")
case "$SEARCH" in
  *"$EXPERT_ID"*) : ;;
  *) fail "expert not found in search: $SEARCH" ;;
esac
case "$SEARCH" in
  *"mk-expert-$STAMP@example.com"*) fail "search leaked the expert's email" ;;
  *) : ;;
esac
printf 'found, with no account data in the result\n'

say "create an offering"
DEFINITION=$(curl -s -H "$EXPERT_AUTH" "$API/services" \
  | tr ',' '\n' | grep -m1 '"id"' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
SERVICES=$(curl -s -H "$EXPERT_AUTH" "$API/services")
# Pick a service that supports appointments and chat.
DEF_ID=$(docker compose exec -T api python - <<'PY'
import asyncio
from sqlalchemy import select
from app.db.models.service import ServiceDefinition
from app.db.session import get_session_factory


async def main() -> None:
    async with get_session_factory()() as session:
        row = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.supports_chat.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        print(row.id if row else "")


asyncio.run(main())
PY
)
DEF_ID=$(printf '%s' "$DEF_ID" | tr -d '\r\n ')
[ -n "$DEF_ID" ] || fail "no appointment+chat service in the catalogue"

OFFERING=$(curl -s -X POST "$API/experts/me/services" -H "$EXPERT_AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"service_definition_id\":\"$DEF_ID\",\"title\":\"Smoke consultation\",
       \"delivery_type\":\"chat\",\"duration_minutes\":60,
       \"price_minor\":10000,\"currency\":\"TRY\"}")
SERVICE_ID=$(field "$OFFERING" id)
[ -n "$SERVICE_ID" ] || fail "no offering id: $OFFERING"
printf 'offering created at 10000 TRY minor units\n'

say "add a weekly schedule"
for DAY in 0 1 2 3 4 5 6; do
  CODE=$(status_of -X POST "$API/experts/me/availability" -H "$EXPERT_AUTH" \
    -H 'Content-Type: application/json' \
    -d "{\"weekday\":$DAY,\"start_local_time\":\"09:00:00\",
         \"end_local_time\":\"18:00:00\"}")
  [ "$CODE" = "201" ] || fail "availability day $DAY returned $CODE"
done
printf 'seven windows, 09:00-18:00 Istanbul\n'

say "list slots"
FROM=$(date -u -d '+1 day' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null \
  || date -u -v+1d '+%Y-%m-%dT%H:%M:%SZ')
TO=$(date -u -d '+8 days' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null \
  || date -u -v+8d '+%Y-%m-%dT%H:%M:%SZ')
SLOTS=$(curl -s -H "$CLIENT_AUTH" \
  "$API/experts/$EXPERT_ID/slots?service_id=$SERVICE_ID&from=$FROM&to=$TO")
SLOT=$(printf '%s' "$SLOTS" | sed -n 's/.*"starts_at_utc":"\([^"]*\)".*/\1/p' | head -1)
[ -n "$SLOT" ] || fail "no slots generated: $SLOTS"
COUNT=$(printf '%s' "$SLOTS" | grep -o '"starts_at_utc"' | wc -l)
printf '%s slots, first at %s\n' "$COUNT" "$SLOT"

say "order and book in one call"
ORDER=$(curl -s -X POST "$API/orders" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: smoke-$STAMP" \
  -d "{\"expert_service_id\":\"$SERVICE_ID\",\"starts_at_utc\":\"$SLOT\"}")
ORDER_ID=$(field "$ORDER" id)
[ -n "$ORDER_ID" ] || fail "no order id: $ORDER"
case "$ORDER" in
  *'"status":"pending_payment"'*) : ;;
  *) fail "a priced order should wait for payment: $ORDER" ;;
esac
case "$ORDER" in
  *'"payment_status":"pending"'*) : ;;
  *) fail "payment status is wrong: $ORDER" ;;
esac
case "$ORDER" in
  *'"platform_fee_minor":2000'*) : ;;
  *) fail "commission split is wrong: $ORDER" ;;
esac
case "$ORDER" in
  *'"expert_net_minor":8000'*) : ;;
  *) fail "expert net is wrong: $ORDER" ;;
esac
printf 'order created, appointment booked, 2000/8000 split at 2000 bp\n'

say "the same request is idempotent"
AGAIN=$(curl -s -X POST "$API/orders" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: smoke-$STAMP" \
  -d "{\"expert_service_id\":\"$SERVICE_ID\",\"starts_at_utc\":\"$SLOT\"}")
AGAIN_ID=$(field "$AGAIN" id)
[ "$AGAIN_ID" = "$ORDER_ID" ] || fail "a retry created a second order"
printf 'retry returned the same order\n'

say "a second user cannot take the same slot"
CONFLICT=$(curl -s -X POST "$API/orders" -H "$RIVAL_AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"expert_service_id\":\"$SERVICE_ID\",\"starts_at_utc\":\"$SLOT\"}")
case "$CONFLICT" in
  *slot_unavailable*|*slot_not_offered*) printf 'second booking refused\n' ;;
  *) fail "the slot was double booked: $CONFLICT" ;;
esac

say "the price is frozen"
curl -s -o /dev/null -X PATCH "$API/experts/me/services/$SERVICE_ID" \
  -H "$EXPERT_AUTH" -H 'Content-Type: application/json' \
  -d '{"price_minor":15000}'
FROZEN=$(curl -s -H "$CLIENT_AUTH" "$API/orders/$ORDER_ID")
case "$FROZEN" in
  *'"amount_minor":10000'*) printf 'the old order still says 10000\n' ;;
  *) fail "a price change rewrote an existing order: $FROZEN" ;;
esac

say "the expert sees the order but not the data"
EXPERT_VIEW=$(curl -s -H "$EXPERT_AUTH" "$API/expert/orders/$ORDER_ID")
case "$EXPERT_VIEW" in
  *"$ORDER_ID"*) : ;;
  *) fail "the expert cannot see their own order: $EXPERT_VIEW" ;;
esac
case "$EXPERT_VIEW" in
  *'"granted_consent_scopes":[]'*) printf 'no consent granted yet\n' ;;
  *) fail "consent appeared without being granted: $EXPERT_VIEW" ;;
esac

say "another expert cannot see it"
CODE=$(status_of -X POST "$API/experts/apply" -H "$OTHER_AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Other","languages":["tr"],"specialties":["tarot"],
       "timezone":"Europe/Istanbul"}')
[ "$CODE" = "201" ] || fail "second expert application returned $CODE"
CODE=$(status_of -H "$OTHER_AUTH" "$API/expert/orders/$ORDER_ID")
[ "$CODE" = "404" ] || fail "another expert read the order ($CODE)"
printf "another expert's attempt is 404\n"

say "grant consent"
GRANTED=$(curl -s -X PUT "$API/orders/$ORDER_ID/consents" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"scopes":["share_birth_profile","share_natal_chart"]}')
case "$GRANTED" in
  *share_birth_profile*) : ;;
  *) fail "consent was not recorded: $GRANTED" ;;
esac
AFTER=$(curl -s -H "$EXPERT_AUTH" "$API/expert/orders/$ORDER_ID")
case "$AFTER" in
  *share_birth_profile*) printf 'the expert now sees the granted scopes\n' ;;
  *) fail "consent did not reach the expert view: $AFTER" ;;
esac

say "an expert cannot grant consent"
CODE=$(status_of -X PUT "$API/orders/$ORDER_ID/consents" -H "$EXPERT_AUTH" \
  -H 'Content-Type: application/json' -d '{"scopes":["share_synastry"]}')
[ "$CODE" = "404" ] || fail "an expert reached the consent route ($CODE)"
printf 'refused\n'

say "revoke consent"
REVOKED=$(curl -s -X PUT "$API/orders/$ORDER_ID/consents" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' -d '{"scopes":[]}')
case "$REVOKED" in
  *'"active":false'*) : ;;
  *) fail "revocation did not take: $REVOKED" ;;
esac
GONE=$(curl -s -H "$EXPERT_AUTH" "$API/expert/orders/$ORDER_ID")
case "$GONE" in
  *'"granted_consent_scopes":[]'*) printf 'access withdrawn\n' ;;
  *) fail "consent survived revocation: $GONE" ;;
esac

say "a review needs a completed order"
CODE=$(status_of -X POST "$API/orders/$ORDER_ID/review" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' -d '{"rating":5}')
[ "$CODE" = "409" ] || fail "a pending order was reviewable ($CODE)"

docker compose exec -T api python - "$ORDER_ID" <<'PY'
import asyncio, sys, uuid

from sqlalchemy import select

from app.db.models.marketplace import ServiceOrder
from app.db.session import get_session_factory
from app.services.marketplace.orders import OrderService


async def main(order_id: str) -> None:
    async with get_session_factory()() as session:
        order = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == uuid.UUID(order_id))
        )
        await OrderService(session).complete(order)
        await session.commit()
    print("completed")


asyncio.run(main(sys.argv[1]))
PY

REVIEW=$(curl -s -X POST "$API/orders/$ORDER_ID/review" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"rating":5,"comment":"Clear and useful"}')
REVIEW_ID=$(field "$REVIEW" id)
[ -n "$REVIEW_ID" ] || fail "review not created: $REVIEW"
printf 'review created after completion\n'

say "the rating aggregate follows"
DETAIL=$(curl -s -H "$CLIENT_AUTH" "$API/experts/$EXPERT_ID")
case "$DETAIL" in
  *'"rating_count":1'*) : ;;
  *) fail "rating count did not update: $DETAIL" ;;
esac
case "$DETAIL" in
  *'"rating_average":5'*) printf 'average 5.0 over 1 review\n' ;;
  *) fail "rating average did not update: $DETAIL" ;;
esac

say "a second review on the same order is refused"
CODE=$(status_of -X POST "$API/orders/$ORDER_ID/review" -H "$CLIENT_AUTH" \
  -H 'Content-Type: application/json' -d '{"rating":1}')
[ "$CODE" = "409" ] || fail "a second review was allowed ($CODE)"
printf 'refused\n'

say "favourites"
CODE=$(status_of -X POST "$API/experts/$EXPERT_ID/favorite" -H "$CLIENT_AUTH")
[ "$CODE" = "200" ] || fail "favourite returned $CODE"
FAVS=$(curl -s -H "$CLIENT_AUTH" "$API/favorites/experts")
case "$FAVS" in
  *"$EXPERT_ID"*) : ;;
  *) fail "favourite not listed: $FAVS" ;;
esac
CODE=$(status_of -X DELETE "$API/experts/$EXPERT_ID/favorite" -H "$CLIENT_AUTH")
[ "$CODE" = "200" ] || fail "unfavourite returned $CODE"
printf 'added and removed\n'

say "invalid spread of requests"
CODE=$(status_of -H "$CLIENT_AUTH" "$API/experts?sort=vibes")
[ "$CODE" = "422" ] || fail "an unknown sort returned $CODE"
CODE=$(status_of "$API/experts")
[ "$CODE" = "401" ] || fail "search is reachable unauthenticated ($CODE)"
printf 'validation and auth hold\n'

printf '\nMARKETPLACE SMOKE OK\n'
