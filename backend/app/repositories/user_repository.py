from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subscription import Subscription
from app.db.models.user import User, UserProfile
from app.domain.enums import AuthProvider, SubscriptionTier


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(
                User.email == normalize_email(email), User.deleted_at.is_(None)
            )
        )

    async def email_exists(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def create(
        self,
        *,
        email: str,
        password_hash: str | None,
        name: str,
        language: str = "tr",
        timezone: str = "Europe/Istanbul",
        provider: AuthProvider = AuthProvider.PASSWORD,
        provider_subject: str | None = None,
    ) -> User:
        user = User(
            email=normalize_email(email),
            password_hash=password_hash,
            auth_provider=provider,
            provider_subject=provider_subject,
        )
        user.profile = UserProfile(name=name.strip(), language=language, timezone=timezone)
        user.subscription = Subscription(tier=SubscriptionTier.FREE)
        self.session.add(user)
        await self.session.flush()
        return user

    async def touch_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()

    async def soft_delete(self, user: User) -> None:
        user.soft_delete()
        user.is_active = False
        await self.session.flush()


def normalize_email(email: str) -> str:
    return email.strip().lower()
