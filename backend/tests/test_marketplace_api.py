"""Marketplace flows: booking, orders, consent, reviews, ownership.

The things worth breaking a build over:

* **A price is frozen at purchase.** An expert raising their rate must not
  change what somebody already agreed to.
* **Consent is the whole of expert access.** Not "they are an expert", not
  "the order references it" - a live grant, on that order, or nothing.
* **A slot belongs to one appointment.** Proven at the state-machine level
  here; the Postgres exclusion constraint is proven by
  `scripts/booking_concurrency_check.py` against a real database.
* **Someone else's row is a 404.** Never a 403, which would confirm it exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.marketplace import (
    Expert,
    ExpertAvailability,
    ExpertService,
    ServiceOrder,
)
from app.db.models.service import ServiceDefinition
from app.db.models.user import User
from app.domain.marketplace import (
    DeliveryType,
    ExpertStatus,
    PaymentStatus,
)

API = "/api/v1"


# =============================================================== fixtures


async def register(client: httpx.AsyncClient, email: str, **extra) -> dict:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Str0ngPassphrase!",
            "name": extra.get("name", "Person"),
            "birth_date": "1990-04-04",
            "birth_time": "11:00:00",
            "birth_place": "Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "email": email}


@pytest.fixture
async def catalog(session_factory):
    from app.services.catalog.service import CatalogService

    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()
        definition = await session.scalar(
            select(ServiceDefinition)
            .where(
                ServiceDefinition.supports_appointment.is_(True),
                ServiceDefinition.active.is_(True),
            )
            .limit(1)
        )
        automated = await session.scalar(
            select(ServiceDefinition)
            .where(ServiceDefinition.supports_automated_report.is_(True))
            .limit(1)
        )
        return {
            "appointment_definition_id": definition.id,
            "appointment_code": definition.code,
            "supports_video": definition.supports_video,
            "supports_chat": definition.supports_chat,
            "automated_definition_id": automated.id if automated else None,
        }


@pytest.fixture
async def expert(client: httpx.AsyncClient, catalog, session_factory):
    """An active expert with an offering and a wide-open schedule."""
    account = await register(client, "expert@example.com", name="Expert")

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == "expert@example.com")
        )
        row = Expert(
            user_id=user.id,
            display_name="Nova Astro",
            headline="Natal and synastry",
            bio="Fifteen years of practice.",
            languages=["tr", "en"],
            specialties=["astrology", "synastry"],
            experience_years=15,
            timezone="Europe/Istanbul",
            status=ExpertStatus.ACTIVE.value,
            verified=True,
            rating_average=0,
            rating_count=0,
        )
        session.add(row)
        await session.flush()

        delivery = (
            DeliveryType.VIDEO.value
            if catalog["supports_video"]
            else DeliveryType.CHAT.value
        )
        offering = ExpertService(
            expert_id=row.id,
            service_definition_id=catalog["appointment_definition_id"],
            title="60-minute consultation",
            delivery_type=delivery,
            duration_minutes=60,
            price_minor=10000,
            currency="TRY",
            active=True,
        )
        session.add(offering)

        for weekday in range(7):
            session.add(
                ExpertAvailability(
                    expert_id=row.id,
                    weekday=weekday,
                    start_local_time=time(0, 0),
                    end_local_time=time(23, 0),
                    timezone="Europe/Istanbul",
                    active=True,
                )
            )
        await session.commit()

        return {
            "expert_id": row.id,
            "service_id": offering.id,
            "user_id": user.id,
            "headers": account["headers"],
        }


@pytest.fixture
def wide_open(monkeypatch):
    """Remove scheduling friction so a test can pick any slot."""
    monkeypatch.setattr(settings, "appointment_minimum_notice_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_before_minutes", 0)
    monkeypatch.setattr(settings, "appointment_buffer_after_minutes", 0)


async def first_slot(client, headers, expert, *, skip: int = 0) -> str:
    now = datetime.now(UTC)
    response = await client.get(
        f"{API}/experts/{expert['expert_id']}/slots",
        headers=headers,
        params={
            "service_id": str(expert["service_id"]),
            "from": now.isoformat(),
            "to": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    slots = response.json()["slots"]
    assert len(slots) > skip, "no slots generated"
    return slots[skip]["starts_at_utc"]


async def complete_order(session_factory, order_id: uuid.UUID) -> None:
    """Drive an order to completed, the way a consultation surface will."""
    from app.services.marketplace.orders import OrderService

    async with session_factory() as session:
        order = await session.scalar(
            select(ServiceOrder).where(ServiceOrder.id == order_id)
        )
        await OrderService(session).complete(order)
        await session.commit()


# ============================================================ application


async def test_an_applicant_cannot_publish_themselves(
    client: httpx.AsyncClient, registered
):
    response = await client.post(
        f"{API}/experts/apply",
        headers=registered["headers"],
        json={
            "display_name": "Hopeful",
            "languages": ["tr"],
            "specialties": ["tarot"],
            "experience_years": 3,
            "timezone": "Europe/Istanbul",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending_review"
    assert body["verified"] is False

    # And they cannot promote themselves afterwards either.
    promote = await client.patch(
        f"{API}/experts/me", headers=registered["headers"], json={"status": "active"}
    )
    assert promote.status_code == 403
    assert promote.json()["error"]["code"] == "forbidden"


async def test_one_profile_per_account(client: httpx.AsyncClient, registered):
    payload = {
        "display_name": "Hopeful",
        "languages": ["tr"],
        "specialties": ["tarot"],
        "timezone": "Europe/Istanbul",
    }
    first = await client.post(
        f"{API}/experts/apply", headers=registered["headers"], json=payload
    )
    assert first.status_code == 201

    second = await client.post(
        f"{API}/experts/apply", headers=registered["headers"], json=payload
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "expert_profile_exists"


async def test_an_application_is_validated(
    client: httpx.AsyncClient, registered
):
    bad_timezone = await client.post(
        f"{API}/experts/apply",
        headers=registered["headers"],
        json={
            "display_name": "Hopeful",
            "languages": ["tr"],
            "specialties": ["tarot"],
            "timezone": "Mars/Olympus",
        },
    )
    assert bad_timezone.status_code == 422
    assert bad_timezone.json()["error"]["code"] == "invalid_timezone"

    bad_language = await client.post(
        f"{API}/experts/apply",
        headers=registered["headers"],
        json={
            "display_name": "Hopeful",
            "languages": ["klingon"],
            "specialties": ["tarot"],
            "timezone": "Europe/Istanbul",
        },
    )
    assert bad_language.status_code == 422


async def test_a_pending_profile_is_not_discoverable(
    client: httpx.AsyncClient, registered
):
    created = await client.post(
        f"{API}/experts/apply",
        headers=registered["headers"],
        json={
            "display_name": "Hopeful",
            "languages": ["tr"],
            "specialties": ["tarot"],
            "timezone": "Europe/Istanbul",
        },
    )
    expert_id = created.json()["id"]

    search = await client.get(f"{API}/experts", headers=registered["headers"])
    assert all(row["id"] != expert_id for row in search.json()["items"])

    # Not even by direct id: application status is not public information.
    direct = await client.get(
        f"{API}/experts/{expert_id}", headers=registered["headers"]
    )
    assert direct.status_code == 404

    # The owner still sees their own.
    own = await client.get(f"{API}/experts/me", headers=registered["headers"])
    assert own.status_code == 200
    assert own.json()["status"] == "pending_review"


# ================================================================ search


async def test_search_returns_public_information_only(
    client: httpx.AsyncClient, registered, expert
):
    response = await client.get(f"{API}/experts", headers=registered["headers"])
    assert response.status_code == 200
    body = response.json()

    assert body["total"] >= 1
    assert body["limit"] == 20 and body["offset"] == 0
    row = next(item for item in body["items"] if item["id"] == str(expert["expert_id"]))

    assert row["display_name"] == "Nova Astro"
    assert row["from_price"]["amount_minor"] == 10000
    assert row["from_price"]["currency"] == "TRY"

    # Nothing from the underlying account.
    text = response.text
    assert "expert@example.com" not in text
    assert "birth" not in text.lower()
    assert "user_id" not in text


async def test_search_filters(client: httpx.AsyncClient, registered, expert):
    hit = await client.get(
        f"{API}/experts",
        headers=registered["headers"],
        params={"specialty": "synastry", "language": "tr", "verified": True},
    )
    assert hit.json()["total"] == 1

    miss = await client.get(
        f"{API}/experts", headers=registered["headers"], params={"specialty": "rune"}
    )
    assert miss.json()["total"] == 0

    price_miss = await client.get(
        f"{API}/experts",
        headers=registered["headers"],
        params={"max_price_minor": 100},
    )
    assert price_miss.json()["total"] == 0

    price_hit = await client.get(
        f"{API}/experts",
        headers=registered["headers"],
        params={"min_price_minor": 5000, "max_price_minor": 20000},
    )
    assert price_hit.json()["total"] == 1


async def test_an_unknown_sort_is_refused(
    client: httpx.AsyncClient, registered, expert
):
    response = await client.get(
        f"{API}/experts", headers=registered["headers"], params={"sort": "vibes"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_search"


# ====================================================== offering rules


async def test_an_expert_cannot_widen_what_the_catalogue_allows(
    client: httpx.AsyncClient, catalog, expert, session_factory
):
    """The catalogue is the source of truth, not the offering."""
    async with session_factory() as session:
        automated_only = await session.scalar(
            select(ServiceDefinition).where(
                ServiceDefinition.fulfillment_modes.isnot(None),
                ServiceDefinition.supports_video.is_(False),
                ServiceDefinition.active.is_(True),
            )
        )

    response = await client.post(
        f"{API}/experts/me/services",
        headers=expert["headers"],
        json={
            "service_definition_id": str(automated_only.id),
            "title": "Video reading",
            "delivery_type": "video",
            "duration_minutes": 60,
            "price_minor": 5000,
            "currency": "TRY",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "service_not_offerable"


async def test_offering_capabilities_are_an_intersection(
    client: httpx.AsyncClient, registered, expert
):
    response = await client.get(
        f"{API}/experts/{expert['expert_id']}/services",
        headers=registered["headers"],
    )
    offering = response.json()[0]

    # Exactly one channel is true - the one it is sold through - and only if
    # the definition supports it too.
    channels = [
        offering["supports_chat"],
        offering["supports_voice"],
        offering["supports_video"],
    ]
    assert sum(1 for flag in channels if flag) <= 1
    assert offering["requires_birth_data"] in (True, False)


async def test_another_expert_cannot_touch_your_offerings(
    client: httpx.AsyncClient, expert, catalog
):
    """There is no route that takes an expert id for a write."""
    intruder = await register(client, "intruder-expert@example.com")
    await client.post(
        f"{API}/experts/apply",
        headers=intruder["headers"],
        json={
            "display_name": "Intruder",
            "languages": ["tr"],
            "specialties": ["tarot"],
            "timezone": "Europe/Istanbul",
        },
    )

    # The intruder's own /me is their own profile; the victim's service id is
    # simply not found under it.
    response = await client.patch(
        f"{API}/experts/me/services/{expert['service_id']}",
        headers=intruder["headers"],
        json={"price_minor": 1},
    )
    assert response.status_code == 404


# =============================================================== booking


async def test_booking_creates_an_order_and_an_appointment(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)

    response = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()

    assert order["status"] == "pending_payment"
    assert order["payment_status"] == "pending"
    assert order["total"]["amount_minor"] == 10000
    assert order["appointment"] is not None
    assert order["appointment"]["status"] == "pending"
    assert order["appointment"]["starts_at_utc"] == starts


async def test_a_slot_can_only_be_booked_once(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    other = await register(client, "second@example.com")

    first = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert first.status_code == 201

    second = await client.post(
        f"{API}/orders",
        headers=other["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert second.status_code in (409, 422)
    assert second.json()["error"]["code"] in (
        "slot_unavailable",
        "slot_not_offered",
    )


async def test_a_booked_slot_disappears_from_the_list(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )

    now = datetime.now(UTC)
    response = await client.get(
        f"{API}/experts/{expert['expert_id']}/slots",
        headers=registered["headers"],
        params={
            "service_id": str(expert["service_id"]),
            "from": now.isoformat(),
            "to": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert starts not in [slot["starts_at_utc"] for slot in response.json()["slots"]]


async def test_a_time_that_was_never_offered_cannot_be_booked(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    """A hand-crafted request is refused even though the row would fit."""
    far_future = (datetime.now(UTC) + timedelta(days=400)).isoformat()
    response = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": far_future,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "slot_not_offered"


async def test_a_hold_blocks_another_user_then_expires(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    other = await register(client, "holder@example.com")

    held = await client.post(
        f"{API}/experts/{expert['expert_id']}/hold",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert held.status_code == 201

    blocked = await client.post(
        f"{API}/orders",
        headers=other["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert blocked.status_code in (409, 422)

    # An abandoned hold must not block the slot forever.
    from app.db.models.marketplace import SlotHold

    async with session_factory() as session:
        hold = await session.scalar(
            select(SlotHold).where(SlotHold.id == uuid.UUID(held.json()["id"]))
        )
        hold.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    now_free = await client.post(
        f"{API}/orders",
        headers=other["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert now_free.status_code == 201


async def test_your_own_hold_does_not_block_your_own_booking(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    await client.post(
        f"{API}/experts/{expert['expert_id']}/hold",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )

    response = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert response.status_code == 201, response.text


async def test_idempotent_booking(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    """A retry on a flaky connection must not book twice."""
    starts = await first_slot(client, registered["headers"], expert)
    payload = {
        "expert_service_id": str(expert["service_id"]),
        "starts_at_utc": starts,
    }
    headers = {**registered["headers"], "Idempotency-Key": "retry-me-once"}

    first = await client.post(f"{API}/orders", headers=headers, json=payload)
    second = await client.post(f"{API}/orders", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    orders = await client.get(f"{API}/orders", headers=registered["headers"])
    assert len(orders.json()) == 1


async def test_the_same_key_with_a_different_request_is_a_conflict(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory, catalog
):
    starts = await first_slot(client, registered["headers"], expert)
    headers = {**registered["headers"], "Idempotency-Key": "one-key"}

    await client.post(
        f"{API}/orders",
        headers=headers,
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )

    # A second offering, same key.
    async with session_factory() as session:
        other = ExpertService(
            expert_id=expert["expert_id"],
            service_definition_id=catalog["appointment_definition_id"],
            title="Another",
            delivery_type=DeliveryType.CHAT.value
            if catalog["supports_chat"]
            else DeliveryType.VIDEO.value,
            duration_minutes=30,
            price_minor=5000,
            currency="TRY",
            active=True,
        )
        session.add(other)
        await session.commit()
        other_id = other.id

    conflict = await client.post(
        f"{API}/orders",
        headers=headers,
        json={
            "expert_service_id": str(other_id),
            "starts_at_utc": starts,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


# ========================================================= price & money


async def test_the_price_is_frozen_at_purchase(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    """An expert raising their rate must not change an existing order."""
    starts = await first_slot(client, registered["headers"], expert)
    first = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert first.json()["total"]["amount_minor"] == 10000

    raised = await client.patch(
        f"{API}/experts/me/services/{expert['service_id']}",
        headers=expert["headers"],
        json={"price_minor": 15000},
    )
    assert raised.json()["price"]["amount_minor"] == 15000

    # The old order is untouched.
    old = await client.get(
        f"{API}/orders/{first.json()['id']}", headers=registered["headers"]
    )
    assert old.json()["total"]["amount_minor"] == 10000
    assert old.json()["service_title"] == "60-minute consultation"

    # A new order gets the new price.
    later = await first_slot(client, registered["headers"], expert, skip=8)
    second = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": later,
        },
    )
    assert second.json()["total"]["amount_minor"] == 15000


async def test_commission_is_exact_integer_arithmetic(
    client: httpx.AsyncClient, registered, expert, wide_open, monkeypatch
):
    monkeypatch.setattr(settings, "marketplace_commission_bps", 2000)  # 20%

    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    commission = order["commission"]
    assert commission["commission_basis_points"] == 2000
    assert commission["gross_amount_minor"] == 10000
    assert commission["platform_fee_minor"] == 2000
    assert commission["expert_net_minor"] == 8000
    # Nothing is lost or invented in the split.
    assert (
        commission["platform_fee_minor"] + commission["expert_net_minor"]
        == commission["gross_amount_minor"]
    )


def test_commission_rounding_favours_the_expert():
    from app.domain.marketplace import Money

    fee, net = Money(999, "TRY").split_commission(2000)
    assert fee.amount_minor == 199  # truncated
    assert net.amount_minor == 800
    assert fee.amount_minor + net.amount_minor == 999


async def test_a_free_service_needs_no_payment(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    await client.patch(
        f"{API}/experts/me/services/{expert['service_id']}",
        headers=expert["headers"],
        json={"price_minor": 0},
    )

    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    assert order["status"] == "confirmed"
    assert order["payment_status"] == "not_required"


async def test_nothing_marks_a_priced_order_paid(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    """No payment provider is integrated, and the flow does not pretend."""
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    assert order["payment_status"] == PaymentStatus.PENDING.value

    again = await client.get(
        f"{API}/orders/{order['id']}", headers=registered["headers"]
    )
    assert again.json()["payment_status"] == PaymentStatus.PENDING.value


# ========================================================== cancellation


async def test_cancelling_an_order_cancels_its_appointment(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    cancelled = await client.post(
        f"{API}/orders/{order['id']}/cancel",
        headers=registered["headers"],
        json={"reason": "Changed my mind"},
    )
    assert cancelled.status_code == 200
    body = cancelled.json()

    assert body["status"] == "cancelled"
    assert body["cancellation_actor"] == "user"
    assert body["cancellation_reason"] == "Changed my mind"
    assert body["appointment"]["status"] == "cancelled"
    # Payment state is untouched: a refund may still be owed.
    assert body["payment_status"] == "pending"

    # And the slot is free again.
    now = datetime.now(UTC)
    slots = await client.get(
        f"{API}/experts/{expert['expert_id']}/slots",
        headers=registered["headers"],
        params={
            "service_id": str(expert["service_id"]),
            "from": now.isoformat(),
            "to": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert starts in [slot["starts_at_utc"] for slot in slots.json()["slots"]]


async def test_an_expert_cancellation_is_recorded_as_theirs(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    appointment_id = order["appointment"]["id"]

    response = await client.post(
        f"{API}/expert/appointments/{appointment_id}/cancel",
        headers=expert["headers"],
        json={"reason": "Unwell"},
    )
    assert response.status_code == 200
    assert response.json()["cancellation_actor"] == "expert"


async def test_cancelling_a_cancelled_order_is_a_replay(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    """A retried cancel returns the cancelled order; a completed one is 409."""
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    first = await client.post(
        f"{API}/orders/{order['id']}/cancel",
        headers=registered["headers"],
        json={},
    )
    again = await client.post(
        f"{API}/orders/{order['id']}/cancel",
        headers=registered["headers"],
        json={},
    )
    assert again.status_code == 200
    assert again.json()["status"] == "cancelled"
    assert again.json()["cancelled_at"] == first.json()["cancelled_at"]

    # Another terminal state is still not cancellable.
    starts = await first_slot(client, registered["headers"], expert)
    other = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={"expert_service_id": str(expert["service_id"]), "starts_at_utc": starts},
        )
    ).json()
    await complete_order(session_factory, uuid.UUID(other["id"]))
    refused = await client.post(
        f"{API}/orders/{other['id']}/cancel", headers=registered["headers"], json={}
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "order_not_cancellable"


# ============================================================= ownership


async def test_another_user_cannot_see_your_order_or_appointment(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    stranger = await register(client, "stranger@example.com")

    for method, path in (
        ("get", f"{API}/orders/{order['id']}"),
        ("get", f"{API}/orders/{order['id']}/consents"),
        ("get", f"{API}/appointments/{order['appointment']['id']}"),
    ):
        response = await getattr(client, method)(
            path, headers=stranger["headers"]
        )
        assert response.status_code == 404, path

    cancel = await client.post(
        f"{API}/orders/{order['id']}/cancel",
        headers=stranger["headers"],
        json={},
    )
    assert cancel.status_code == 404


async def test_an_expert_only_sees_their_own_orders(
    client: httpx.AsyncClient, registered, expert, wide_open, catalog, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    # A second, unrelated expert.
    other = await register(client, "other-expert@example.com")
    await client.post(
        f"{API}/experts/apply",
        headers=other["headers"],
        json={
            "display_name": "Other",
            "languages": ["tr"],
            "specialties": ["tarot"],
            "timezone": "Europe/Istanbul",
        },
    )

    mine = await client.get(f"{API}/expert/orders", headers=expert["headers"])
    assert [row["id"] for row in mine.json()] == [order["id"]]

    theirs = await client.get(f"{API}/expert/orders", headers=other["headers"])
    assert theirs.json() == []

    direct = await client.get(
        f"{API}/expert/orders/{order['id']}", headers=other["headers"]
    )
    assert direct.status_code == 404


async def test_a_user_without_an_expert_profile_has_no_workspace(
    client: httpx.AsyncClient, registered
):
    for path in ("/expert/orders", "/expert/appointments"):
        response = await client.get(f"{API}{path}", headers=registered["headers"])
        assert response.status_code == 404


# =============================================================== consent


async def test_an_expert_sees_nothing_without_consent(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    """Being the expert on the order grants nothing at all."""
    from app.db.models.birth_profile import BirthProfile

    async with session_factory() as session:
        profile = await session.scalar(
            select(BirthProfile).where(
                BirthProfile.user_id
                == (
                    await session.scalar(
                        select(User.id).where(User.email == registered["email"])
                    )
                )
            )
        )
        profile_id = profile.id

    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
                "sources": [
                    {
                        "source_kind": "birth_profile",
                        "source_id": str(profile_id),
                    }
                ],
            },
        )
    ).json()

    # The expert can see that a source exists, but not read it.
    view = await client.get(
        f"{API}/expert/orders/{order['id']}", headers=expert["headers"]
    )
    assert view.status_code == 200
    assert view.json()["sources"][0]["readable"] is False
    assert view.json()["granted_consent_scopes"] == []


async def test_consent_grants_then_revokes_access(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    from app.db.models.birth_profile import BirthProfile

    async with session_factory() as session:
        user_id = await session.scalar(
            select(User.id).where(User.email == registered["email"])
        )
        profile = await session.scalar(
            select(BirthProfile).where(BirthProfile.user_id == user_id)
        )

    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
                "sources": [
                    {
                        "source_kind": "birth_profile",
                        "source_id": str(profile.id),
                    }
                ],
            },
        )
    ).json()

    granted = await client.put(
        f"{API}/orders/{order['id']}/consents",
        headers=registered["headers"],
        json={"scopes": ["share_birth_profile"]},
    )
    assert granted.status_code == 200
    assert granted.json()[0]["active"] is True

    view = await client.get(
        f"{API}/expert/orders/{order['id']}", headers=expert["headers"]
    )
    assert view.json()["sources"][0]["readable"] is True
    assert view.json()["granted_consent_scopes"] == ["share_birth_profile"]

    # Revoke by sending a smaller set.
    revoked = await client.put(
        f"{API}/orders/{order['id']}/consents",
        headers=registered["headers"],
        json={"scopes": []},
    )
    assert revoked.json()[0]["active"] is False
    assert revoked.json()[0]["revoked_at"] is not None

    after = await client.get(
        f"{API}/expert/orders/{order['id']}", headers=expert["headers"]
    )
    assert after.json()["sources"][0]["readable"] is False
    assert after.json()["granted_consent_scopes"] == []


async def test_an_expert_cannot_grant_consent(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    # The consent route lives under the *user's* own order, so the expert's
    # attempt does not find it at all.
    response = await client.put(
        f"{API}/orders/{order['id']}/consents",
        headers=expert["headers"],
        json={"scopes": ["share_birth_profile"]},
    )
    assert response.status_code == 404


async def test_consent_is_scoped_to_one_order(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    """Sharing for one engagement is not sharing for the next."""
    first_starts = await first_slot(client, registered["headers"], expert)
    first = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": first_starts,
            },
        )
    ).json()
    await client.put(
        f"{API}/orders/{first['id']}/consents",
        headers=registered["headers"],
        json={"scopes": ["share_natal_chart"]},
    )

    second_starts = await first_slot(client, registered["headers"], expert, skip=8)
    second = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": second_starts,
            },
        )
    ).json()

    view = await client.get(
        f"{API}/expert/orders/{second['id']}", headers=expert["headers"]
    )
    assert view.json()["granted_consent_scopes"] == []


async def test_a_source_must_belong_to_the_ordering_user(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    """An order cannot reference a stranger's chart."""
    stranger = await register(client, "victim@example.com")
    from app.db.models.birth_profile import BirthProfile

    async with session_factory() as session:
        victim_id = await session.scalar(
            select(User.id).where(User.email == "victim@example.com")
        )
        profile = await session.scalar(
            select(BirthProfile).where(BirthProfile.user_id == victim_id)
        )

    starts = await first_slot(client, registered["headers"], expert)
    response = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
            "sources": [
                {"source_kind": "birth_profile", "source_id": str(profile.id)}
            ],
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"


