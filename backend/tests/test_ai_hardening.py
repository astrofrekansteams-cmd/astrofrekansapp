"""B6.1: memory, jobs, the worker, quotas, fallback policy and cancellation.

These are the things B6 built but did not prove. Everything here runs against
`FakeAIProvider` - no key, no cost, no network - because what is being tested
is our own state machine: who may claim a job, what happens when a worker
dies, what a dropped stream leaves behind, and which calls are allowed to be
served by a cheaper model.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.rate_limit import Quota
from app.db.models.ai import AIConversation, AIMessage, AIReport, AIReportJob
from app.db.models.user import User
from app.domain.ai import (
    CompletionStatus,
    JobStatus,
    Locale,
    MessageRole,
    ModelTier,
    ReportStatus,
    UseCase,
)
from app.services.ai import factory, safety
from app.services.ai.conversations import ConversationService
from app.services.ai.fake_provider import FakeAIProvider
from app.services.ai.provider import AIRateLimited, AITimeout
from app.services.ai.queue import (
    claim_next_job,
    queue_depth,
    recover_stale_jobs,
    release_claim,
)
from app.services.ai.router import ModelRouter
from app.workers.ai_report_worker import AIReportWorker

API = "/api/v1"


@pytest.fixture(autouse=True)
def unpriced_reports(monkeypatch):
    """These tests are about generation, caching and jobs - not payment.

    Paid report enforcement (natal, synastry and yearly need a credit) is
    covered in `test_report_payments.py`. Here the price list is emptied so
    every report type takes the FREE path, which is exactly the B6 behaviour
    these tests describe.
    """
    from app.services.ai import report_access

    monkeypatch.setattr(report_access, "PAID_REPORT_PRODUCTS", {})


@pytest.fixture
def ai(monkeypatch) -> FakeAIProvider:
    monkeypatch.setattr(settings, "ai_provider", "fake")
    provider = FakeAIProvider()
    factory.set_ai_provider(provider)
    yield provider
    factory.set_ai_provider(None)


@pytest.fixture
async def user_row(client: httpx.AsyncClient, registered, session_factory) -> User:
    """The registered user as a row, for service-level tests."""
    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email == registered["email"])
        )
        assert user is not None
        return user


async def enqueue_job(
    client: httpx.AsyncClient, registered, report_type: str = "natal"
) -> uuid.UUID:
    response = await client.post(
        f"{API}/ai/report-jobs",
        headers=registered["headers"],
        json={"report_type": report_type},
    )
    assert response.status_code == 202, response.text
    return uuid.UUID(response.json()["id"])


async def load_job(session_factory, job_id: uuid.UUID) -> AIReportJob:
    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        assert job is not None
        return job


# =====================================================  conversation memory


async def test_summary_triggers_once_and_is_persisted(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """Twelve unsummarised messages produce exactly one cheap summary call."""
    conversation_id: str | None = None
    for index in range(6):  # six turns = twelve messages
        payload = {"message": f"Bugün {index} ne olacak?"}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await client.post(
            f"{API}/ai/chat", headers=registered["headers"], json=payload
        )
        assert response.status_code == 200, response.text
        conversation_id = response.json()["conversation_id"]

    summary_calls = [call for call in ai.calls if call.use_case is UseCase.SUMMARY]
    assert len(summary_calls) == 1, "the summary is built once, not per turn"

    call = summary_calls[0]
    assert call.tier is ModelTier.LOW_COST, "memory does not need the good model"
    assert "conversation_summary_v1" == call.metadata["prompt_version"]
    assert "Do NOT record astrological facts" in call.instructions

    async with session_factory() as session:
        conversation = await session.scalar(
            select(AIConversation).where(
                AIConversation.id == uuid.UUID(conversation_id)
            )
        )
        assert conversation.summary, "the summary reached the database"
        assert conversation.summary_version == 1
        # The boundary moves, so the next twelve messages trigger the next
        # summary rather than re-summarising the same ones.
        assert conversation.summarised_message_count == conversation.message_count
        assert conversation.message_count == 12


async def test_summary_is_reused_not_recomputed(
    client: httpx.AsyncClient, registered, ai
):
    conversation_id: str | None = None
    for index in range(7):
        payload = {"message": f"Soru {index}"}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await client.post(
            f"{API}/ai/chat", headers=registered["headers"], json=payload
        )
        conversation_id = response.json()["conversation_id"]

    assert (
        len([c for c in ai.calls if c.use_case is UseCase.SUMMARY]) == 1
    ), "a second summary is only built after another twelve messages"

    # The last chat turn carried the summary as memory.
    last_chat = [c for c in ai.calls if c.use_case is UseCase.CHAT][-1]
    contents = [item["content"] for item in last_chat.input]
    assert any("<conversation_summary>" in item for item in contents)


async def test_history_sent_to_the_model_is_bounded(
    client: httpx.AsyncClient, registered, ai, monkeypatch
):
    """Memory is a window plus a summary, never the whole transcript."""
    monkeypatch.setattr(settings, "ai_recent_message_window", 4)

    conversation_id: str | None = None
    for index in range(8):
        payload = {"message": f"Mesaj {index}"}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await client.post(
            f"{API}/ai/chat", headers=registered["headers"], json=payload
        )
        conversation_id = response.json()["conversation_id"]

    last_chat = [c for c in ai.calls if c.use_case is UseCase.CHAT][-1]
    # context + (summary) + <= window history + user message
    assert len(last_chat.input) <= 4 + 2 + 1
    assert "Mesaj 0" not in str(last_chat.input), "old turns are not replayed"


async def test_summary_failure_is_not_a_user_facing_error(
    client: httpx.AsyncClient, registered, ai, session_factory, db_session
):
    """A stale summary is a small loss of memory, not a broken conversation."""
    service = ConversationService(db_session)
    conversation = await service.create(
        user_id=(
            await db_session.scalar(
                select(User).where(User.email == registered["email"])
            )
        ).id,
        locale=Locale.TR,
    )
    for index in range(4):
        await service.add_message(
            conversation, role=MessageRole.USER, content=f"m{index}"
        )
    await db_session.commit()

    ai.rate_limit_next()
    result = await service.refresh_summary(
        conversation,
        generation=factory.build_generation_service(),
        user_id=conversation.user_id,
    )
    assert result is None
    assert conversation.summary is None
    assert conversation.summary_version == 0


# ===========================================================  report jobs


async def test_run_job_completes(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        assert job.status == JobStatus.QUEUED.value

        service = factory.build_report_service(session)
        job = await service.run_job(job, user)
        await session.commit()

    assert job.status == JobStatus.COMPLETED.value
    assert job.report_id is not None
    assert job.attempt == 1
    assert job.started_at is not None and job.finished_at is not None
    assert job.error_code is None

    report = await client.get(
        f"{API}/ai/reports/{job.report_id}", headers=registered["headers"]
    )
    assert report.status_code == 200
    assert report.json()["status"] == "completed"


async def test_permanent_failure_is_not_retried(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    """Bad output will be bad again: the inputs have not changed."""
    job_id = await enqueue_job(client, registered)
    ai.hallucinate_factor = "natal:aspect:invented"

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        job = await factory.build_report_service(session).run_job(job, user)
        await session.commit()

    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "generation_failed"
    assert job.finished_at is not None


async def test_transient_failure_goes_back_to_the_queue(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        ai.raise_next(AITimeout())
        job = await factory.build_report_service(session).run_job(job, user)
        await session.commit()

    assert job.status == JobStatus.QUEUED.value, "a timeout deserves another go"
    assert job.error_code == "ai_timeout"
    assert job.attempt == 1
    assert job.finished_at is None
    assert job.worker_id is None


async def test_retries_stop_at_max_attempts(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        job.attempt = job.max_attempts - 1
        ai.raise_next(AIRateLimited())
        job = await factory.build_report_service(session).run_job(job, user)
        await session.commit()

    assert job.status == JobStatus.FAILED.value
    assert job.attempt == job.max_attempts
    assert job.error_code == "ai_rate_limited"


async def test_cancelled_job_is_never_run(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    job_id = await enqueue_job(client, registered)
    cancelled = await client.post(
        f"{API}/ai/report-jobs/{job_id}/cancel", headers=registered["headers"]
    )
    assert cancelled.json()["status"] == "cancelled"

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        job = await factory.build_report_service(session).run_job(job, user)
        await session.commit()

    assert job.status == JobStatus.CANCELLED.value
    assert job.report_id is None
    assert not ai.calls, "a cancelled job costs nothing"


async def test_completed_job_rerun_produces_no_second_report(
    client: httpx.AsyncClient, registered, ai, session_factory, user_row
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        service = factory.build_report_service(session)
        job = await service.run_job(job, user)
        await session.commit()
        first_report_id = job.report_id

    calls_after_first = len(ai.calls)

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        user = await session.get(User, user_row.id)
        job = await factory.build_report_service(session).run_job(job, user)
        await session.commit()

    assert job.report_id == first_report_id
    assert len(ai.calls) == calls_after_first, "no second generation"

    async with session_factory() as session:
        reports = list(
            await session.scalars(
                select(AIReport).where(
                    AIReport.status == ReportStatus.COMPLETED.value
                )
            )
        )
    assert len(reports) == 1


async def test_unauthorized_source_never_becomes_a_job(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """Authorisation happens before the job row exists, not when it runs."""
    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "intruder@example.com",
            "password": "An0therStrongPass!",
            "name": "Intruder",
            "birth_date": "1988-11-02",
            "birth_time": "06:15:00",
            "birth_place": "Ankara",
        },
    )
    intruder = {"Authorization": f"Bearer {other.json()['access_token']}"}

    question = await client.post(
        f"{API}/horary/questions",
        headers=registered["headers"],
        json={
            "question": "Will it arrive?",
            "category": "general",
            "latitude": 41.0082,
            "longitude": 28.9784,
            "location_name": "Istanbul",
        },
    )
    question_id = question.json()["id"]

    response = await client.post(
        f"{API}/ai/report-jobs",
        headers=intruder,
        json={"report_type": "horary", "source_id": question_id},
    )
    assert response.status_code == 404

    async with session_factory() as session:
        jobs = list(await session.scalars(select(AIReportJob)))
    assert jobs == [], "no row was written for an unauthorised request"


# ===============================================================  worker


async def test_worker_claims_and_completes(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    job_id = await enqueue_job(client, registered)
    worker = AIReportWorker(worker_id="worker-a")

    async with session_factory() as session:
        job = await claim_next_job(session, worker_id=worker.worker_id)
        assert job is not None and job.id == job_id
        assert job.status == JobStatus.RUNNING.value
        assert job.worker_id == "worker-a"
        assert job.lease_expires_at is not None
        assert job.attempt == 1

        await worker.process(session, job)

    finished = await load_job(session_factory, job_id)
    assert finished.status == JobStatus.COMPLETED.value
    assert finished.report_id is not None
    assert finished.worker_id is None, "a finished job holds no claim"
    assert finished.lease_expires_at is None
    assert worker.processed == 1


async def test_a_claimed_job_is_invisible_to_the_next_worker(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """Two workers, one job: the second finds nothing to do."""
    await enqueue_job(client, registered)

    async with session_factory() as session:
        first = await claim_next_job(session, worker_id="worker-a")
    async with session_factory() as session:
        second = await claim_next_job(session, worker_id="worker-b")

    assert first is not None
    assert second is None, "the same job is never handed out twice"


async def test_two_workers_split_two_jobs(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    first_id = await enqueue_job(client, registered, "natal")
    second_id = await enqueue_job(client, registered, "daily")

    async with session_factory() as session:
        first = await claim_next_job(session, worker_id="worker-a")
    async with session_factory() as session:
        second = await claim_next_job(session, worker_id="worker-b")

    assert {first.id, second.id} == {first_id, second_id}
    assert first.worker_id != second.worker_id
    # Oldest first: a queue that reorders itself is a queue that starves
    # somebody.
    assert first.id == first_id


async def test_stale_running_job_is_recovered(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """A worker that died leaves a lease that expires. Nothing else can."""
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await claim_next_job(session, worker_id="doomed-worker")
        job.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with session_factory() as session:
        recovered = await recover_stale_jobs(session)
    assert recovered == 1

    job = await load_job(session_factory, job_id)
    assert job.status == JobStatus.QUEUED.value
    assert job.worker_id is None
    assert job.lease_expires_at is None

    async with session_factory() as session:
        reclaimed = await claim_next_job(session, worker_id="worker-b")
    assert reclaimed is not None and reclaimed.attempt == 2


async def test_a_live_lease_is_left_alone(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """Recovery must not steal a job from a worker that is still working."""
    await enqueue_job(client, registered)

    async with session_factory() as session:
        await claim_next_job(session, worker_id="busy-worker")

    async with session_factory() as session:
        assert await recover_stale_jobs(session) == 0
        assert await claim_next_job(session, worker_id="worker-b") is None


async def test_stale_job_out_of_attempts_fails(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    """A job that keeps killing its worker stops being handed out."""
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await claim_next_job(session, worker_id="doomed")
        job.attempt = job.max_attempts
        job.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with session_factory() as session:
        await recover_stale_jobs(session)

    job = await load_job(session_factory, job_id)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "worker_lost"


async def test_graceful_shutdown_requeues_the_job_in_hand(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        await claim_next_job(session, worker_id="worker-a")

    async with session_factory() as session:
        await release_claim(session, job_id, requeue=True)

    job = await load_job(session_factory, job_id)
    assert job.status == JobStatus.QUEUED.value
    assert job.worker_id is None


async def test_worker_leaves_jobs_alone_without_a_key(
    client: httpx.AsyncClient, registered, ai, session_factory, monkeypatch
):
    """No key must not mean a pile of permanently failed reports."""
    await enqueue_job(client, registered)

    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    factory.set_ai_provider(None)

    worker = AIReportWorker(worker_id="unconfigured")
    worker.request_stop()  # one pass, then stop
    await worker.run_forever()

    async with session_factory() as session:
        depth = await queue_depth(session)
    assert depth["queued"] == 1, "the work is still there for a configured worker"


async def test_worker_survives_a_job_whose_user_vanished(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    job_id = await enqueue_job(client, registered)

    async with session_factory() as session:
        job = await claim_next_job(session, worker_id="worker-a")
        job.user_id = uuid.uuid4()  # the account went away
        await session.commit()

    async with session_factory() as session:
        job = await session.scalar(
            select(AIReportJob).where(AIReportJob.id == job_id)
        )
        await AIReportWorker(worker_id="worker-a").process(session, job)

    job = await load_job(session_factory, job_id)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "user_missing"


# ==========================================================  rate limits


@pytest.fixture
def tight_limits(monkeypatch):
    """Small, test-only quotas. Never the production numbers."""
    from app.api.v1 import ai as ai_routes

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        ai_routes._chat_limit.dependency, "quota", Quota(limit=2, window_seconds=60)
    )
    monkeypatch.setattr(
        ai_routes._stream_limit.dependency, "quota", Quota(limit=2, window_seconds=60)
    )
    monkeypatch.setattr(
        ai_routes._report_limit.dependency, "quota", Quota(limit=1, window_seconds=60)
    )
    return True


async def test_chat_quota_is_enforced(
    client: httpx.AsyncClient, registered, ai, tight_limits
):
    for _ in range(2):
        allowed = await client.post(
            f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
        )
        assert allowed.status_code == 200

    blocked = await client.post(
        f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
    )
    assert blocked.status_code == 429
    body = blocked.json()["error"]
    assert body["code"] == "ai_rate_limited"
    assert body["details"]["limit"] == 2
    assert body["details"]["scope"] == "ai_chat"

    retry_after = blocked.headers.get("retry-after")
    assert retry_after is not None, "a 429 must say how long to wait"
    assert 0 < int(retry_after) <= 60


async def test_report_quota_is_enforced_and_separate(
    client: httpx.AsyncClient, registered, ai, tight_limits
):
    first = await client.post(
        f"{API}/ai/reports",
        headers=registered["headers"],
        json={"report_type": "natal"},
    )
    assert first.status_code == 200

    blocked = await client.post(
        f"{API}/ai/reports",
        headers=registered["headers"],
        json={"report_type": "daily"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["scope"] == "ai_report"

    # A separate scope: the report quota does not consume the chat quota.
    chat = await client.post(
        f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
    )
    assert chat.status_code == 200


async def test_stream_quota_is_enforced(
    client: httpx.AsyncClient, registered, ai, tight_limits
):
    for _ in range(2):
        async with client.stream(
            "POST",
            f"{API}/ai/chat/stream",
            headers=registered["headers"],
            json={"message": "Merhaba"},
        ) as response:
            assert response.status_code == 200
            await response.aread()

    async with client.stream(
        "POST",
        f"{API}/ai/chat/stream",
        headers=registered["headers"],
        json={"message": "Merhaba"},
    ) as blocked:
        assert blocked.status_code == 429
        await blocked.aread()
    assert blocked.json()["error"]["code"] == "ai_rate_limited"


async def test_quotas_are_per_user(
    client: httpx.AsyncClient, registered, ai, tight_limits
):
    other = await client.post(
        f"{API}/auth/register",
        json={
            "email": "second@example.com",
            "password": "An0therStrongPass!",
            "name": "Second",
            "birth_date": "1990-03-03",
            "birth_time": "10:00:00",
            "birth_place": "Izmir",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    for _ in range(3):
        await client.post(
            f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
        )

    # One user exhausting a quota must not lock everyone else out.
    fresh = await client.post(
        f"{API}/ai/chat", headers=headers, json={"message": "Merhaba"}
    )
    assert fresh.status_code == 200


# ======================================================  fallback policy


def test_premium_reports_do_not_fall_back_by_default():
    """A downgraded report should fail loudly, not arrive quietly."""
    router = ModelRouter()
    assert router.fallback_allowed(UseCase.REPORT) is False

    premium = router.choose(UseCase.REPORT)
    assert router.fallback(premium, reason="AITimeout", use_case=UseCase.REPORT) is None


def test_chat_and_summary_still_fall_back():
    """A cheaper answer beats no answer when the user is waiting in a chat."""
    router = ModelRouter()
    assert router.fallback_allowed(UseCase.CHAT) is True
    assert router.fallback_allowed(UseCase.SUMMARY) is True

    choice = router.choose(UseCase.CHAT)
    fallback = router.fallback(choice, reason="AITimeout", use_case=UseCase.CHAT)
    assert fallback is not None
    assert fallback.tier is ModelTier.LOW_COST
    assert fallback.requested_model == choice.requested_model
    assert fallback.fallback_reason == "AITimeout"


def test_report_fallback_can_be_enabled_deliberately(monkeypatch):
    monkeypatch.setattr(settings, "ai_allow_fallback_report", True)
    router = ModelRouter()
    assert router.fallback_allowed(UseCase.REPORT) is True
    assert (
        router.fallback(
            router.choose(UseCase.REPORT), reason="x", use_case=UseCase.REPORT
        )
        is not None
    )


def test_master_switch_disables_every_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_allow_model_fallback", False)
    monkeypatch.setattr(settings, "ai_allow_fallback_chat", True)
    router = ModelRouter()
    assert router.fallback_allowed(UseCase.CHAT) is False


async def test_status_exposes_models_and_policy_without_secrets(
    client: httpx.AsyncClient, registered, ai
):
    response = await client.get(f"{API}/ai/status", headers=registered["headers"])
    body = response.json()

    assert body["models"]["low_cost"] == settings.ai_model_low_cost
    assert body["models"]["standard"] == settings.ai_model_standard
    assert body["models"]["premium"] == settings.ai_model_premium
    assert body["fallback"]["report"] is False
    assert body["fallback"]["chat"] is True

    text = response.text.lower()
    assert "api_key" not in text and "sk-" not in text and "secret" not in text


async def test_status_says_why_ai_is_off(
    client: httpx.AsyncClient, registered, monkeypatch
):
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    factory.set_ai_provider(None)
    try:
        response = await client.get(f"{API}/ai/status", headers=registered["headers"])
        body = response.json()
        assert body["configured"] is False
        assert body["diagnostic"] == "OPENAI_API_KEY is not set on this server."
        # The models it *would* use are still visible, so an operator can check
        # the configuration without a key in place.
        assert body["models"]["premium"]
    finally:
        factory.set_ai_provider(None)


# ==================================================  stream cancellation


async def test_completed_stream_is_marked_completed(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    async with client.stream(
        "POST",
        f"{API}/ai/chat/stream",
        headers=registered["headers"],
        json={"message": "Bu hafta?"},
    ) as response:
        await response.aread()

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(AIMessage).where(
                    AIMessage.role == MessageRole.ASSISTANT.value
                )
            )
        )
    assert len(rows) == 1
    assert rows[0].completion_status == CompletionStatus.COMPLETED.value


async def test_interrupted_stream_is_not_stored_as_a_finished_answer(
    client: httpx.AsyncClient, registered, ai, session_factory, db_session
):
    """A dropped connection leaves text, but not a completed turn."""
    from app.services.ai.chat import ChatService

    user = await db_session.scalar(
        select(User).where(User.email == registered["email"])
    )
    conversations = ConversationService(db_session)
    conversation = await conversations.create(user_id=user.id, locale=Locale.TR)
    await db_session.commit()

    service = ChatService(
        session=db_session,
        conversations=conversations,
        resolver=factory.build_source_resolver(db_session),
        generation=factory.build_generation_service(),
    )

    stream = service.stream(
        user, conversation, message="Bugün nasıl?", locale=Locale.TR
    )
    # Take a couple of events, then walk away like a client that closed the tab.
    async for chunk in stream:
        if chunk.type == "text_delta":
            break
    await stream.aclose()
    await db_session.commit()

    rows = await conversations.messages(conversation_id=conversation.id)
    assistant = [row for row in rows if row.role == MessageRole.ASSISTANT.value]
    assert len(assistant) == 1
    assert assistant[0].completion_status == CompletionStatus.CANCELLED.value
    assert assistant[0].content, "what the user saw is still recorded"


async def test_partial_turns_are_labelled_when_replayed(
    client: httpx.AsyncClient, registered, ai, db_session
):
    """The model is told the turn was unfinished rather than shown a lie."""
    user = await db_session.scalar(
        select(User).where(User.email == registered["email"])
    )
    conversations = ConversationService(db_session)
    conversation = await conversations.create(user_id=user.id, locale=Locale.TR)
    await conversations.add_message(
        conversation, role=MessageRole.USER, content="Bir soru"
    )
    await conversations.add_message(
        conversation,
        role=MessageRole.ASSISTANT,
        content="Yarım kalan cevap",
        completion_status=CompletionStatus.CANCELLED,
    )
    await db_session.commit()

    history = await conversations.recent_history(conversation)
    assistant_turn = history[-1]["content"]
    assert "Yarım kalan cevap" in assistant_turn
    assert "unfinished answer" in assistant_turn
    assert "cancelled" in assistant_turn


async def test_api_reports_completion_status(
    client: httpx.AsyncClient, registered, ai
):
    response = await client.post(
        f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
    )
    messages = await client.get(
        f"{API}/ai/conversations/{response.json()['conversation_id']}/messages",
        headers=registered["headers"],
    )
    assert all(
        row["completion_status"] == "completed" for row in messages.json()
    )


# =====================================================  safety regression


@pytest.mark.parametrize(
    ("text", "finding"),
    [
        # Turkish
        ("Kesin evleneceksiniz.", "certain_future_claim"),
        ("O sizi kesin aldatıyor.", "third_party_claim"),
        ("Uğur şansınız %82.", "certain_future_claim"),
        ("İlişkinizin başarı şansı %72.", "certain_future_claim"),
        ("Davayı kazanacaksınız.", "legal_outcome_claim"),
        ("İlacınızı bırakın.", "medical_directive"),
        ("Bu hisseyi alın.", "financial_directive"),
        ("Telefonunu kontrol edin.", "relationship_surveillance"),
        # Azerbaijani
        ("Bu hissəni alın.", "financial_directive"),
        ("Dərmanı dayandırın.", "medical_directive"),
        ("Məhkəməni qazanacaqsınız.", "legal_outcome_claim"),
        # English
        ("You will definitely get the job.", "certain_future_claim"),
        ("There is a 90% chance of success.", "certain_future_claim"),
        ("He is cheating on you.", "third_party_claim"),
        ("You will win the case.", "legal_outcome_claim"),
        ("Buy this stock now.", "financial_directive"),
        ("Stop taking your medication.", "medical_directive"),
    ],
)
def test_scanner_catches_the_claims_the_product_must_not_make(
    text: str, finding: str
):
    assert finding in safety.scan_output(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Bu dönem para konuşmalarını öne çıkarıyor; bütçenizi gözden geçirmek "
        "isteyebilirsiniz.",
        "Bu hafta ilişkinizde iletişim teması öne çıkıyor.",
        "Bu period dincəlmək üçün əlverişlidir.",
        "This period emphasises rest, and many people use it to review a budget.",
        "Saturn is crossing your seventh house between 3 and 19 March.",
    ],
)
def test_scanner_leaves_ordinary_language_alone(text: str):
    assert safety.scan_output(text) == [], text


async def test_unsafe_chat_answer_is_not_delivered(
    client: httpx.AsyncClient, registered, ai, session_factory
):
    # Chat is a structured call, so the unsafe text has to arrive in the
    # structured payload - not as free text the chat path never reads.
    ai.custom_payload = {
        "answer": "O sizi kesin aldatıyor ve davayı kazanacaksınız.",
        "source_factor_ids": [],
        "context_note": None,
    }

    response = await client.post(
        f"{API}/ai/chat", headers=registered["headers"], json={"message": "Merhaba"}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "generation_failed"


async def test_safety_is_layered_not_only_a_scanner(ai):
    """The scanner is the last line, not the only one."""
    from app.services.ai import prompts

    instructions = prompts.SYNASTRY_REPORT.instructions(Locale.TR).lower()
    # 1. The prompt forbids it.
    assert "never convert it into a chance" in instructions
    assert "never diagnose" in instructions
    # 2. The structure carries it as data.
    from app.services.ai.context.builder import AstroAIContextBuilder

    context = AstroAIContextBuilder().synastry(
        {
            "overall_score": 70,
            "score_semantics": "factor index, not a probability",
            "themes": [],
            "aspects": [],
            "overlays_a_in_b": [],
            "overlays_b_in_a": [],
            "warnings": [],
        },
        locale=Locale.TR,
        subject={},
        token_budget=4000,
    )
    assert any("not a probability" in item for item in context.warnings)
    # 3. And the scanner refuses the output if both fail.
    assert safety.scan_output("Başarı şansınız %72.") != []
