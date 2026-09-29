"""Solar and lunar return charts plus their deterministic themes.

The charts come from ``ReturnEngine`` (root-searched return instants). The
theme is read off fixed placements - return Sun/Moon houses, the return
Ascendant, angular planets and the tightest aspects - never generated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.exceptions import MissingBirthData
from app.domain.astrology import Chart
from app.domain.enums import Planet, ZodiacSign
from app.services.astrology.houses import house_of
from app.services.astrology.returns import ReturnEngine, get_return_engine
from app.services.guides import content
from app.services.guides.content import pick

ANGULAR_HOUSES = (1, 4, 7, 10)
RETURNS_GUIDE_VERSION = "returns_guide_v1"


@dataclass(slots=True)
class ReturnTheme:
    headline: str
    lines: list[str] = field(default_factory=list)
    focus_houses: list[int] = field(default_factory=list)
    angular_planets: list[Planet] = field(default_factory=list)
    ascendant_in_natal_house: int | None = None


@dataclass(slots=True)
class ReturnReading:
    kind: str
    moment: datetime
    chart: Chart
    theme: ReturnTheme
    version: str = RETURNS_GUIDE_VERSION


class ReturnsGuide:
    def __init__(self, engine: ReturnEngine | None = None) -> None:
        self._engine = engine or get_return_engine()

    def solar(
        self,
        natal: Chart,
        year: int,
        *,
        locale: str = "tr",
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
    ) -> ReturnReading:
        chart = self._engine.solar_return_chart(
            natal, year, latitude=latitude, longitude=longitude, timezone=timezone
        )
        if chart is None:
            raise MissingBirthData("Solar return needs a natal Sun.", code="return_unavailable")
        return ReturnReading(
            kind="solar_return",
            moment=chart.moment_utc,
            chart=chart,
            theme=self._theme(chart, natal, solar=True, locale=locale),
        )

    def lunar(
        self,
        natal: Chart,
        after: datetime,
        *,
        locale: str = "tr",
        latitude: float | None = None,
        longitude: float | None = None,
        timezone: str | None = None,
    ) -> ReturnReading:
        chart = self._engine.lunar_return_chart(
            natal, after=after, latitude=latitude, longitude=longitude, timezone=timezone
        )
        if chart is None:
            raise MissingBirthData("Lunar return needs a natal Moon.", code="return_unavailable")
        return ReturnReading(
            kind="lunar_return",
            moment=chart.moment_utc,
            chart=chart,
            theme=self._theme(chart, natal, solar=False, locale=locale),
        )

    # ------------------------------------------------------------ internals

    def _theme(self, chart: Chart, natal: Chart, *, solar: bool, locale: str) -> ReturnTheme:
        period = pick(("yıl", "year"), locale) if solar else pick(("ay", "month"), locale)
        sun = chart.position(Planet.SUN)
        moon = chart.position(Planet.MOON)
        lines: list[str] = []
        focus: list[int] = []

        anchor = sun if solar else moon
        if anchor is not None and anchor.house is not None:
            topic = pick(content.HOUSE_TOPICS[anchor.house], locale)
            focus.append(anchor.house)
            headline = pick(
                (
                    f"Bu {period} öne çıkan alan: {topic} ({anchor.house}. ev).",
                    f"This {period}'s focus: {topic} (house {anchor.house}).",
                ),
                locale,
            )
        else:
            headline = pick(
                (
                    f"Bu {period} için ev temaları doğum saati olmadan hesaplanamaz.",
                    f"House themes for this {period} need a birth time.",
                ),
                locale,
            )

        asc_house: int | None = None
        if chart.angles is not None:
            asc_sign = ZodiacSign.from_longitude(chart.angles.ascendant)
            lines.append(
                pick(
                    (
                        f"Dönüş yükseleni {pick(content.SIGN_NAMES[asc_sign], locale)}: "
                        f"bu {period} tavrın {pick(content.SIGN_MOODS[asc_sign], locale)}.",
                        f"Return Ascendant {pick(content.SIGN_NAMES[asc_sign], locale)}: "
                        f"your approach this {period} is {pick(content.SIGN_MOODS[asc_sign], locale)}.",
                    ),
                    locale,
                )
            )
            asc_house = house_of(chart.angles.ascendant, natal.houses)
            if asc_house is not None:
                lines.append(
                    pick(
                        (
                            f"Dönüş yükseleni natal {asc_house}. evine düşüyor: "
                            f"{pick(content.HOUSE_TOPICS[asc_house], locale)} konusu kişisel gündemin.",
                            f"The return Ascendant falls in your natal {asc_house}th house: "
                            f"{pick(content.HOUSE_TOPICS[asc_house], locale)} become personal.",
                        ),
                        locale,
                    )
                )

        if solar and moon is not None:
            moon_sign = pick(content.SIGN_NAMES[moon.sign], locale)
            if moon.house is not None:
                focus.append(moon.house)
                lines.append(
                    pick(
                        (
                            f"Dönüş Ay'ı {moon_sign} burcunda, {moon.house}. evde: duygusal ihtiyaçlar "
                            f"{pick(content.HOUSE_TOPICS[moon.house], locale)} etrafında.",
                            f"Return Moon in {moon_sign}, house {moon.house}: emotional needs centre on "
                            f"{pick(content.HOUSE_TOPICS[moon.house], locale)}.",
                        ),
                        locale,
                    )
                )

        angular = [
            p.planet
            for p in chart.positions
            if p.house in ANGULAR_HOUSES and not p.planet.is_point
        ]
        for planet in angular[:4]:
            position = chart.position(planet)
            assert position is not None and position.house is not None
            lines.append(
                pick(
                    (
                        f"{pick(content.PLANET_NAMES[planet], locale)} açısal evde ({position.house}. ev): "
                        f"{pick(content.PLANET_THEMES[planet], locale)} belirgin.",
                        f"{pick(content.PLANET_NAMES[planet], locale)} is angular (house {position.house}): "
                        f"{pick(content.PLANET_THEMES[planet], locale)} is prominent.",
                    ),
                    locale,
                )
            )

        for hit in chart.aspects[:3]:
            lines.append(
                pick(
                    (
                        f"{pick(content.PLANET_NAMES[hit.first], locale)} "
                        f"{pick(content.ASPECT_NAMES[hit.aspect.value], locale)} "
                        f"{pick(content.PLANET_NAMES[hit.second], locale)} (orb {hit.orb:.1f}°)",
                        f"{pick(content.PLANET_NAMES[hit.first], locale)} "
                        f"{pick(content.ASPECT_NAMES[hit.aspect.value], locale)} "
                        f"{pick(content.PLANET_NAMES[hit.second], locale)} (orb {hit.orb:.1f}°)",
                    ),
                    locale,
                )
            )

        return ReturnTheme(
            headline=headline,
            lines=lines,
            focus_houses=sorted(set(focus)),
            angular_planets=angular,
            ascendant_in_natal_house=asc_house,
        )


_guide: ReturnsGuide | None = None


def get_returns_guide() -> ReturnsGuide:
    global _guide
    if _guide is None:
        _guide = ReturnsGuide()
    return _guide
