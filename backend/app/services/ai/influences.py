"""Readable "what shaped this answer" lines for Astro AI.

The model cites factor ids; ids are for machines (transit ids are hashes). This
turns the cited or available factors back into short localized lines from
their structured engine data - "Transit Satürn kare natal Güneş" - so the
answer's astrological basis is visible. Text comes from fixed tables, never
from the model.
"""

from __future__ import annotations

from app.domain.ai import AstroContext, ContextFactor
from app.domain.enums import Planet, ZodiacSign
from app.services.guides.content import ASPECT_NAMES, PLANET_NAMES, SIGN_NAMES, pick

ANGLE_NAMES = {
    "asc": ("Yükselen", "Ascendant"),
    "ascendant": ("Yükselen", "Ascendant"),
    "mc": ("MC", "MC"),
    "midheaven": ("MC", "MC"),
    "dsc": ("Alçalan", "Descendant"),
    "descendant": ("Alçalan", "Descendant"),
    "ic": ("IC", "IC"),
    "imum_coeli": ("IC", "IC"),
}

MAX_INFLUENCES = 8


def _planet(value: str | None, locale: str) -> str:
    if not value:
        return ""
    try:
        return pick(PLANET_NAMES[Planet(value)], locale)
    except ValueError:
        angle = ANGLE_NAMES.get(value)
        if angle:
            return pick(angle, locale)
        if value.startswith("house_"):
            number = value.removeprefix("house_")
            return pick((f"{number}. ev", f"house {number}"), locale)
        return value


def _sign(value: str | None, locale: str) -> str:
    try:
        return pick(SIGN_NAMES[ZodiacSign(value)], locale) if value else ""
    except ValueError:
        return value or ""


def _aspect(value: str | None, locale: str) -> str:
    return pick(ASPECT_NAMES[value], locale) if value in ASPECT_NAMES else (value or "")


def describe(factor: ContextFactor, locale: str) -> str | None:
    data = factor.structured_data or {}
    kind = factor.factor_type
    if kind in ("natal_planet", "chart_planet"):
        house = data.get("house")
        base = pick(("Natal", "Natal"), locale) + f" {_planet(data.get('planet'), locale)} {_sign(data.get('sign'), locale)}"
        return base + (pick((f" ({house}. ev)", f" (house {house})"), locale) if house else "")
    if kind in ("natal_aspect", "chart_aspect"):
        return (
            f"{_planet(data.get('first'), locale)} {_aspect(data.get('aspect'), locale)} "
            f"{_planet(data.get('second'), locale)}"
        )
    if kind == "natal_angle":
        return f"{_planet(data.get('angle') or data.get('name'), locale)} {_sign(data.get('sign'), locale)}"
    if kind == "transit":
        target = data.get("target")
        moving = _planet(data.get("transiting_body"), locale)
        if data.get("aspect"):
            return pick(
                (
                    f"Transit {moving} {_aspect(data.get('aspect'), locale)} natal {_planet(target, locale)}",
                    f"Transit {moving} {_aspect(data.get('aspect'), locale)} natal {_planet(target, locale)}",
                ),
                locale,
            )
        return f"{moving} → {_planet(target, locale)}"
    if kind == "house_ingress":
        return pick(
            (
                f"{_planet(data.get('planet'), locale)} {data.get('to_house')}. evde",
                f"{_planet(data.get('planet'), locale)} in house {data.get('to_house')}",
            ),
            locale,
        )
    if kind == "synastry_aspect":
        return data.get("label") or factor.label or None
    if kind in ("influence", "important_date", "key_period", "important_hour"):
        return data.get("label") or factor.label or None
    if kind == "moon_context":
        return pick(
            (
                f"Ay {_sign(data.get('moon_sign') or data.get('sign'), locale)}"
                + (f", {data.get('moon_house')}. ev" if data.get("moon_house") else ""),
                f"Moon in {_sign(data.get('moon_sign') or data.get('sign'), locale)}"
                + (f", house {data.get('moon_house')}" if data.get("moon_house") else ""),
            ),
            locale,
        )
    return None  # summaries and score tables are not "influences"


def influences(
    context: AstroContext,
    locale: str,
    *,
    cited: list[str] | None = None,
) -> list[dict]:
    """Cited factors first (when the model named them), else the strongest
    available ones. Each entry: id, kind, nature, label."""
    by_id = {factor.factor_id: factor for factor in context.factors}
    if cited:
        chosen = [by_id[i] for i in cited if i in by_id]
    else:
        chosen = sorted(context.factors, key=lambda f: f.importance.rank)
    result: list[dict] = []
    for factor in chosen:
        label = describe(factor, locale)
        if not label:
            continue
        result.append(
            {
                "id": factor.factor_id,
                "kind": factor.factor_type,
                "nature": (factor.structured_data or {}).get("nature"),
                "label": label.strip(),
            }
        )
        if len(result) >= MAX_INFLUENCES:
            break
    return result
