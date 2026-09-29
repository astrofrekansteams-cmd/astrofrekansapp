"""Model routing.

Model names are configuration, never literals scattered through services, so
a model can be swapped, overridden per use case, or rolled back from the
environment alone.

Fallback is allowed but never silent: when a tier cannot be served, the
generation records `model_requested`, `model_actual` and `fallback_reason`, so
a cheaper answer is always visible in the data rather than quietly shipped as
if it were the premium one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.domain.ai import ModelTier, UseCase

# Which tier each use case asks for. Reports are where quality is worth
# paying for; summaries and intent classification are not.
USE_CASE_TIERS: dict[UseCase, ModelTier] = {
    UseCase.CHAT: ModelTier.STANDARD,
    UseCase.INTERPRETATION: ModelTier.STANDARD,
    UseCase.REPORT: ModelTier.PREMIUM,
    UseCase.SUMMARY: ModelTier.LOW_COST,
    UseCase.TITLE: ModelTier.LOW_COST,
    UseCase.INTENT: ModelTier.LOW_COST,
}

# Where a tier drops to when its model is unavailable.
FALLBACK_CHAIN: dict[ModelTier, ModelTier | None] = {
    ModelTier.PREMIUM: ModelTier.STANDARD,
    ModelTier.STANDARD: ModelTier.LOW_COST,
    ModelTier.LOW_COST: None,
}


@dataclass(slots=True, frozen=True)
class ModelChoice:
    tier: ModelTier
    model: str
    requested_model: str
    fallback_reason: str | None = None

    @property
    def is_fallback(self) -> bool:
        return self.model != self.requested_model


class ModelRouter:
    def tier_for(self, use_case: UseCase) -> ModelTier:
        return USE_CASE_TIERS.get(use_case, ModelTier.STANDARD)

    def model_for_tier(self, tier: ModelTier) -> str:
        return {
            ModelTier.LOW_COST: settings.ai_model_low_cost,
            ModelTier.STANDARD: settings.ai_model_standard,
            ModelTier.PREMIUM: settings.ai_model_premium,
        }[tier]

    def override_for(self, use_case: UseCase) -> str | None:
        """Per-use-case override, e.g. AI_MODEL_REPORT."""
        return {
            UseCase.CHAT: settings.ai_model_chat,
            UseCase.INTERPRETATION: settings.ai_model_chat,
            UseCase.REPORT: settings.ai_model_report,
            UseCase.SUMMARY: settings.ai_model_summary,
            UseCase.TITLE: settings.ai_model_summary,
            UseCase.INTENT: settings.ai_model_summary,
        }.get(use_case)

    def choose(
        self, use_case: UseCase, *, tier: ModelTier | None = None
    ) -> ModelChoice:
        resolved_tier = tier or self.tier_for(use_case)
        override = self.override_for(use_case)
        model = override or self.model_for_tier(resolved_tier)
        return ModelChoice(tier=resolved_tier, model=model, requested_model=model)

    def fallback_allowed(self, use_case: UseCase) -> bool:
        """Whether this kind of call may be served by a cheaper model.

        Deliberately not one global switch. A chat answer from a cheaper model
        is still a useful answer, so falling back beats failing. A premium
        report is something the user waited for and may have paid for -
        producing it with a weaker model and presenting it as the premium
        reading is worse than saying the service is busy, so reports do not
        fall back unless an operator turns it on.
        """
        if not settings.ai_allow_model_fallback:
            return False
        return {
            UseCase.CHAT: settings.ai_allow_fallback_chat,
            UseCase.INTERPRETATION: settings.ai_allow_fallback_chat,
            UseCase.SUMMARY: settings.ai_allow_fallback_summary,
            UseCase.TITLE: settings.ai_allow_fallback_summary,
            UseCase.INTENT: settings.ai_allow_fallback_summary,
            UseCase.REPORT: settings.ai_allow_fallback_report,
        }.get(use_case, False)

    def fallback(
        self,
        choice: ModelChoice,
        reason: str,
        *,
        use_case: UseCase | None = None,
    ) -> ModelChoice | None:
        """The next cheapest option, or None when there is nothing left.

        The reason travels with the choice so the generation row can say why a
        premium request was served by a standard model. When ``use_case`` is
        given, the per-use-case policy decides whether a downgrade is allowed
        at all.
        """
        if use_case is not None:
            if not self.fallback_allowed(use_case):
                return None
        elif not settings.ai_allow_model_fallback:
            return None

        next_tier = FALLBACK_CHAIN.get(choice.tier)
        if next_tier is None:
            return None
        model = self.model_for_tier(next_tier)
        if model == choice.model:
            return None
        return ModelChoice(
            tier=next_tier,
            model=model,
            requested_model=choice.requested_model,
            fallback_reason=reason,
        )


_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
