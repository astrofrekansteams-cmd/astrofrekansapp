"""AI domain types.

The boundary this module encodes: **the engine computes, the AI explains.**
Everything astrological arrives here already computed and verified - planet
positions, aspects, exact transit times, dignities, receptions, scores - and
the model's only job is to turn those facts into language. Nothing in these
types lets a model contribute an astrological fact of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ContextType(StrEnum):
    """What kind of astrological material a request is about."""

    NATAL = "natal"
    TRANSIT = "transit"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    HORARY = "horary"
    SYNASTRY = "synastry"
    COMPOSITE = "composite"
    DAVISON = "davison"
    GENERAL_ASTRO_CHAT = "general_astro_chat"

    # Divination (B7). The draw is a fact the backend produced; the model
    # interprets it and may not change a card, an orientation or a position.
    TAROT = "tarot"
    RUNE = "rune"
    KATINA = "katina"


class ReportType(StrEnum):
    NATAL = "natal"
    TRANSIT = "transit"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    HORARY = "horary"
    SYNASTRY = "synastry"
    COMPOSITE = "composite"
    DAVISON = "davison"

    TAROT = "tarot"
    RUNE = "rune"
    KATINA = "katina"

    # Short, free readings shown under a compatibility result. Grounded in the
    # same stored calculation as the long reports above, but a different
    # product: they never replace or unlock the paid long report.
    SYNASTRY_READING = "synastry_reading"
    COMPOSITE_READING = "composite_reading"
    DAVISON_READING = "davison_reading"

    @property
    def is_divination(self) -> bool:
        return self in (ReportType.TAROT, ReportType.RUNE, ReportType.KATINA)

    @property
    def is_compatibility_reading(self) -> bool:
        return self in (
            ReportType.SYNASTRY_READING,
            ReportType.COMPOSITE_READING,
            ReportType.DAVISON_READING,
        )

    @property
    def compatibility_kind(self) -> str | None:
        """'synastry' / 'composite' / 'davison' for compatibility types."""
        return {
            ReportType.SYNASTRY: "synastry",
            ReportType.COMPOSITE: "composite",
            ReportType.DAVISON: "davison",
            ReportType.SYNASTRY_READING: "synastry",
            ReportType.COMPOSITE_READING: "composite",
            ReportType.DAVISON_READING: "davison",
        }.get(self)

    @property
    def context_type(self) -> ContextType:
        kind = self.compatibility_kind
        return ContextType(kind if kind is not None else self.value)


class ReportStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID_OUTPUT = "invalid_output"
    CANCELLED = "cancelled"


class ModelTier(StrEnum):
    LOW_COST = "low_cost"
    STANDARD = "standard"
    PREMIUM = "premium"


class UseCase(StrEnum):
    """What a call is for. Drives model tier, budget and prompt."""

    CHAT = "chat"
    INTENT = "intent"
    SUMMARY = "summary"
    TITLE = "title"
    REPORT = "report"
    INTERPRETATION = "interpretation"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"

    # Developer/system text is never stored as a user-visible message; this
    # role exists only for internal notes attached to a conversation.
    SYSTEM_NOTE = "system_note"


class CompletionStatus(StrEnum):
    """Whether a stored turn is the whole answer.

    A stream the client dropped leaves real text behind. It is worth keeping -
    the user saw it, and throwing it away would make the thread lie about what
    happened - but it is not a finished answer, and must not be presented, or
    replayed to the model, as though it were.
    """

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

    @property
    def is_complete(self) -> bool:
        return self is CompletionStatus.COMPLETED


class Intent(StrEnum):
    GENERAL = "general"
    NATAL = "natal"
    LOVE = "love"
    RELATIONSHIP = "relationship"
    CAREER = "career"
    MONEY = "money"
    TRANSIT = "transit"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    COMPATIBILITY = "compatibility"
    HORARY_REFERENCE = "horary_reference"


class Locale(StrEnum):
    TR = "tr"
    AZ = "az"
    EN = "en"

    @property
    def language_name(self) -> str:
        return {"tr": "Turkish", "az": "Azerbaijani", "en": "English"}[self.value]


class FactorImportance(StrEnum):
    """How hard a factor is to drop when the context budget is tight.

    ``CRITICAL`` factors are never trimmed: warnings, exact contacts, horary
    significators and the source a report is about. Dropping one of those to
    save tokens would change what the reading is *about*, silently.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}[self.value]


@dataclass(slots=True, frozen=True)
class ContextFactor:
    """One verified astrological fact handed to the model.

    ``factor_id`` is reused from the engine layer (B4/B5) wherever one exists,
    so a sentence in a report can be traced back to the transit card the app
    already shows. New ids are only minted for material that has none.
    """

    factor_id: str
    factor_type: str
    importance: FactorImportance
    structured_data: dict
    label: str = ""
    at: datetime | None = None

    @property
    def is_critical(self) -> bool:
        return self.importance is FactorImportance.CRITICAL


@dataclass(slots=True, frozen=True)
class AstroContext:
    """Everything the model is allowed to know for one request.

    It is **data, not instructions**: the prompt says so explicitly, and no
    field of it is ever treated as a command.
    """

    context_type: ContextType
    subject: dict
    time_reference: datetime
    locale: Locale
    factors: list[ContextFactor] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    context_version: str = ""
    source_fingerprint: str = ""
    trimmed_factor_ids: list[str] = field(default_factory=list)
    estimated_tokens: int = 0

    @property
    def factor_ids(self) -> set[str]:
        return {item.factor_id for item in self.factors}

    def factor(self, factor_id: str) -> ContextFactor | None:
        for item in self.factors:
            if item.factor_id == factor_id:
                return item
        return None


@dataclass(slots=True, frozen=True)
class GenerationMetadata:
    """What a call cost and how it was configured. No secrets, no prompts."""

    provider: str
    model_requested: str
    model_actual: str
    prompt_version: str
    context_version: str
    source_fingerprint: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    latency_ms: int = 0
    status: GenerationStatus = GenerationStatus.COMPLETED
    retry_count: int = 0
    provider_response_id: str | None = None
    fallback_reason: str | None = None
    use_case: UseCase = UseCase.CHAT
    error_code: str | None = None
