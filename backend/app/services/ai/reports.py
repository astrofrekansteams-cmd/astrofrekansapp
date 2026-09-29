"""AI report generation, snapshots and jobs.

A report is a snapshot. Its fingerprint covers the source material *and* the
versions that produced it - engine, context selection, prompt. Change any of
them and the next request produces a new report; the old one keeps saying what
the user already read. That is what makes a report safe to pay for, to share
with an expert, or to come back to a year later.

Long premium reports run through a durable job whose state lives in Postgres,
so a crash or a disconnect leaves an inspectable row rather than a silently
lost request.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.config import settings
from app.core.exceptions import AppError, NotFound
from app.core.logging import get_logger
from app.db.models.ai import AIReport, AIReportJob
from app.db.models.user import User
from app.domain.payments import EntitlementStatus
from app.domain.ai import (
    JobStatus,
    Locale,
    ModelTier,
    ReportStatus,
    ReportType,
    UseCase,
)
from app.services.ai import prompts, safety
from app.services.ai.generation import (
    GenerationService,
    acquire_generation_lock,
    release_generation_lock,
)
from app.services.ai.provider import (
    AIError,
    AIGenerationFailed,
    AIRateLimited,
    AITimeout,
)
from app.services.ai.report_access import (
    ReportAccess,
    ReportAccessDecision,
    ReportAccessPolicy,
    ReportConsumerRefRequired,
    ReportCreditConflict,
    ReportCreditUnavailable,
    ReportPaymentRequired,
    reservation_ref,
)
from app.services.ai.schemas import REPORT_SCHEMA, validate_report
from app.services.coins.service import CoinService
from app.services.notifications.outbox import OutboxService
from app.domain.chat import PushEvent
from app.services.ai.sources import ResolvedSource, SourceResolver
from app.services.payments.entitlements import (
    EntitlementService,
    NoCreditAvailable,
    advisory_xact_lock,
)

logger = get_logger(__name__)

# Source types whose id is part of the request (the others derive from the
# user's own birth profile).
_SOURCE_ID_TYPES = ("horary_question", "compatibility_report", "divination_reading")


@dataclass(slots=True)
class ReportOutcome:
    """What `ReportService.request` produced.

    `report` when there is one to return now; otherwise `job`. `run_inline`
    means this request holds the job's claim and should run it before
    answering (a synchronous paid report).
    """

    report: AIReport | None = None
    job: AIReportJob | None = None
    cached: bool = False
    run_inline: bool = False


def _coin_ref(consumer_ref: str) -> str:
    """The coin ledger reference of an AI job's spend."""
    return f"ai:{consumer_ref}"


def _ref_fingerprint(consumer_ref: str | None) -> str | None:
    if not consumer_ref:
        return None
    return hashlib.sha256(consumer_ref.encode("utf-8")).hexdigest()[:12]


