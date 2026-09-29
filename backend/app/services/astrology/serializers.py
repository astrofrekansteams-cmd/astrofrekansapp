"""Chart <-> JSON conversion for the caches.

Kept separate from the API schemas on purpose: this format is internal and
versioned by ``engine_version``, while the API schema is a public contract the
mobile client depends on.

Format version 2 stores the chart ``subject`` (instant, place, kind), so
horary, return and event charts cache through exactly the same path as natal
charts.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from app.domain.astrology import (
    AspectHit,
    BirthData,
    Chart,
    ChartAngles,
    ChartSubject,
    HousePosition,
    PlanetPosition,
)
from app.domain.enums import AspectType, ChartKind, HouseSystem, Planet

PAYLOAD_VERSION = 2


def chart_to_payload(chart: Chart) -> dict[str, Any]:
    birth = chart.birth_data
    return {
        "version": PAYLOAD_VERSION,
        "engine": chart.engine,
        "engine_version": chart.engine_version,
        "computed_at": chart.computed_at.isoformat(),
        "house_system": chart.house_system.value,
        "subject": {
            "kind": chart.subject.kind.value,
            "moment_utc": chart.subject.moment_utc.isoformat(),
            "latitude": chart.subject.latitude,
            "longitude": chart.subject.longitude,
            "timezone": chart.subject.timezone,
            "house_system": chart.subject.house_system.value,
            "location_name": chart.subject.location_name,
            "label": chart.subject.label,
        },
        "birth_data": (
            {
                "birth_date": birth.birth_date.isoformat(),
                "birth_time": birth.birth_time.isoformat() if birth.birth_time else None,
                "timezone": birth.timezone,
                "latitude": birth.latitude,
                "longitude": birth.longitude,
                "place": birth.place,
                "house_system": birth.house_system.value,
            }
            if birth is not None
            else None
        ),
        "positions": [
            {
                "planet": position.planet.value,
                "longitude": position.longitude,
                "latitude": position.latitude,
                "speed_longitude": position.speed_longitude,
                "house": position.house,
            }
            for position in chart.positions
        ],
        "houses": [
            {"number": house.number, "cusp_longitude": house.cusp_longitude}
            for house in chart.houses
        ],
        "angles": (
            {
                "ascendant": chart.angles.ascendant,
                "midheaven": chart.angles.midheaven,
            }
            if chart.angles
            else None
        ),
        "aspects": [
            {
                "first": hit.first.value,
                "second": hit.second.value,
                "aspect": hit.aspect.value,
                "orb": hit.orb,
                "applying": hit.applying,
                "exact_angle": hit.exact_angle,
            }
            for hit in chart.aspects
        ],
    }


def chart_from_payload(payload: dict[str, Any]) -> Chart:
    birth_payload = payload.get("birth_data")
    birth = (
        BirthData(
            birth_date=date.fromisoformat(birth_payload["birth_date"]),
            birth_time=(
                time.fromisoformat(birth_payload["birth_time"])
                if birth_payload["birth_time"]
                else None
            ),
            timezone=birth_payload["timezone"],
            latitude=birth_payload["latitude"],
            longitude=birth_payload["longitude"],
            place=birth_payload.get("place"),
            house_system=HouseSystem(birth_payload["house_system"]),
        )
        if birth_payload
        else None
    )

    subject_payload = payload["subject"]
    subject = ChartSubject(
        kind=ChartKind(subject_payload["kind"]),
        moment_utc=datetime.fromisoformat(subject_payload["moment_utc"]),
        latitude=subject_payload["latitude"],
        longitude=subject_payload["longitude"],
        timezone=subject_payload["timezone"],
        house_system=HouseSystem(subject_payload["house_system"]),
        location_name=subject_payload.get("location_name"),
        label=subject_payload.get("label"),
    )

    return Chart(
        subject=subject,
        computed_at=datetime.fromisoformat(payload["computed_at"]),
        engine=payload["engine"],
        engine_version=payload["engine_version"],
        positions=[
            PlanetPosition(
                planet=Planet(item["planet"]),
                longitude=item["longitude"],
                latitude=item["latitude"],
                speed_longitude=item["speed_longitude"],
                house=item["house"],
            )
            for item in payload["positions"]
        ],
        houses=[
            HousePosition(number=item["number"], cusp_longitude=item["cusp_longitude"])
            for item in payload["houses"]
        ],
        angles=(
            ChartAngles(
                ascendant=payload["angles"]["ascendant"],
                midheaven=payload["angles"]["midheaven"],
            )
            if payload.get("angles")
            else None
        ),
        aspects=[
            AspectHit(
                first=Planet(item["first"]),
                second=Planet(item["second"]),
                aspect=AspectType(item["aspect"]),
                orb=item["orb"],
                applying=item["applying"],
                exact_angle=item["exact_angle"],
            )
            for item in payload["aspects"]
        ],
        house_system=HouseSystem(payload["house_system"]),
        birth_data=birth,
    )
