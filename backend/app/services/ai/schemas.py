"""Structured output schemas and their validators.

A report is only stored once it is schema-valid **and** grounded: every
specific section must cite factor ids that came from the context, or declare
itself a general summary. An id the model invented is a hallucination with a
citation attached, which is worse than an uncited sentence - so it is
rejected.

The JSON Schema handed to the provider is generated from these Pydantic models
and tightened for OpenAI strict mode (all properties required,
``additionalProperties: false``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.ai import AstroContext


class ReportSection(BaseModel):
    key: str = Field(description="Stable slug, e.g. overview, love, timing.")
    title: str
    body: str
    factor_ids: list[str] = Field(
        default_factory=list,
        description=(
            "factor_id values from the context that this section rests on. "
            "Only ids present in the context are allowed."
        ),
    )
    general_summary: bool = Field(
        default=False,
        description=(
            "True when the section is general framing rather than a claim "
            "about specific factors. Such a section may have no factor_ids."
        ),
    )


class StructuredReport(BaseModel):
    title: str
    summary: str
    sections: list[ReportSection]
    interpretation_scope: str = Field(
        description=(
            "One sentence stating what this reading is and is not, e.g. "
            "astrological interpretation for reflection, not a prediction."
        )
    )
    safety_note: str | None = Field(
        default=None,
        description=(
            "Set only when the subject touches health, money or legal matters "
            "and the reader should be pointed to a qualified professional."
        ),
    )


class ChatAnswer(BaseModel):
    answer: str
    source_factor_ids: list[str] = Field(default_factory=list)
    context_note: str | None = Field(
        default=None,
        description=(
            "Set when the context did not contain what the question needed."
        ),
    )


def strict_schema(model: type[BaseModel], name: str) -> dict[str, Any]:
    """Pydantic model -> JSON Schema the Responses API accepts in strict mode.

    Strict mode requires every property to be listed in ``required`` and
    ``additionalProperties: false`` everywhere; optional fields become
    nullable instead.
    """
    schema = model.model_json_schema()
    _tighten(schema, schema.get("$defs", {}))
    schema.pop("$defs", None)
    schema["title"] = name
    return schema


def _tighten(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node.pop("$ref")
            target = defs.get(ref.rsplit("/", 1)[-1], {})
            node.update(_tighten(dict(target), defs))

        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties", {})
            for value in properties.values():
                _tighten(value, defs)
            node["required"] = list(properties)
            node["additionalProperties"] = False

        for key in ("items", "anyOf", "allOf", "oneOf"):
            if key in node:
                node[key] = _tighten(node[key], defs)

        # Strict mode rejects unknown keywords like default/examples.
        for key in ("default", "examples", "$defs"):
            node.pop(key, None)
        return node

    if isinstance(node, list):
        return [_tighten(item, defs) for item in node]
    return node


REPORT_SCHEMA = strict_schema(StructuredReport, "astrofrekans_report")
CHAT_SCHEMA = strict_schema(ChatAnswer, "astrofrekans_chat_answer")


# ------------------------------------------------------------- validation


class GroundingError(ValueError):
    """Raised when a generation cites factors the context never supplied."""

    def __init__(self, unknown: list[str]) -> None:
        self.unknown = unknown
        super().__init__(f"Unknown factor ids: {', '.join(sorted(unknown))}")


def validate_report(payload: dict, context: AstroContext) -> StructuredReport:
    """Schema-check the payload and verify every citation.

    ``response factor ids ⊆ context factor ids``. This is the mechanism that
    keeps an interpretation tied to what the engine actually computed.
    """
    report = StructuredReport.model_validate(payload)
    allowed = context.factor_ids

    unknown: list[str] = []
    for section in report.sections:
        unknown.extend(item for item in section.factor_ids if item not in allowed)

    if unknown:
        raise GroundingError(sorted(set(unknown)))

    ungrounded = [
        section.key
        for section in report.sections
        if not section.factor_ids and not section.general_summary
    ]
    if ungrounded and allowed:
        raise GroundingError([f"section_without_factors:{key}" for key in ungrounded])

    return report


def validate_chat(payload: dict, context: AstroContext) -> ChatAnswer:
    answer = ChatAnswer.model_validate(payload)
    unknown = [
        item for item in answer.source_factor_ids if item not in context.factor_ids
    ]
    if unknown:
        raise GroundingError(sorted(set(unknown)))
    return answer


def filter_known_factor_ids(ids: list[str], context: AstroContext) -> list[str]:
    """Keep only ids the context actually contains.

    Used on the streaming path, where there is no second chance to retry: an
    invented id is dropped rather than shown to the user as a source.
    """
    allowed = context.factor_ids
    return [item for item in ids if item in allowed]
