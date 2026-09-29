"""AstroAIContextBuilder.

Selects the *relevant* verified material for one request and nothing else. The
model never receives a whole database or a whole chart "just in case": a large
context is expensive, dilutes attention, and makes it harder to tell what an
answer actually rests on.

Two rules hold everywhere:

* every factor carries an id, reusing the engine's own ids from B4/B5 wherever
  they exist, so a sentence can be traced back to the transit card the app
  already shows,
* context is **data**. The prompt says so, and nothing in a factor is ever
  executed as an instruction.

``context_selection_v1``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from app.domain.ai import (
    AstroContext,
    ContextFactor,
    ContextType,
    FactorImportance,
    Locale,
)
from app.domain.astrology import Chart
from app.services.ai.context import budget as budget_module
from app.services.ai.context.budget import CRITICAL, HIGH, LOW, MEDIUM

CONTEXT_VERSION = "context_selection_v1"

# How many of each kind survive selection before budgeting even starts.
LIMITS = {
    "natal_aspects": 12,
    "transits": 14,
    "ingresses": 6,
    "moon_events": 6,
    "important_dates": 10,
    "key_periods": 6,
    "synastry_aspects": 18,
    "overlays": 10,
    "composite_aspects": 12,
    "horary_aspects": 10,
}


def fingerprint(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def factor(
    factor_id: str,
    factor_type: str,
    importance: FactorImportance,
    data: dict,
    *,
    label: str = "",
    at: datetime | None = None,
) -> ContextFactor:
    return ContextFactor(
        factor_id=factor_id,
        factor_type=factor_type,
        importance=importance,
        structured_data=data,
        label=label,
        at=at,
    )


class AstroAIContextBuilder:
    """Turns engine output into a bounded, grounded context."""

    version = CONTEXT_VERSION

    # ------------------------------------------------------------- natal

    def natal(
        self,
        chart: Chart,
        *,
        locale: Locale,
        subject: dict,
        focus: str | None = None,
        token_budget: int,
    ) -> AstroContext:
        factors: list[ContextFactor] = []

        for position in chart.positions:
            importance = (
                HIGH
                if position.planet.is_luminary or position.planet.is_personal
                else MEDIUM
            )
            factors.append(
                factor(
                    f"natal:planet:{position.planet.value}",
                    "natal_planet",
                    importance,
                    {
                        "planet": position.planet.value,
                        "sign": position.sign.value,
                        "degree": position.degree,
                        "minute": position.minute,
                        "house": position.house,
                        "retrograde": position.retrograde,
                    },
                    label=f"{position.planet.value} in {position.sign.value}",
                )
            )

        if chart.angles is not None:
            for name, longitude in (
                ("asc", chart.angles.ascendant),
                ("mc", chart.angles.midheaven),
            ):
                from app.domain.enums import ZodiacSign

                factors.append(
                    factor(
                        f"natal:angle:{name}",
                        "natal_angle",
                        CRITICAL if name == "asc" else HIGH,
                        {
                            "angle": name,
                            "sign": ZodiacSign.from_longitude(longitude).value,
                            "degree": int(longitude % 30),
                        },
                        label=f"{name} in {ZodiacSign.from_longitude(longitude).value}",
                    )
                )

        for hit in chart.aspects[: LIMITS["natal_aspects"]]:
            factors.append(
                factor(
                    f"natal:aspect:{hit.first.value}:{hit.second.value}:{hit.aspect.value}",
                    "natal_aspect",
                    HIGH if hit.orb <= 2 else MEDIUM,
                    {
                        "first": hit.first.value,
                        "second": hit.second.value,
                        "aspect": hit.aspect.value,
                        "nature": hit.aspect.nature.value,
                        "orb": round(hit.orb, 2),
                        "applying": hit.applying,
                    },
                    label=f"{hit.first.value} {hit.aspect.value} {hit.second.value}",
                )
            )

        for house in chart.houses:
            factors.append(
                factor(
                    f"natal:house:{house.number}",
                    "natal_house",
                    LOW,
                    {
                        "house": house.number,
                        "sign": house.sign.value,
                        "degree": house.degree,
                        "ruler": chart.house_rulers.get(house.number, "").value
                        if chart.house_rulers.get(house.number)
                        else None,
                    },
                )
            )

        factors.append(
            factor(
                "natal:dominants",
                "natal_summary",
                CRITICAL,
                {
                    "dominant_planet": chart.dominant_planet.value,
                    "dominant_element": chart.dominant_element.value,
                    "dominant_modality": chart.dominant_modality.value,
                    "elements": {
                        key.value: value
                        for key, value in chart.element_distribution.items()
                    },
                    "modalities": {
                        key.value: value
                        for key, value in chart.modality_distribution.items()
                    },
                    "big_three": [
                        sign.value if sign else None for sign in chart.big_three_signs
                    ],
                },
                label="chart summary",
            )
        )

        if focus:
            factors = self._apply_focus(factors, focus)

        warnings: list[str] = []
        if chart.birth_data is not None and not chart.birth_data.time_known:
            warnings.append(
                "birth_time_unknown: houses and angles are unavailable and the "
                "Moon may be off by up to 13 degrees."
            )

        return self._finalise(
            ContextType.NATAL,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={"focus": focus, "house_system": chart.house_system.value},
            fingerprint_payload={"chart": chart.subject.moment_utc.isoformat(), "focus": focus},
        )

    # ---------------------------------------------------------- transits

    def transits(
        self,
        payload: dict,
        *,
        locale: Locale,
        subject: dict,
        token_budget: int,
        context_type: ContextType = ContextType.TRANSIT,
    ) -> AstroContext:
        """From the `/astrology/transits` response shape (B4)."""
        factors: list[ContextFactor] = []
        groups = ("active", "approaching", "upcoming")

        seen = 0
        for group in groups:
            for item in payload.get(group, []):
                if seen >= LIMITS["transits"]:
                    break
                seen += 1
                exact = item.get("exact_at")
                # An exact contact inside the window is the thing the reading
                # is about; it is never trimmed for budget.
                importance = (
                    CRITICAL
                    if item.get("status") == "exact" or item.get("strength", 0) >= 60
                    else HIGH
                    if item.get("strength", 0) >= 35
                    else MEDIUM
                )
                factors.append(
                    factor(
                        item["id"],
                        "transit",
                        importance,
                        {
                            "group": group,
                            "transiting_body": item["transiting_body"],
                            "target": item.get("target_body")
                            or item.get("target_angle")
                            or (
                                f"house_{item['target_house']}"
                                if item.get("target_house")
                                else None
                            ),
                            "aspect": item.get("aspect_type"),
                            "nature": item.get("nature"),
                            "orb": item.get("orb"),
                            "applying": item.get("applying"),
                            "status": item.get("status"),
                            "strength": item.get("strength"),
                            "start_at": item.get("start_at"),
                            "exact_at": exact,
                            "end_at": item.get("end_at"),
                            "passes": [
                                {
                                    "pass_number": p["pass_number"],
                                    "exact_at": p["exact_at"],
                                    "direction": p["direction"],
                                }
                                for p in item.get("passes", [])
                            ],
                            "affected_houses": item.get("affected_houses", []),
                            "window_clipped": item.get("window_clipped", False),
                        },
                        label=(
                            f"{item['transiting_body']} {item.get('aspect_type')} "
                            f"{item.get('target_body') or item.get('target_angle')}"
                        ),
                    )
                )

        for item in payload.get("ingresses", [])[: LIMITS["ingresses"]]:
            factors.append(
                factor(
                    item["id"],
                    "house_ingress",
                    MEDIUM,
                    {
                        "planet": item["planet"],
                        "from_house": item["from_house"],
                        "to_house": item["to_house"],
                        "entered_at": item["entered_at"],
                        "estimated_exit_at": item.get("estimated_exit_at"),
                        "retrograde": item.get("retrograde"),
                        "re_entry": item.get("re_entry"),
                    },
                    label=f"{item['planet']} enters house {item['to_house']}",
                )
            )

        warnings = [
            "Transit dates come from the engine. Do not estimate or round them."
        ]
        if any(
            item.get("window_clipped")
            for group in groups
            for item in payload.get(group, [])
        ):
            warnings.append(
                "window_clipped: some windows run past the search horizon, so "
                "their start or end is a bound rather than the real edge."
            )

        return self._finalise(
            context_type,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={
                "range": payload.get("range"),
                "reference": payload.get("reference"),
                "timezone": payload.get("timezone"),
            },
            fingerprint_payload={
                "range": payload.get("range"),
                "start": payload.get("start_at"),
                "ids": sorted(item.factor_id for item in factors),
            },
        )

    # ---------------------------------------------------------- forecast

    def daily(
        self, payload: dict, *, locale: Locale, subject: dict, token_budget: int
    ) -> AstroContext:
        factors = [
            factor(
                "daily:scores",
                "daily_scores",
                CRITICAL,
                {
                    "overall": payload["overall"],
                    "scores": {
                        key: {
                            "score": value["score"],
                            "trend": value["trend"],
                            "factor_ids": value.get("factor_ids", [])[:4],
                        }
                        for key, value in payload["scores"].items()
                    },
                },
                label="daily scores",
            )
        ]

        for hour in payload.get("important_hours", []):
            factors.append(
                factor(
                    f"daily:hour:{hour['start']}",
                    "important_hour",
                    HIGH,
                    {
                        "start": hour["start"],
                        "end": hour["end"],
                        "type": hour["type"],
                        "strength": hour["strength"],
                        "reason": hour["reason"],
                        "factor_ids": hour.get("factor_ids", []),
                    },
                    label=hour["reason"],
                )
            )

        for influence in payload.get("influences", [])[:10]:
            factors.append(
                factor(
                    influence["id"],
                    "influence",
                    HIGH if abs(influence.get("contribution", 0)) >= 0.4 else MEDIUM,
                    {
                        "kind": influence["kind"],
                        "label": influence["label"],
                        "contribution": influence["contribution"],
                        "areas": influence.get("areas", []),
                        "detail": influence.get("detail", {}),
                    },
                    label=influence["label"],
                )
            )

        context = payload.get("message_context", {})
        if context:
            factors.append(
                factor(
                    "daily:moon_context",
                    "moon_context",
                    HIGH,
                    context,
                    label="moon placement today",
                )
            )

        return self._finalise(
            ContextType.DAILY,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=[],
            token_budget=token_budget,
            metadata={"date": payload.get("date"), "timezone": payload.get("timezone")},
            fingerprint_payload={"date": payload.get("date"), "overall": payload.get("overall")},
        )

    def horoscope(
        self,
        payload: dict,
        *,
        context_type: ContextType,
        locale: Locale,
        subject: dict,
        token_budget: int,
    ) -> AstroContext:
        """Weekly / monthly / yearly structured forecasts (B4)."""
        factors: list[ContextFactor] = [
            factor(
                f"{context_type.value}:areas",
                "area_scores",
                CRITICAL,
                {
                    "overall": payload.get("overall") or payload.get("overall_score"),
                    "areas": [
                        {
                            "area": item["area"],
                            "score": item["score"],
                            "trend": item["trend"],
                            "factor_ids": item.get("factor_ids", [])[:4],
                        }
                        for item in payload.get("areas", [])
                    ],
                    "general_theme": payload.get("general_theme", []),
                },
                label="scored areas",
            )
        ]

        for item in payload.get("key_periods", [])[: LIMITS["key_periods"]]:
            factors.append(
                factor(
                    f"period:{item['start_at']}",
                    "key_period",
                    CRITICAL,
                    {
                        "start_at": item["start_at"],
                        "end_at": item["end_at"],
                        "areas": item["areas"],
                        "strength": item["strength"],
                        "source_factors": item.get("source_factors", [])[:6],
                    },
                    label=item.get("label", "key period"),
                )
            )

        for item in payload.get("important_dates", [])[: LIMITS["important_dates"]]:
            factors.append(
                factor(
                    f"date:{item['date']}:{item['label']}",
                    "important_date",
                    HIGH,
                    {
                        "date": item["date"],
                        "label": item["label"],
                        "strength": item["strength"],
                        "nature": item["nature"],
                        "factor_ids": item.get("factor_ids", []),
                    },
                    label=item["label"],
                )
            )

        for item in payload.get("major_transits", [])[: LIMITS["transits"]]:
            factors.append(
                factor(
                    item["id"],
                    "transit",
                    HIGH if item.get("strength", 0) >= 45 else MEDIUM,
                    {
                        "transiting_body": item["transiting_body"],
                        "target": item.get("target_body") or item.get("target_angle"),
                        "aspect": item.get("aspect_type"),
                        "strength": item.get("strength"),
                        "exact_at": item.get("exact_at"),
                        "start_at": item.get("start_at"),
                        "end_at": item.get("end_at"),
                        "passes": len(item.get("passes", [])),
                    },
                )
            )

        for key, importance in (
            ("moon_events", MEDIUM),
            ("retrogrades", HIGH),
            ("eclipses", CRITICAL),
        ):
            for item in payload.get(key, [])[: LIMITS["moon_events"]]:
                factors.append(
                    factor(
                        item["id"],
                        key.rstrip("s"),
                        importance,
                        {
                            "type": item["type"],
                            "exact_at": item["exact_at"],
                            "start_at": item.get("start_at"),
                            "end_at": item.get("end_at"),
                            "planet": item.get("planet"),
                            "sign": item.get("sign"),
                            "eclipse_subtype": item.get("eclipse_subtype"),
                        },
                        label=item["type"],
                    )
                )

        for item in payload.get("house_activations", [])[:6]:
            factors.append(
                factor(
                    f"house_activation:{item['house']}",
                    "house_activation",
                    MEDIUM,
                    {
                        "house": item["house"],
                        "planets": item["planets"],
                        "strength": item["strength"],
                    },
                )
            )

        if payload.get("solar_return"):
            factors.append(
                factor(
                    "solar_return",
                    "solar_return",
                    HIGH,
                    payload["solar_return"],
                    label="solar return",
                )
            )

        warnings: list[str] = []
        if payload.get("eclipses"):
            warnings.append(
                "Eclipse subtypes for solar eclipses are intentionally null: "
                "the engine does not compute them. Do not state one."
            )

        return self._finalise(
            context_type,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={
                "start_at": payload.get("start_at"),
                "end_at": payload.get("end_at"),
                "timezone": payload.get("timezone"),
                "year": payload.get("year"),
                "month": payload.get("month"),
            },
            fingerprint_payload={
                "type": context_type.value,
                "start": payload.get("start_at"),
                "overall": payload.get("overall") or payload.get("overall_score"),
            },
        )

    # ------------------------------------------------------------ horary

    def horary(
        self, payload: dict, *, locale: Locale, subject: dict, token_budget: int
    ) -> AstroContext:
        """From the B5 HoraryAnalysis payload. Nothing is recomputed."""
        factors: list[ContextFactor] = [
            factor(
                "horary:querent",
                "significator",
                CRITICAL,
                payload["querent"],
                label="querent significator",
            ),
            factor(
                "horary:quesited",
                "significator",
                CRITICAL,
                payload["quesited"],
                label="quesited significator",
            ),
            factor(
                "horary:moon",
                "moon_condition",
                CRITICAL,
                payload["moon"],
                label="moon condition",
            ),
            factor(
                "horary:houses",
                "house_assignment",
                HIGH,
                {
                    "querent_house": payload["querent_house"],
                    "quesited_house": payload["quesited_house"],
                    "alternative_quesited_houses": payload.get(
                        "alternative_quesited_houses", []
                    ),
                    "house_rulers": payload.get("house_rulers", {}),
                    "is_day_chart": payload.get("is_day_chart"),
                },
            ),
        ]

        if payload.get("co_significator"):
            factors.append(
                factor(
                    "horary:co_significator",
                    "significator",
                    HIGH,
                    payload["co_significator"],
                    label="co-significator (Moon)",
                )
            )

        for item in payload.get("receptions", []):
            factors.append(
                factor(item["id"], "reception", HIGH, item, label=item.get("note", ""))
            )
        for key, importance in (
            ("applying_aspects", CRITICAL),
            ("separating_aspects", MEDIUM),
        ):
            for item in payload.get(key, [])[: LIMITS["horary_aspects"]]:
                factors.append(factor(item["id"], key.rstrip("s"), importance, item))

        for item in payload.get("perfection_factors", []):
            factors.append(
                factor(item["id"], "perfection", CRITICAL, item, label=item["kind"])
            )
        for item in payload.get("obstruction_factors", []):
            factors.append(
                factor(item["id"], "obstruction", CRITICAL, item, label=item["kind"])
            )
        for item in payload.get("dignity_factors", []):
            factors.append(factor(item["id"], "dignity", HIGH, item))

        warnings = [item["message"] for item in payload.get("warnings", [])]
        not_implemented = payload.get("not_implemented", [])
        if not_implemented:
            warnings.append(
                "not_implemented: the engine does not detect "
                + ", ".join(not_implemented)
                + ". Do not claim any of them is present or absent, and draw no "
                "conclusion from them."
            )
        warnings.append(
            "The engine returns no verdict. Do not supply one: describe the "
            "traditional indications as supportive, challenging, mixed or "
            "unclear."
        )

        return self._finalise(
            ContextType.HORARY,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={
                "question": payload.get("question"),
                "category": payload.get("category"),
                "asked_at_utc": payload.get("asked_at_utc"),
                "not_implemented": not_implemented,
                "rules_version": payload.get("rules_version"),
                "dignity_version": payload.get("dignity_version"),
            },
            fingerprint_payload={
                "asked_at": payload.get("asked_at_utc"),
                "question": payload.get("question"),
            },
        )

    # ----------------------------------------------------- compatibility

    def synastry(
        self, payload: dict, *, locale: Locale, subject: dict, token_budget: int
    ) -> AstroContext:
        factors: list[ContextFactor] = [
            factor(
                "synastry:scores",
                "theme_scores",
                CRITICAL,
                {
                    "overall_score": payload["overall_score"],
                    "score_semantics": payload["score_semantics"],
                    "themes": [
                        {
                            "theme": item["theme"],
                            "score": item["score"],
                            "strength": item["strength"],
                        }
                        for item in payload.get("themes", [])
                    ],
                },
                label="theme scores",
            )
        ]

        for item in payload.get("aspects", [])[: LIMITS["synastry_aspects"]]:
            factors.append(
                factor(
                    item["id"],
                    "synastry_aspect",
                    HIGH if item.get("weight", 0) >= 0.45 else MEDIUM,
                    {
                        "label": item["label"],
                        "aspect": item["aspect"],
                        "nature": item["nature"],
                        "orb": item["orb"],
                        "weight": item["weight"],
                        "themes": item.get("themes", []),
                    },
                    label=item["label"],
                )
            )

        for key, direction in (
            ("overlays_a_in_b", "a_to_b"),
            ("overlays_b_in_a", "b_to_a"),
        ):
            for item in payload.get(key, [])[: LIMITS["overlays"]]:
                factors.append(
                    factor(
                        item["id"],
                        "house_overlay",
                        MEDIUM,
                        {
                            "direction": direction,
                            "planet": item["planet"],
                            "house": item["house"],
                            "weight": item["weight"],
                            "themes": item.get("themes", []),
                            "label": item["label"],
                        },
                        label=item["label"],
                    )
                )

        warnings = list(payload.get("warnings", []))
        warnings.append(
            "The compatibility score is an astrological factor index, not a "
            "probability and not a prediction. Never express it as a chance of "
            "success."
        )

        return self._finalise(
            ContextType.SYNASTRY,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={
                "person_a_label": payload.get("person_a_label"),
                "person_b_label": payload.get("person_b_label"),
                "scoring_version": payload.get("scoring_version"),
            },
            fingerprint_payload={"report": payload.get("report_id")},
        )

    def composite(
        self,
        payload: dict,
        *,
        kind: ContextType,
        locale: Locale,
        subject: dict,
        token_budget: int,
    ) -> AstroContext:
        chart = payload["chart"]
        factors: list[ContextFactor] = [
            factor(
                f"{kind.value}:summary",
                "chart_summary",
                CRITICAL,
                {
                    "method": payload.get("method"),
                    "house_method": payload.get("house_method"),
                    "dominant_element": payload.get("dominant_element")
                    or chart.get("dominant_element"),
                    "dominant_modality": payload.get("dominant_modality")
                    or chart.get("dominant_modality"),
                    "angles": chart.get("angles"),
                    "midpoint_utc": payload.get("midpoint_utc"),
                    "midpoint_latitude": payload.get("midpoint_latitude"),
                    "midpoint_longitude": payload.get("midpoint_longitude"),
                },
                label=f"{kind.value} summary",
            )
        ]

        for position in chart.get("planets", []):
            factors.append(
                factor(
                    f"{kind.value}:planet:{position['planet']}",
                    "chart_planet",
                    HIGH
                    if position["planet"] in ("sun", "moon", "venus", "mars")
                    else MEDIUM,
                    {
                        "planet": position["planet"],
                        "sign": position["sign"],
                        "degree": position["degree"],
                        "house": position.get("house"),
                    },
                )
            )

        for item in (payload.get("aspects") or chart.get("aspects") or [])[
            : LIMITS["composite_aspects"]
        ]:
            first = item.get("first")
            second = item.get("second")
            factors.append(
                factor(
                    f"{kind.value}:aspect:{first}:{second}:{item.get('aspect')}",
                    "chart_aspect",
                    MEDIUM,
                    item,
                    label=f"{first} {item.get('aspect')} {second}",
                )
            )

        warnings = list(payload.get("warnings", []))
        ambiguous = payload.get("ambiguous_midpoints") or []
        if ambiguous:
            warnings.append(
                "ambiguous_midpoints: "
                + ", ".join(ambiguous)
                + " have no unique midpoint. Treat them as uncertain rather "
                "than interpreting them as settled."
            )

        return self._finalise(
            kind,
            subject=subject,
            locale=locale,
            factors=factors,
            warnings=warnings,
            token_budget=token_budget,
            metadata={
                "method": payload.get("method"),
                "house_method": payload.get("house_method"),
            },
            fingerprint_payload={"report": payload.get("report_id")},
        )

    # ------------------------------------------------------------ chat

    def general_chat(
        self, *, locale: Locale, subject: dict, token_budget: int
    ) -> AstroContext:
        """No chart material: general astrology questions.

        The model still may not invent anything about *this* person - there is
        simply nothing personal in scope.
        """
        return self._finalise(
            ContextType.GENERAL_ASTRO_CHAT,
            subject=subject,
            locale=locale,
            factors=[],
            warnings=[
                "No personal chart material is in scope for this question. Do "
                "not state anything specific about this person's chart."
            ],
            token_budget=token_budget,
            metadata={},
            fingerprint_payload={"general": True},
        )

    # --------------------------------------------------------- internals

    def _apply_focus(
        self, factors: list[ContextFactor], focus: str
    ) -> list[ContextFactor]:
        """Raise the importance of the material a focus area needs.

        Career pulls the Midheaven, the tenth house and Saturn forward; love
        pulls Venus, Mars, the fifth and seventh. Nothing is removed - the
        budget does the removing - but the ranking changes.
        """
        keys: dict[str, tuple[str, ...]] = {
            "career": ("mc", "saturn", "jupiter", "sun", ":house:10", ":house:6"),
            "love": ("venus", "mars", "moon", ":house:5", ":house:7"),
            "relationship": ("venus", "mars", "moon", "saturn", ":house:7"),
            "money": ("venus", "jupiter", ":house:2", ":house:8"),
            "health": ("moon", "mars", "saturn", ":house:6", ":house:1"),
        }
        wanted = keys.get(focus, ())
        if not wanted:
            return factors

        promoted: list[ContextFactor] = []
        for item in factors:
            if any(key in item.factor_id for key in wanted) and not item.is_critical:
                promoted.append(
                    ContextFactor(
                        factor_id=item.factor_id,
                        factor_type=item.factor_type,
                        importance=FactorImportance.HIGH,
                        structured_data=item.structured_data,
                        label=item.label,
                        at=item.at,
                    )
                )
            else:
                promoted.append(item)
        return promoted

    def _finalise(
        self,
        context_type: ContextType,
        *,
        subject: dict,
        locale: Locale,
        factors: list[ContextFactor],
        warnings: list[str],
        token_budget: int,
        metadata: dict,
        fingerprint_payload: dict,
    ) -> AstroContext:
        kept, dropped, tokens = budget_module.trim_factors(factors, token_budget)
        return AstroContext(
            context_type=context_type,
            subject=subject,
            time_reference=datetime.now(UTC),
            locale=locale,
            factors=kept,
            warnings=warnings,
            metadata={**metadata, "selection": CONTEXT_VERSION},
            context_version=CONTEXT_VERSION,
            source_fingerprint=fingerprint(
                {**fingerprint_payload, "type": context_type.value}
            ),
            trimmed_factor_ids=dropped,
            estimated_tokens=tokens,
        )


_builder: AstroAIContextBuilder | None = None


def get_context_builder() -> AstroAIContextBuilder:
    global _builder
    if _builder is None:
        _builder = AstroAIContextBuilder()
    return _builder
