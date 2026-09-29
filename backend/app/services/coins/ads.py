"""Rewarded-ad verification.

A reward is granted only when the ad network confirms it. Real networks
(AdMob, AppLovin, ...) do that with a server-side verification callback or a
signed token; each gets a verifier here. Until one is configured the reward
endpoint answers `ad_rewards_unavailable` - except the explicit "mock"
verifier, which exists for development and is refused in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import AppError


class AdRewardsUnavailable(AppError):
    status_code = 503
    code = "ad_rewards_unavailable"
    message = "Rewarded ads are not available right now."


class AdRewardRejected(AppError):
    status_code = 422
    code = "ad_reward_rejected"
    message = "This ad reward could not be verified."


@dataclass(slots=True, frozen=True)
class VerifiedReward:
    # The network's unique id for this rewarded view: the idempotency key.
    reward_id: str
    network: str


class AdRewardVerifier(Protocol):
    name: str

    async def verify(self, *, user_id: str, token: str) -> VerifiedReward: ...


class MockAdRewardVerifier:
    """Development only: trusts the client's token as the reward id."""

    name = "mock"

    async def verify(self, *, user_id: str, token: str) -> VerifiedReward:
        if len(token) < 8:
            raise AdRewardRejected()
        return VerifiedReward(reward_id=token, network=self.name)


def get_ad_verifier() -> AdRewardVerifier:
    choice = (settings.ad_reward_verifier or "").strip().lower()
    if choice == "mock" and not settings.is_production:
        return MockAdRewardVerifier()
    # No real network is integrated yet: fail closed.
    raise AdRewardsUnavailable()


def ad_rewards_enabled() -> bool:
    try:
        get_ad_verifier()
    except AdRewardsUnavailable:
        return False
    return True
