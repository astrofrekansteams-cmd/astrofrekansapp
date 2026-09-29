from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.birth_profile import BirthProfile, SavedPerson
from app.domain.astrology import BirthData
from app.domain.enums import HouseSystem, SavedPersonRelation


def to_birth_data(profile: BirthProfile | SavedPerson) -> BirthData:
    """ORM row -> the engine's input type."""
    return BirthData(
        birth_date=profile.birth_date,
        birth_time=profile.birth_time if profile.birth_time_known else None,
        timezone=profile.timezone,
        latitude=profile.latitude,
        longitude=profile.longitude,
        place=profile.birth_place,
        house_system=HouseSystem(profile.house_system),
    )


class BirthProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[BirthProfile]:
        result = await self.session.scalars(
            select(BirthProfile)
            .where(
                BirthProfile.user_id == user_id, BirthProfile.deleted_at.is_(None)
            )
            .order_by(BirthProfile.is_primary.desc(), BirthProfile.created_at)
        )
        return list(result)

    async def get_primary(self, user_id: uuid.UUID) -> BirthProfile | None:
        return await self.session.scalar(
            select(BirthProfile).where(
                BirthProfile.user_id == user_id,
                BirthProfile.is_primary.is_(True),
                BirthProfile.deleted_at.is_(None),
            )
        )

    async def get(self, user_id: uuid.UUID, profile_id: uuid.UUID) -> BirthProfile | None:
        return await self.session.scalar(
            select(BirthProfile).where(
                BirthProfile.id == profile_id,
                BirthProfile.user_id == user_id,
                BirthProfile.deleted_at.is_(None),
            )
        )

    async def upsert_primary(
        self,
        *,
        user_id: uuid.UUID,
        birth_date: date,
        birth_time: time | None,
        birth_place: str | None,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
        label: str | None = None,
    ) -> BirthProfile:
        profile = await self.get_primary(user_id)
        if profile is None:
            profile = BirthProfile(user_id=user_id, is_primary=True)
            self.session.add(profile)

        profile.birth_date = birth_date
        profile.birth_time = birth_time
        profile.birth_time_known = birth_time is not None
        profile.birth_place = birth_place
        profile.latitude = latitude
        profile.longitude = longitude
        profile.timezone = timezone
        profile.house_system = house_system
        profile.label = label
        await self.session.flush()
        return profile

    async def clear_primary_flags(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(BirthProfile)
            .where(BirthProfile.user_id == user_id)
            .values(is_primary=False)
        )


class SavedPersonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[SavedPerson]:
        result = await self.session.scalars(
            select(SavedPerson)
            .where(SavedPerson.user_id == user_id, SavedPerson.deleted_at.is_(None))
            .order_by(SavedPerson.created_at)
        )
        return list(result)

    async def get(self, user_id: uuid.UUID, person_id: uuid.UUID) -> SavedPerson | None:
        return await self.session.scalar(
            select(SavedPerson).where(
                SavedPerson.id == person_id,
                SavedPerson.user_id == user_id,
                SavedPerson.deleted_at.is_(None),
            )
        )

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        relation: SavedPersonRelation,
        birth_date: date,
        birth_time: time | None,
        birth_place: str | None,
        latitude: float | None,
        longitude: float | None,
        timezone: str | None,
        house_system: HouseSystem = HouseSystem.PLACIDUS,
        note: str | None = None,
    ) -> SavedPerson:
        person = SavedPerson(
            user_id=user_id,
            name=name.strip(),
            relation=relation,
            birth_date=birth_date,
            birth_time=birth_time,
            birth_time_known=birth_time is not None,
            birth_place=birth_place,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            house_system=house_system,
            note=note,
        )
        self.session.add(person)
        await self.session.flush()
        return person

    async def soft_delete(self, person: SavedPerson) -> None:
        person.soft_delete()
        await self.session.flush()