def report_fingerprint(
    *,
    report_type: ReportType,
    source: ResolvedSource,
    locale: Locale,
    prompt_version: str,
) -> str:
    payload = {
        "report_type": report_type.value,
        "source_type": source.source_type,
        "source_id": str(source.source_id) if source.source_id else None,
        "source_fingerprint": source.context.source_fingerprint,
        "context_version": source.context.context_version,
        "engine_version": source.engine_version,
        "prompt_version": prompt_version,
        "locale": locale.value,
        "extra": source.extra_fingerprint or {},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ReportService:
    def __init__(
        self,
        session: AsyncSession,
        resolver: SourceResolver,
        generation: GenerationService,
    ) -> None:
        self.session = session
        self.resolver = resolver
        self.generation = generation

    # ---------------------------------------------------------- reading

    async def get(self, *, user: User, report_id: uuid.UUID) -> AIReport:
        report = await self.session.scalar(
            select(AIReport).where(
                AIReport.id == report_id,
                AIReport.user_id == user.id,
                AIReport.deleted_at.is_(None),
            )
        )
        if report is None:
            raise NotFound("Report not found.")
        return report

    async def list(
        self,
        *,
        user: User,
        report_type: ReportType | None = None,
        limit: int = 50,
    ) -> list[AIReport]:
        statement = (
            select(AIReport)
            .where(AIReport.user_id == user.id, AIReport.deleted_at.is_(None))
            .order_by(AIReport.created_at.desc())
            .limit(limit)
        )
        if report_type is not None:
            statement = statement.where(AIReport.report_type == report_type.value)
        return list(await self.session.scalars(statement))

    # -------------------------------------------------------- resolving

    async def resolve_source(
        self,
        user: User,
        *,
        report_type: ReportType,
        source_id: uuid.UUID | None,
        locale: Locale,
    ) -> ResolvedSource:
        """Authorise and assemble. Ownership is checked before anything else."""
        budget = settings.ai_report_context_budget

        if report_type is ReportType.NATAL:
            return await self.resolver.natal(user, locale=locale, budget=budget)
        if report_type is ReportType.TRANSIT:
            return await self.resolver.transits(
                user, locale=locale, budget=budget, range_key="month"
            )
        if report_type in (
            ReportType.DAILY,
            ReportType.WEEKLY,
            ReportType.MONTHLY,
            ReportType.YEARLY,
        ):
            return await self.resolver.forecast(
                user, report_type=report_type, locale=locale, budget=budget
            )
        if report_type.is_divination:
            if source_id is None:
                raise NotFound("A reading interpretation needs a reading id.")
            return await self.resolver.divination(
                user,
                reading_id=source_id,
                locale=locale,
                budget=budget,
                report_type=report_type,
            )
        if report_type is ReportType.HORARY:
            if source_id is None:
                raise NotFound("A horary report needs a question id.")
            return await self.resolver.horary(
                user, question_id=source_id, locale=locale, budget=budget
            )

        if source_id is None:
            raise NotFound("This report needs a compatibility report id.")
        return await self.resolver.compatibility(
            user,
            report_id=source_id,
            report_type=report_type,
            locale=locale,
            budget=budget,
        )

    # --------------------------------------------------------- requesting

    async def request(
        self,
        user: User,
        *,
        report_type: ReportType,
        source_id: uuid.UUID | None,
        locale: Locale,
        refresh: bool = False,
        background: bool = False,
        consumer_ref: str | None = None,
        pay_with_coins: bool = False,
    ) -> ReportOutcome:
        """The only way a report is asked for: sync, background, every route.

        Order matters. The source is authorised first (a source the caller
        does not own is a 404 whatever they paid), then the payment policy
        decides, then - for a paid report - the credit is reserved and the
        durable job created in the caller's transaction, before any generation
        starts.
        """
        prompt = prompts.prompt_for_report(report_type)
        source = await self.resolve_source(
            user, report_type=report_type, source_id=source_id, locale=locale
        )
        fingerprint = report_fingerprint(
            report_type=report_type,
            source=source,
            locale=locale,
            prompt_version=prompt.version,
        )
        decision = await ReportAccessPolicy(self.session).decide(
            user.id, report_type, user.tier
        )

        if decision.access is ReportAccess.COINS or (
            decision.access is ReportAccess.CREDIT_REQUIRED
            and pay_with_coins
            and decision.coin_item
        ):
            outcome = await self._coin_paid(
                user,
                decision.coin_item or "",
                report_type=report_type,
                source=source,
                locale=locale,
                fingerprint=fingerprint,
                refresh=refresh,
                background=background,
                consumer_ref=consumer_ref,
            )
        elif decision.access is ReportAccess.CREDIT_REQUIRED:
            outcome = await self._paid(
                user,
                decision,
                report_type=report_type,
                source=source,
                locale=locale,
                fingerprint=fingerprint,
                refresh=refresh,
                background=background,
                consumer_ref=consumer_ref,
            )
        elif background and not refresh and (
            cached_report := await self._cached(user, fingerprint)
        ) is not None:
            # Already written for exactly these inputs: answer with it rather
            # than queueing a job that would only find the same snapshot.
            outcome = ReportOutcome(report=cached_report, cached=True)
        elif background:
            job = self._new_job(
                user,
                report_type=report_type,
                source=source,
                locale=locale,
                fingerprint=fingerprint,
                basis=decision.access,
                refresh=refresh,
            )
            await self.session.flush()
            outcome = ReportOutcome(job=job)
        else:
            report, cached = await self._generate_for(
                user,
                report_type=report_type,
                source=source,
                locale=locale,
                fingerprint=fingerprint,
                refresh=refresh,
            )
            outcome = ReportOutcome(report=report, cached=cached)

        logger.info(
            "ai_report_access",
            user_id=str(user.id),
            report_type=report_type.value,
            outcome=decision.access.value,
            product_code=decision.product_code,
            consumer_ref_fingerprint=_ref_fingerprint(consumer_ref),
            job_id=str(outcome.job.id) if outcome.job else None,
            report_id=str(outcome.report.id) if outcome.report else None,
        )
        return outcome

    async def _paid(
        self,
        user: User,
        decision: ReportAccessDecision,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        fingerprint: str,
        refresh: bool,
        background: bool,
        consumer_ref: str | None,
    ) -> ReportOutcome:
        """Reserve a credit and create the job that will deliver against it.

        Both are written in the caller's transaction, so there is never a held
        credit without its job or a paid job without its credit. The credit is
        consumed only in the commit that completes the report (`run_job`).
        """
        if not consumer_ref:
            raise ReportConsumerRefRequired(
                details={"product_code": decision.product_code}
            )

        # Serialise requests carrying the same reference: the second one waits
        # and then finds the first one's job instead of racing it.
        await advisory_xact_lock(self.session, f"ai_report_job:{user.id}:{consumer_ref}")

        existing = await self.session.scalar(
            select(AIReportJob).where(
                AIReportJob.user_id == user.id,
                AIReportJob.consumer_ref == consumer_ref,
            )
        )
        if existing is not None:
            return await self._replay(
                existing,
                report_type=report_type,
                source=source,
                locale=locale,
                refresh=refresh,
                background=background,
            )

        if not refresh:
            # A snapshot this user has already paid for is theirs; asking for
            # it again does not charge again. An unpaid one (from before paid
            # reports were enforced) does not count.
            owned = await self._paid_snapshot(user, fingerprint)
            if owned is not None:
                return ReportOutcome(report=owned, cached=True)

        entitlements = EntitlementService(self.session)
        try:
            credit = await entitlements.reserve(
                user.id, decision.entitlement_code, reservation_ref(consumer_ref)
            )
        except NoCreditAvailable as exc:
            raise ReportPaymentRequired(
                details={
                    "product_code": decision.product_code,
                    "entitlement_code": decision.entitlement_code,
                }
            ) from exc
        except AppError as exc:
            if exc.code == "consumption_conflict":
                raise ReportCreditConflict() from exc
            raise
        if credit.status != EntitlementStatus.RESERVED.value:
            # The reference already paid for something that is not this job.
            raise ReportCreditConflict()

        job = self._new_job(
            user,
            report_type=report_type,
            source=source,
            locale=locale,
            fingerprint=fingerprint,
            basis=ReportAccess.CREDIT_REQUIRED,
            refresh=refresh,
        )
        job.consumer_ref = consumer_ref
        job.entitlement_id = credit.id
        run_inline = not background
        if run_inline:
            self._claim_inline(job)
        await self.session.flush()
        return ReportOutcome(job=job, run_inline=run_inline)

    async def _coin_paid(
        self,
        user: User,
        item: str,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        fingerprint: str,
        refresh: bool,
        background: bool,
        consumer_ref: str | None,
    ) -> ReportOutcome:
        """Charge coins and create the job that delivers against them.

        The spend and the job are written in the caller's transaction. A job
        that ends without a report refunds the spend (`_refund_coins`); the
        same reference never charges twice, and a reading the user already
        has is returned without a charge.
        """
        existing = None
        if consumer_ref:
            await advisory_xact_lock(
                self.session, f"ai_report_job:{user.id}:{consumer_ref}"
            )
            existing = await self.session.scalar(
                select(AIReportJob).where(
                    AIReportJob.user_id == user.id,
                    AIReportJob.consumer_ref == consumer_ref,
                )
            )
        if existing is not None:
            if (
                existing.report_type != report_type.value
                or existing.source_id != source.source_id
                or existing.locale != locale.value
                or existing.refresh != refresh
            ):
                raise ReportCreditConflict()
            if existing.status == JobStatus.COMPLETED.value and existing.report_id:
                report = await self.session.get(AIReport, existing.report_id)
                if report is not None and report.status == ReportStatus.COMPLETED.value:
                    return ReportOutcome(report=report, job=existing, cached=True)
            # Queued, running, or ended (then already refunded): the same job.
            return ReportOutcome(job=existing)

        if not refresh:
            owned = await self._cached(user, fingerprint)
            if owned is not None:
                return ReportOutcome(report=owned, cached=True)
            # A second press while the first is still generating joins it
            # instead of paying again.
            pending = await self.session.scalar(
                select(AIReportJob)
                .where(
                    AIReportJob.user_id == user.id,
                    AIReportJob.input_fingerprint == fingerprint,
                    AIReportJob.payment_basis == ReportAccess.COINS.value,
                    AIReportJob.status.in_(
                        (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
                    ),
                )
                .order_by(AIReportJob.created_at.desc())
                .limit(1)
            )
            if pending is not None:
                return ReportOutcome(job=pending)

        # Only a new charge needs a reference; owning the reading does not.
        if not consumer_ref:
            raise ReportConsumerRefRequired(details={"coin_item": item})
        await CoinService(self.session).spend(
            user.id,
            items=[item],
            consumer_ref=_coin_ref(consumer_ref),
            reference_id=report_type.value,
        )
        job = self._new_job(
            user,
            report_type=report_type,
            source=source,
            locale=locale,
            fingerprint=fingerprint,
            basis=ReportAccess.COINS,
            refresh=refresh,
        )
        job.consumer_ref = consumer_ref
        run_inline = not background
        if run_inline:
            self._claim_inline(job)
        await self.session.flush()
        return ReportOutcome(job=job, run_inline=run_inline)

    async def _refund_coins(self, job: AIReportJob) -> None:
        """Give back the coins of a job that will not deliver. Idempotent."""
        if job.payment_basis != ReportAccess.COINS.value or not job.consumer_ref:
            return
        ledger = CoinService(self.session)
        ref = _coin_ref(job.consumer_ref)
        if await ledger.already_spent(job.user_id, ref):
            await ledger.refund(job.user_id, consumer_ref=ref)
            logger.info("ai_job_coins_refunded", job_id=str(job.id))

    async def _replay(
        self,
        job: AIReportJob,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        refresh: bool,
        background: bool,
    ) -> ReportOutcome:
        """The same reference again: the same logical result, never a charge."""
        if (
            job.report_type != report_type.value
            or job.source_id != source.source_id
            or job.locale != locale.value
            or job.refresh != refresh
        ):
            raise ReportCreditConflict()

        if job.status == JobStatus.COMPLETED.value and job.report_id is not None:
            report = await self.session.get(AIReport, job.report_id)
            if report is not None and report.status == ReportStatus.COMPLETED.value:
                return ReportOutcome(report=report, job=job, cached=True)

        if job.status in (
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
            JobStatus.COMPLETED.value,
        ):
            # Paid for, not delivered: run it again on the same reservation.
            if job.entitlement_id is None or not await EntitlementService(
                self.session
            ).is_held(job.entitlement_id, reservation_ref(job.consumer_ref or "")):
                raise ReportCreditUnavailable(details={"job_id": str(job.id)})
            job.status = JobStatus.QUEUED.value
            job.attempt = 0
            job.error_code = None
            job.finished_at = None
            job.report_id = None
            await self.session.flush()

        if not background and job.status == JobStatus.QUEUED.value:
            # Take it from the queue only if no worker has: the conditional
            # update is the claim.
            claimed = await self.session.execute(
                update(AIReportJob)
                .where(
                    AIReportJob.id == job.id,
                    AIReportJob.status == JobStatus.QUEUED.value,
                )
                .values(**self._inline_claim_values(job.attempt))
                .execution_options(synchronize_session=False)
            )
            await self.session.refresh(job)
            return ReportOutcome(job=job, run_inline=claimed.rowcount == 1)

        # Queued for a worker, or running somewhere: the client polls the job.
        return ReportOutcome(job=job)

    async def _paid_snapshot(self, user: User, fingerprint: str) -> AIReport | None:
        return await self.session.scalar(
            select(AIReport)
            .where(
                AIReport.user_id == user.id,
                AIReport.input_fingerprint == fingerprint,
                AIReport.status == ReportStatus.COMPLETED.value,
                AIReport.entitlement_id.is_not(None),
                AIReport.deleted_at.is_(None),
            )
            .order_by(AIReport.created_at.desc())
            .limit(1)
        )

    def _new_job(
        self,
        user: User,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        fingerprint: str,
        basis: ReportAccess,
        refresh: bool,
    ) -> AIReportJob:
        job = AIReportJob(
            user_id=user.id,
            report_type=report_type.value,
            source_type=source.source_type,
            source_id=source.source_id,
            locale=locale.value,
            status=JobStatus.QUEUED.value,
            attempt=0,
            input_fingerprint=fingerprint,
            max_attempts=settings.ai_job_max_attempts,
            payment_basis=basis.value,
            refresh=refresh,
        )
        self.session.add(job)
        return job

    @staticmethod
    def _inline_claim_values(attempt: int) -> dict:
        now = datetime.now(UTC)
        return {
            "status": JobStatus.RUNNING.value,
            "worker_id": f"inline:{uuid.uuid4().hex[:12]}",
            "lease_expires_at": now + timedelta(seconds=settings.ai_job_lease_seconds),
            "attempt": attempt + 1,
            "started_at": now,
        }

    def _claim_inline(self, job: AIReportJob) -> None:
        """This request runs the job; the lease keeps workers off it.

        If the request dies mid-generation the lease expires and a worker
        finishes the job - the reserved credit is never stranded.
        """
        for key, value in self._inline_claim_values(job.attempt or 0).items():
            setattr(job, key, value)

    # -------------------------------------------------------- generating

    async def _generate(
        self,
        user: User,
        *,
        report_type: ReportType,
        source_id: uuid.UUID | None,
        locale: Locale,
        refresh: bool = False,
    ) -> tuple[AIReport, bool]:
        """Returns (report, cached). Ungated: its callers are `request` and `run_job`."""
        prompt = prompts.prompt_for_report(report_type)
        source = await self.resolve_source(
            user, report_type=report_type, source_id=source_id, locale=locale
        )
        fingerprint = report_fingerprint(
            report_type=report_type,
            source=source,
            locale=locale,
            prompt_version=prompt.version,
        )
        return await self._generate_for(
            user,
            report_type=report_type,
            source=source,
            locale=locale,
            fingerprint=fingerprint,
            refresh=refresh,
        )

    async def _generate_for(
        self,
        user: User,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        fingerprint: str,
        refresh: bool,
    ) -> tuple[AIReport, bool]:
        prompt = prompts.prompt_for_report(report_type)
        if not refresh:
            cached = await self._cached(user, fingerprint)
            if cached is not None:
                return cached, True

        lock_key = f"{user.id}:{fingerprint}"
        if not await acquire_generation_lock(lock_key):
            # The same expensive generation is already running for this user.
            existing = await self._cached(user, fingerprint)
            if existing is not None:
                return existing, True
            raise AIGenerationFailed(
                "This report is already being generated.",
                code="generation_in_progress",
            )

        try:
            report = await self._generate_now(
                user,
                report_type=report_type,
                source=source,
                locale=locale,
                fingerprint=fingerprint,
                prompt_version=prompt.version,
            )
        finally:
            await release_generation_lock(lock_key)

        return report, False

    async def _generate_now(
        self,
        user: User,
        *,
        report_type: ReportType,
        source: ResolvedSource,
        locale: Locale,
        fingerprint: str,
        prompt_version: str,
    ) -> AIReport:
        prompt = prompts.prompt_for_report(report_type)

        row = AIReport(
            user_id=user.id,
            report_type=report_type.value,
            source_type=source.source_type,
            source_id=source.source_id,
            locale=locale.value,
            status=ReportStatus.GENERATING.value,
            input_fingerprint=fingerprint,
            prompt_version=prompt.version,
            context_version=source.context.context_version,
            engine_version=source.engine_version,
            provider=self.generation.provider.name,
            model="",
        )
        self.session.add(row)
        await self.session.flush()

        try:
            report, metadata = await self.generation.run_structured(
                session=self.session,
                user_id=user.id,
                prompt=prompt,
                context=source.context,
                json_schema=REPORT_SCHEMA,
                schema_name="astrofrekans_report",
                validator=validate_report,
                use_case=UseCase.REPORT,
                tier=ModelTier.PREMIUM,
            )
        except AIError as exc:
            row.status = ReportStatus.FAILED.value
            row.error_code = getattr(exc, "code", "generation_failed")
            await self.session.flush()
            raise

        findings = safety.scan_output(
            " ".join(
                [report.summary] + [section.body for section in report.sections]
            )
        )
        if findings:
            # The prompt is the primary control; this is the backstop. A
            # generation that trips it is not shown as a finished report.
            logger.warning(
                "ai_safety_violation",
                report_type=report_type.value,
                findings=findings,
            )
            row.status = ReportStatus.FAILED.value
            row.error_code = "safety_violation"
            await self.session.flush()
            raise AIGenerationFailed(
                "The interpretation could not be produced safely.",
                code="generation_failed",
                details={"findings": findings},
            )

        row.status = ReportStatus.COMPLETED.value
        row.title = report.title[:200]
        row.summary = report.summary
        row.sections = {
            "sections": [section.model_dump() for section in report.sections]
        }
        row.warnings = {"warnings": source.context.warnings}
        row.interpretation_scope = report.interpretation_scope
        row.safety_note = report.safety_note
        row.model = metadata.model_actual
        await self.session.flush()

        await get_cache().set(
            f"ai:report:{fingerprint}",
            {"report_id": str(row.id)},
            settings.ai_report_cache_ttl_seconds,
        )
        return row

    async def _cached(self, user: User, fingerprint: str) -> AIReport | None:
        pointer = await get_cache().get(f"ai:report:{fingerprint}")
        if pointer:
            report = await self.session.scalar(
                select(AIReport).where(
                    AIReport.id == uuid.UUID(pointer["report_id"]),
                    AIReport.user_id == user.id,
                    AIReport.deleted_at.is_(None),
                )
            )
            if report is not None and report.status == ReportStatus.COMPLETED.value:
                return report

        # Several reports can share a fingerprint - an explicit refresh writes
        # a new one rather than overwriting what the user already read - so the
        # newest completed row is the current snapshot.
        report = await self.session.scalar(
            select(AIReport)
            .where(
                AIReport.input_fingerprint == fingerprint,
                AIReport.user_id == user.id,
                AIReport.status == ReportStatus.COMPLETED.value,
                AIReport.deleted_at.is_(None),
            )
            .order_by(AIReport.created_at.desc())
            .limit(1)
        )
        return report

    # -------------------------------------------------------------- jobs

    async def get_job(self, *, user: User, job_id: uuid.UUID) -> AIReportJob:
        job = await self.session.scalar(
            select(AIReportJob).where(
                AIReportJob.id == job_id, AIReportJob.user_id == user.id
            )
        )
        if job is None:
            raise NotFound("Job not found.")
        return job

    async def run_job(self, job: AIReportJob, user: User) -> AIReportJob:
        """Execute one claimed job.

        The worker claims a job (``queue.claim_next_job``) and then calls this.
        Calling it inline is also fine - the state machine is the same either
        way - but a job that is not in a runnable state is left exactly as it
        is. Re-running a completed job must not produce a second report, and
        a cancelled job must not run at all.
        """
        if job.status in (
            JobStatus.COMPLETED.value,
            JobStatus.CANCELLED.value,
            JobStatus.FAILED.value,
        ):
            logger.info(
                "ai_job_skipped", job_id=str(job.id), status=job.status
            )
            return job

        if job.status == JobStatus.QUEUED.value:
            # Inline execution without a claim: take the transition here so
            # the row still reflects reality while the work runs.
            job.status = JobStatus.RUNNING.value
            job.attempt += 1
            await self.session.flush()

        job.started_at = job.started_at or datetime.now(UTC)
        await self.session.flush()

        blocked = await self._payment_gate(job, user)
        if blocked is not None:
            # Not paid for: nothing is generated and nothing is delivered.
            return await self._fail_job(job, AIError("Report not paid for.", code=blocked))

        try:
            report, cached = await self._generate(
                user,
                report_type=ReportType(job.report_type),
                source_id=job.source_id if job.source_type in _SOURCE_ID_TYPES else None,
                locale=Locale(job.locale),
                refresh=job.refresh,
            )
        except AIError as exc:
            return await self._fail_job(job, exc)

        if job.payment_basis == ReportAccess.CREDIT_REQUIRED.value:
            if not await self._settle(job, report, cached=cached):
                return await self._fail_job(
                    job,
                    AIError(
                        "The credit is no longer held.",
                        code=ReportCreditUnavailable.code,
                    ),
                )

        in_background = not (job.worker_id or "").startswith("inline:")
        job.status = JobStatus.COMPLETED.value
        job.report_id = report.id
        job.error_code = None
        job.worker_id = None
        job.lease_expires_at = None
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        if in_background:
            # The person asked and left: tell them it is ready (respecting
            # their notification preferences at delivery).
            await OutboxService(self.session).enqueue(
                event=PushEvent.AI_REPORT_READY,
                user_id=job.user_id,
                dedupe_key=f"ai_report_ready:{job.id}",
                data={"report_id": str(report.id), "job_id": str(job.id)},
            )
        logger.info(
            "ai_job_completed",
            job_id=str(job.id),
            report_id=str(report.id),
            report_type=job.report_type,
            payment_basis=job.payment_basis,
            attempt=job.attempt,
        )
        return job

    async def _payment_gate(self, job: AIReportJob, user: User) -> str | None:
        """Why this job may not run, or None. Judged again at run time.

        A credit job needs its reservation still held (a refund revokes it).
        Any other job - free, premium, or queued before paid reports were
        enforced - is re-judged by the policy now: premium may have lapsed, or
        the type may have become paid.
        """
        if job.payment_basis == ReportAccess.CREDIT_REQUIRED.value:
            if job.entitlement_id is None or not await EntitlementService(
                self.session
            ).is_held(job.entitlement_id, reservation_ref(job.consumer_ref or "")):
                return ReportCreditUnavailable.code
            return None
        if job.payment_basis == ReportAccess.COINS.value:
            if not job.consumer_ref or not await CoinService(self.session).spend_active(
                job.user_id, _coin_ref(job.consumer_ref)
            ):
                return "coins_refunded"
            return None
        decision = await ReportAccessPolicy(self.session).decide(
            user.id, ReportType(job.report_type), user.tier
        )
        if decision.access is ReportAccess.CREDIT_REQUIRED:
            return ReportPaymentRequired.code
        if decision.access is ReportAccess.COINS:
            return "coins_required"
        return None

    async def _settle(self, job: AIReportJob, report: AIReport, *, cached: bool) -> bool:
        """Consume the job's credit in the commit that delivers the report.

        Returns False - and withholds a freshly generated report - when the
        reservation was revoked (a store refund) while the report was made.
        """
        entitlements = EntitlementService(self.session)
        ref = reservation_ref(job.consumer_ref or "")
        if (
            cached
            and report.entitlement_id is not None
            and report.entitlement_id != job.entitlement_id
            and await entitlements.release(job.entitlement_id, ref)
        ):
            # Already paid for with another of this user's credits (two
            # references raced for the same inputs): deliver it and give this
            # credit back rather than charge twice for one snapshot.
            job.entitlement_id = None
            await self.session.flush()
            return True
        credit = await entitlements.settle(job.entitlement_id, ref)
        if credit is None:
            if not cached:
                report.status = ReportStatus.FAILED.value
                report.error_code = ReportCreditUnavailable.code
                report.title = None
                report.summary = None
                report.sections = None
                report.warnings = None
                report.interpretation_scope = None
                report.safety_note = None
                await self.session.flush()
            return False
        if report.entitlement_id is None:
            report.entitlement_id = credit.id
        await self.session.flush()
        return True

    async def _fail_job(self, job: AIReportJob, error: AIError) -> AIReportJob:
        """Retry a transient failure, give up on a permanent one.

        A timeout or a rate limit is the provider having a bad minute and is
        worth another attempt. Output that failed schema validation, factor
        grounding or the safety scan will fail the same way next time - the
        inputs have not changed - so retrying it only spends money.
        """
        code = getattr(error, "code", "generation_failed")
        transient = isinstance(error, (AIRateLimited, AITimeout)) or code in (
            "ai_provider_unavailable",
            "generation_in_progress",
        )
        job.error_code = code
        job.worker_id = None
        job.lease_expires_at = None

        if transient and job.attempt < job.max_attempts:
            job.status = JobStatus.QUEUED.value
            await self.session.flush()
            logger.warning(
                "ai_job_retry",
                job_id=str(job.id),
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                error_code=code,
            )
            return job

        job.status = JobStatus.FAILED.value
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        await self._refund_coins(job)
        logger.warning(
            "ai_job_failed",
            job_id=str(job.id),
            attempt=job.attempt,
            error_code=code,
            retryable=transient,
        )
        return job

    async def cancel_job(self, *, user: User, job_id: uuid.UUID) -> AIReportJob:
        job = await self.get_job(user=user, job_id=job_id)
        if job.status in (JobStatus.QUEUED.value, JobStatus.RUNNING.value):
            job.status = JobStatus.CANCELLED.value
            job.finished_at = datetime.now(UTC)
            await self.session.flush()
            await self._refund_coins(job)
        return job
