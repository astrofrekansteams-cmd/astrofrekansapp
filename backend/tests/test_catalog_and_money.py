"""Service catalogue, money arithmetic and the horary chart primitive.

These cover the forward-compatibility groundwork: the catalogue every later
phase dispatches on, the money rules the marketplace will settle with, and the
fact that a horary chart is cast for the question - not for a birth date.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import httpx
import pytest

from app.domain.astrology import BirthData, ChartSubject
from app.domain.enums import ChartKind, HouseSystem, Planet, ZodiacSign
from app.domain.marketplace import (
    FulfillmentMode,
    Money,
    ServiceCategory,
    ServiceCode,
)
from app.services.astrology.skyfield_engine import get_engine
from app.services.catalog.definitions import CATALOG, CATALOG_BY_CODE
from app.services.catalog.service import CatalogService

API = "/api/v1"


# ------------------------------------------------------------------- money


def test_money_never_uses_floats():
    price = Money.from_decimal("1000.00")
    assert price.amount_minor == 100_000
    assert price.as_decimal == Decimal("1000.00")
    assert str(price) == "1000.00 TRY"


def test_money_rounds_half_up_to_minor_units():
    assert Money.from_decimal("0.005").amount_minor == 1
    assert Money.from_decimal("12.344").amount_minor == 1234
    assert Money.from_decimal("12.345").amount_minor == 1235


def test_money_refuses_to_mix_currencies():
    with pytest.raises(ValueError):
        Money(1000, "TRY") + Money(1000, "USD")
    with pytest.raises(ValueError):
        Money(1000, "TRYY")


def test_commission_split_is_exact_and_favours_the_expert():
    gross = Money.from_decimal("1000.00")
    fee, expert = gross.split_commission(2000)  # 20%

    assert fee == Money.from_decimal("200.00")
    assert expert == Money.from_decimal("800.00")
    assert fee + expert == gross

    # Remainders go to the expert, never lost to rounding.
    odd = Money(10_001, "TRY")
    fee, expert = odd.split_commission(1550)
    assert fee.amount_minor + expert.amount_minor == odd.amount_minor


def test_commission_rate_is_validated():
    with pytest.raises(ValueError):
        Money(1000).split_commission(10_001)


# --------------------------------------------------------------- catalogue


def test_catalog_covers_every_service_code():
    assert {spec.code for spec in CATALOG} == set(ServiceCode)


def test_catalog_input_requirements_are_coherent():
    horary = CATALOG_BY_CODE[ServiceCode.HORARY_QUESTION]
    assert horary.requires_question
    assert not horary.requires_birth_data  # the question moment is the chart

    synastry = CATALOG_BY_CODE[ServiceCode.SYNASTRY]
    assert synastry.requires_partner_data
    assert FulfillmentMode.HYBRID in synastry.fulfillment_modes

    daily = CATALOG_BY_CODE[ServiceCode.DAILY_HOROSCOPE]
    assert daily.fulfillment_modes == (FulfillmentMode.AUTOMATED,)
    assert daily.requires_birth_data  # personalised, not a sun-sign template

    for spec in CATALOG:
        assert spec.fulfillment_modes, f"{spec.code} has no fulfillment mode"
        # Shipped expert services must be bookable; planned ones have no
        # delivery configuration yet.
        if spec.active and FulfillmentMode.EXPERT in spec.fulfillment_modes:
            assert spec.supports_appointment, f"{spec.code} cannot be booked"


async def test_seeding_is_idempotent(db_session):
    service = CatalogService(db_session)

    created, updated = await service.seed()
    assert created == len(CATALOG)
    assert updated == 0

    created_again, updated_again = await service.seed()
    assert created_again == 0
    assert updated_again == len(CATALOG)


async def test_catalog_endpoint_lists_active_services(
    client: httpx.AsyncClient, session_factory
):
    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()

    response = await client.get(f"{API}/services")
    assert response.status_code == 200
    services = response.json()

    codes = {item["code"] for item in services}
    assert ServiceCode.HORARY_QUESTION.value in codes
    assert ServiceCode.SYNASTRY.value in codes
    # Unshipped services are hidden by default.
    assert ServiceCode.ASTROCARTOGRAPHY.value not in codes
    assert all(item["active"] for item in services)


async def test_catalog_filters(client: httpx.AsyncClient, session_factory):
    async with session_factory() as session:
        await CatalogService(session).seed()
        await session.commit()

    by_category = await client.get(
        f"{API}/services", params={"category": ServiceCategory.RELATIONSHIP.value}
    )
    assert {item["code"] for item in by_category.json()} == {
        ServiceCode.SYNASTRY.value,
        ServiceCode.RELATIONSHIP_ANALYSIS.value,
        ServiceCode.COMPOSITE_CHART.value,
        ServiceCode.DAVISON_CHART.value,
    }

    expert_only = await client.get(
        f"{API}/services", params={"fulfillment_mode": FulfillmentMode.EXPERT.value}
    )
    assert all(
        "expert" in item["fulfillment_modes"] for item in expert_only.json()
    )

    single = await client.get(f"{API}/services/{ServiceCode.HORARY_QUESTION.value}")
    assert single.status_code == 200
    assert single.json()["requires_question"] is True

    missing = await client.get(f"{API}/services/not_a_service")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


# ------------------------------------------------------------------ horary


@pytest.fixture(scope="module")
def sky():
    return get_engine()


def test_horary_chart_is_cast_for_the_question_not_a_birth(sky):
    asked_at = datetime(2026, 9, 23, 11, 0, tzinfo=UTC)
    chart = sky.horary_chart(
        asked_at=asked_at,
        latitude=41.0082,
        longitude=28.9784,
        timezone="Europe/Istanbul",
        location_name="Istanbul",
    )

    assert chart.kind is ChartKind.HORARY
    assert chart.birth_data is None
    assert chart.moment_utc == asked_at
    assert chart.subject.location_name == "Istanbul"
    assert len(chart.houses) == 12
    assert chart.angles is not None


def test_horary_chart_matches_an_event_chart_for_the_same_moment(sky):
    moment = datetime(2026, 9, 23, 11, 0, tzinfo=UTC)
    horary = sky.horary_chart(
        asked_at=moment, latitude=41.0082, longitude=28.9784, timezone="Europe/Istanbul"
    )
    event = sky.chart_for(
        ChartSubject(
            kind=ChartKind.EVENT,
            moment_utc=moment,
            latitude=41.0082,
            longitude=28.9784,
            timezone="Europe/Istanbul",
        )
    )
    # Same sky, same houses: only the label differs.
    assert [p.longitude for p in horary.positions] == [
        p.longitude for p in event.positions
    ]
    assert horary.angles.ascendant == event.angles.ascendant
    assert horary.kind is not event.kind


def test_two_questions_an_hour_apart_get_different_charts(sky):
    first = sky.horary_chart(
        asked_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        latitude=41.0082,
        longitude=28.9784,
    )
    second = sky.horary_chart(
        asked_at=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        latitude=41.0082,
        longitude=28.9784,
    )
    # The Ascendant moves roughly a sign an hour: the chart must not be reused.
    assert abs(second.angles.ascendant - first.angles.ascendant) > 5


def test_house_rulers_follow_traditional_rulership(sky):
    chart = sky.horary_chart(
        asked_at=datetime(2026, 9, 23, 11, 0, tzinfo=UTC),
        latitude=41.0082,
        longitude=28.9784,
    )
    rulers = chart.house_rulers
    assert set(rulers) == set(range(1, 13))

    from app.domain.enums import SIGN_RULERS

    for house in chart.houses:
        assert rulers[house.number] is SIGN_RULERS[house.sign]

    # The querent's ruler is the ruler of the rising sign.
    assert chart.ruler_of(1) is SIGN_RULERS[chart.houses[0].sign]


def test_natal_chart_still_carries_birth_data(sky):
    birth = BirthData(
        birth_date=date(1992, 5, 14),
        birth_time=time(14, 30),
        timezone="Europe/Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        house_system=HouseSystem.PLACIDUS,
    )
    chart = sky.natal_chart(birth)
    assert chart.kind is ChartKind.NATAL
    assert chart.birth_data == birth
    assert chart.subject.moment_utc == birth.utc_datetime
    assert chart.sun.sign is ZodiacSign.TAURUS
    assert chart.ruler_of(1) in set(Planet)


def test_chart_subject_rejects_naive_moments():
    with pytest.raises(ValueError):
        ChartSubject(
            kind=ChartKind.HORARY,
            moment_utc=datetime(2026, 9, 23, 11, 0),  # noqa: DTZ001 - the point
        )
