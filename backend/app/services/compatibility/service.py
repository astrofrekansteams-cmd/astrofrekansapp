"""Compatibility use cases: synastry, composite and Davison.

Three things this service is careful about:

* **Authorisation.** A saved person is only ever resolved for the caller who
  owns it; guessing an id gets a 404, not someone else's birth data.
* **Snapshots.** A report stores the fingerprint of both people's birth data
  plus the engine and scoring versions. Editing a saved person later does not
  rewrite an existing report - a new calculation makes a new report.
* **Privacy.** Names, dates, times and places never reach the logs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.exceptions import MissingBirthData, NotFound, ValidationFailed
from app.core.logging import get_logger
from app.db.models.chart import ChartCache
from app.db.models.compatibility import CompatibilityReport
from app.db.models.user import User
from app.domain.astrology import BirthData, Chart
from app.domain.compatibility import CompatibilityKind
from app.domain.enums import ChartKind, HouseSystem
from app.schemas.compatibility import PersonRef
from app.services.astrology.composite import CompositeEngine, get_composite_engine
from app.services.astrology.serializers import chart_to_payload
from app.services.astrology.service import ChartService, chart_fingerprint
from app.services.astrology.synastry import SynastryEngine, get_synastry_engine
from app.services.astrology.synastry_weights import SYNASTRY_SCORING_VERSION
from app.services.astrology.skyfield_engine import ENGINE_VERSION
from app.services.users.service import UserService

logger = get_logger(__name__)

CACHE_TTL = 60 * 60 * 24 * 7


class ResolvedPerson:
    """A chart plus how we got to it, without carrying the birth data around."""

    __slots__ = ("chart", "ref", "label", "fingerprint", "subject_id", "subject_type")

    def __init__(
        self,
        chart: Chart,
        ref: str,
        label: str | None,
        fingerprint: str,
        subject_id: uuid.UUID | None,
        subject_type: str,
    ) -> None:
        self.chart = chart
        self.ref = ref
        self.label = label
        self.fingerprint = fingerprint
        self.subject_id = subject_id
        self.subject_type = subject_type


class CompatibilityService:
    def __init__(
        self,
        session: AsyncSession,
        charts: ChartService,
        synastry: SynastryEngine | None = None,
        composite: CompositeEngine | None = None,
    ) -> None:
        self.session = session
        self.charts = charts
        self._synastry = synastry or get_synastry_engine()
        self._composite = composite or get_composite_engine()

    # ------------------------------------------------------------ people

    async def resolve(
        self, user: User, ref: PersonRef, *, house_system: HouseSystem
    ) -> ResolvedPerson:
        users = UserService(self.session)

        if ref.me:
            birth = await users.get_primary_birth_data(user)
            profile = await users.birth_profiles.get_primary(user.id)
            label = user.profile.name if user.profile else None
            subject_id = profile.id if profile else None
            reference = "me"
            subject_type = "birth_profile"

        elif ref.saved_person_id is not None:
            # Scoped to the caller: another user's saved person is simply not
            # found, never read.
            person = await users.saved_people.get(user.id, ref.saved_person_id)
            if person is None:
                raise NotFound("Saved person not found.")
            from app.repositories.birth_profile_repository import to_birth_data

            birth = to_birth_data(person)
            label = person.name
            subject_id = person.id
            reference = f"saved_person:{person.id}"
            subject_type = "saved_person"

        else:
            latitude, longitude, timezone, place = await users.resolve_location(
                place=ref.birth_place,
                latitude=ref.latitude,
                longitude=ref.longitude,
                timezone=ref.timezone,
            )
            birth = BirthData(
                birth_date=ref.birth_date,
                birth_time=ref.birth_time,
                timezone=timezone,
                latitude=latitude,
                longitude=longitude,
                place=place,
                house_system=ref.house_system,
            )
            label = ref.label
            subject_id = None
            reference = "inline"
            subject_type = "ad_hoc"

        if birth.birth_date is None:
            raise MissingBirthData()

        chart = await self.charts.natal_chart(
            birth,
            session=self.session,
            user_id=user.id,
            subject_type=subject_type,
            subject_id=subject_id,
            house_system=house_system,
        )
        return ResolvedPerson(
            chart=chart,
            ref=reference,
            label=label,
            fingerprint=chart_fingerprint(chart.subject, ENGINE_VERSION),
            subject_id=subject_id,
            subject_type=subject_type,
        )

    # ------------------------------------------------------------ reports

    def _fingerprint(
        self, kind: CompatibilityKind, a: ResolvedPerson, b: ResolvedPerson
    ) -> str:
        """Everything the result depends on - and the version of how it was
        computed - so an old report is never confused with a new one."""
        payload = {
            "kind": kind.value,
            "a": a.fingerprint,
            "b": b.fingerprint,
            "engine": ENGINE_VERSION,
            "scoring": SYNASTRY_SCORING_VERSION,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    async def _cached(self, fingerprint: str) -> dict | None:
        return await get_cache().get(f"compat:{fingerprint}")

    async def _existing_report(
        self, user: User, fingerprint: str
    ) -> CompatibilityReport | None:
        """The caller's own stored report for these inputs, if any."""
        return await self.session.scalar(
            select(CompatibilityReport).where(
                CompatibilityReport.input_fingerprint == fingerprint,
                CompatibilityReport.user_id == user.id,
                CompatibilityReport.deleted_at.is_(None),
            )
        )

    async def _store(
        self,
        *,
        user: User,
        kind: CompatibilityKind,
        a: ResolvedPerson,
        b: ResolvedPerson,
        fingerprint: str,
        payload: dict,
        derived_chart: Chart | None = None,
    ) -> CompatibilityReport:
        await get_cache().set(f"compat:{fingerprint}", payload, CACHE_TTL)

        existing = await self.session.scalar(
            select(CompatibilityReport).where(
                CompatibilityReport.input_fingerprint == fingerprint,
                CompatibilityReport.user_id == user.id,
                CompatibilityReport.deleted_at.is_(None),
            )
        )
        if existing is not None:
            return existing

        derived_id = None
        if derived_chart is not None:
            derived_id = await self._store_derived_chart(user, derived_chart, kind)

        report = CompatibilityReport(
            user_id=user.id,
            kind=kind.value,
            person_a_ref=a.ref,
            person_b_ref=b.ref,
            person_a_label=a.label,
            person_b_label=b.label,
            chart_a_id=await self._chart_id(a),
            chart_b_id=await self._chart_id(b),
            derived_chart_id=derived_id,
            input_fingerprint=fingerprint,
            engine_version=ENGINE_VERSION,
            scoring_version=SYNASTRY_SCORING_VERSION,
            structured_result=payload,
        )
        self.session.add(report)
        await self.session.flush()
        # Ids only: never the names, dates or places.
        logger.info(
            "compatibility_report_created",
            report_id=str(report.id),
            kind=kind.value,
        )
        return report

    async def _chart_id(self, person: ResolvedPerson) -> uuid.UUID | None:
        row = await self.session.scalar(
            select(ChartCache).where(ChartCache.input_hash == person.fingerprint)
        )
        return row.id if row else None

    async def _store_derived_chart(
        self, user: User, chart: Chart, kind: CompatibilityKind
    ) -> uuid.UUID:
        fingerprint = chart_fingerprint(chart.subject, ENGINE_VERSION)
        row = await self.session.scalar(
            select(ChartCache).where(ChartCache.input_hash == fingerprint)
        )
        if row is None:
            row = ChartCache(
                user_id=user.id,
                chart_kind=(
                    ChartKind.COMPOSITE
                    if kind is CompatibilityKind.COMPOSITE
                    else ChartKind.DAVISON
                ),
                subject_type=kind.value,
                subject_id=None,
                moment_utc=chart.subject.moment_utc,
                input_hash=fingerprint,
                engine_version=ENGINE_VERSION,
                house_system=chart.house_system.value,
                payload=chart_to_payload(chart),
            )
            self.session.add(row)
            await self.session.flush()
        return row.id

    # ------------------------------------------------------------ queries

    async def list_reports(
        self, *, user_id: uuid.UUID, kind: CompatibilityKind | None = None, limit: int = 50
    ) -> list[CompatibilityReport]:
        statement = (
            select(CompatibilityReport)
            .where(
                CompatibilityReport.user_id == user_id,
                CompatibilityReport.deleted_at.is_(None),
            )
            .order_by(CompatibilityReport.created_at.desc())
            .limit(limit)
        )
        if kind is not None:
            statement = statement.where(CompatibilityReport.kind == kind.value)
        return list(await self.session.scalars(statement))

    async def get_report(
        self, *, user_id: uuid.UUID, report_id: uuid.UUID
    ) -> CompatibilityReport:
        report = await self.session.scalar(
            select(CompatibilityReport).where(
                CompatibilityReport.id == report_id,
                CompatibilityReport.user_id == user_id,
                CompatibilityReport.deleted_at.is_(None),
            )
        )
        if report is None:
            raise NotFound("Report not found.")
        return report