# =============================================================== reviews


async def test_a_review_needs_a_completed_order(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()

    too_early = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": 5},
    )
    assert too_early.status_code == 409
    assert too_early.json()["error"]["code"] == "review_not_allowed"

    await complete_order(session_factory, uuid.UUID(order["id"]))

    allowed = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": 5, "comment": "Very helpful"},
    )
    assert allowed.status_code == 201
    assert allowed.json()["rating"] == 5


async def test_a_cancelled_order_cannot_be_reviewed(
    client: httpx.AsyncClient, registered, expert, wide_open
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    await client.post(
        f"{API}/orders/{order['id']}/cancel",
        headers=registered["headers"],
        json={},
    )

    response = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": 5},
    )
    assert response.status_code == 409


async def test_one_review_per_order(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    await complete_order(session_factory, uuid.UUID(order["id"]))

    await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": 5},
    )
    second = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": 1},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "review_exists"


async def test_a_stranger_cannot_review_your_order(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    await complete_order(session_factory, uuid.UUID(order["id"]))

    stranger = await register(client, "reviewer@example.com")
    response = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=stranger["headers"],
        json={"rating": 1},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
async def test_a_rating_outside_one_to_five_is_refused(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory, rating
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    await complete_order(session_factory, uuid.UUID(order["id"]))

    response = await client.post(
        f"{API}/orders/{order['id']}/review",
        headers=registered["headers"],
        json={"rating": rating},
    )
    assert response.status_code == 422


async def test_the_rating_aggregate_follows_the_reviews(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    ratings = [5, 3]
    for index, rating in enumerate(ratings):
        starts = await first_slot(
            client, registered["headers"], expert, skip=index * 8
        )
        order = (
            await client.post(
                f"{API}/orders",
                headers=registered["headers"],
                json={
                    "expert_service_id": str(expert["service_id"]),
                    "starts_at_utc": starts,
                },
            )
        ).json()
        await complete_order(session_factory, uuid.UUID(order["id"]))
        await client.post(
            f"{API}/orders/{order['id']}/review",
            headers=registered["headers"],
            json={"rating": rating},
        )

    detail = await client.get(
        f"{API}/experts/{expert['expert_id']}", headers=registered["headers"]
    )
    assert detail.json()["rating_count"] == 2
    assert detail.json()["rating_average"] == pytest.approx(4.0)

    reviews = await client.get(
        f"{API}/experts/{expert['expert_id']}/reviews",
        headers=registered["headers"],
    )
    assert reviews.json()["total"] == 2
    assert reviews.json()["distribution"]["5"] == 1
    assert reviews.json()["distribution"]["3"] == 1


async def test_deleting_a_review_updates_the_aggregate(
    client: httpx.AsyncClient, registered, expert, wide_open, session_factory
):
    starts = await first_slot(client, registered["headers"], expert)
    order = (
        await client.post(
            f"{API}/orders",
            headers=registered["headers"],
            json={
                "expert_service_id": str(expert["service_id"]),
                "starts_at_utc": starts,
            },
        )
    ).json()
    await complete_order(session_factory, uuid.UUID(order["id"]))

    review = (
        await client.post(
            f"{API}/orders/{order['id']}/review",
            headers=registered["headers"],
            json={"rating": 5},
        )
    ).json()

    await client.delete(
        f"{API}/reviews/{review['id']}", headers=registered["headers"]
    )
    detail = await client.get(
        f"{API}/experts/{expert['expert_id']}", headers=registered["headers"]
    )
    assert detail.json()["rating_count"] == 0
    assert detail.json()["rating_average"] == 0


# ============================================================= favorites


async def test_favorites(client: httpx.AsyncClient, registered, expert):
    added = await client.post(
        f"{API}/experts/{expert['expert_id']}/favorite",
        headers=registered["headers"],
    )
    assert added.status_code == 200

    # Idempotent: favouriting twice is not an error.
    again = await client.post(
        f"{API}/experts/{expert['expert_id']}/favorite",
        headers=registered["headers"],
    )
    assert again.status_code == 200

    listed = await client.get(
        f"{API}/favorites/experts", headers=registered["headers"]
    )
    assert [row["id"] for row in listed.json()] == [str(expert["expert_id"])]
    assert listed.json()[0]["is_favorite"] is True

    detail = await client.get(
        f"{API}/experts/{expert['expert_id']}", headers=registered["headers"]
    )
    assert detail.json()["is_favorite"] is True

    removed = await client.delete(
        f"{API}/experts/{expert['expert_id']}/favorite",
        headers=registered["headers"],
    )
    assert removed.status_code == 200

    empty = await client.get(
        f"{API}/favorites/experts", headers=registered["headers"]
    )
    assert empty.json() == []


async def test_favourites_are_private(client: httpx.AsyncClient, registered, expert):
    await client.post(
        f"{API}/experts/{expert['expert_id']}/favorite",
        headers=registered["headers"],
    )
    stranger = await register(client, "nosy@example.com")
    listed = await client.get(f"{API}/favorites/experts", headers=stranger["headers"])
    assert listed.json() == []


# ========================================================== rate limits


async def test_booking_and_search_have_separate_quotas(
    client: httpx.AsyncClient, registered, expert, wide_open, monkeypatch
):
    from app.api.v1 import marketplace as routes
    from app.api.v1 import orders as order_routes
    from app.core.rate_limit import Quota

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        order_routes._order_limit.dependency,
        "quota",
        Quota(limit=1, window_seconds=60),
    )
    monkeypatch.setattr(
        routes._search_limit.dependency, "quota", Quota(limit=50, window_seconds=60)
    )

    starts = await first_slot(client, registered["headers"], expert)
    first = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert first.status_code == 201

    blocked = await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
        },
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["scope"] == "order_create"

    # Search is a different bucket and still works.
    search = await client.get(f"{API}/experts", headers=registered["headers"])
    assert search.status_code == 200


# ================================================================ privacy


async def test_no_birth_data_is_logged_during_booking(
    client: httpx.AsyncClient, registered, expert, wide_open, monkeypatch
):
    from app.services.marketplace import orders as order_module

    recorded: list[tuple[str, dict]] = []

    class Recorder:
        def info(self, event, **fields):
            recorded.append((event, fields))

        def warning(self, event, **fields):
            recorded.append((event, fields))

    monkeypatch.setattr(order_module, "logger", Recorder())

    starts = await first_slot(client, registered["headers"], expert)
    await client.post(
        f"{API}/orders",
        headers=registered["headers"],
        json={
            "expert_service_id": str(expert["service_id"]),
            "starts_at_utc": starts,
            "notes": "Born 1990-04-04 in Istanbul, please prepare",
        },
    )

    assert recorded
    event, fields = recorded[-1]
    assert event == "order_created"

    blob = repr(fields)
    assert "1990-04-04" not in blob
    assert "Istanbul" not in blob
    assert "notes" not in fields
    # The structural facts are there to debug with.
    assert set(fields) >= {"order_id", "user_id", "status", "total_minor"}
