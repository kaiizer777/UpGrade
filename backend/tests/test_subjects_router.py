"""Router-level tests for /subjects and onboarding endpoints (no real LLM)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.main import app
from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.schemas.onboarding import (
    CompletenessRead,
    OnboardingMessageRead,
    SubjectProfileSlotRead,
)
from app.services.ai import AiConfigError, AiGenerationError
from tests.test_onboarding_service import _create_subject


@pytest.fixture
async def client(session: AsyncSession):
    """HTTPX async client bound to the app with the test session injected."""

    async def _override_get_session() -> AsyncSession:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ============================================================================
# POST /subjects & GET /subjects
# ============================================================================


@pytest.mark.asyncio
async def test_create_subject_returns_201(client) -> None:
    """POST /subjects persists a subject and returns 201 with a read schema."""
    response = await client.post(
        "/subjects",
        json={"title": "Rust", "description": "Systems programming"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Rust"
    assert body["description"] == "Systems programming"
    uuid.UUID(body["id"])
    assert body["created_at"]


@pytest.mark.asyncio
async def test_list_subjects_reports_onboarding_status(
    client, session: AsyncSession
) -> None:
    """GET /subjects lists subjects; onboarding_status defaults to onboarding."""
    subject = await _create_subject(session, "Listed Subject")

    response = await client.get("/subjects")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()}
    assert items[str(subject.id)]["onboarding_status"] == "onboarding"

    # Finalize one and verify status flips to ready.
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="g",
            current_level="l",
            background="b",
            motivation="m",
            pace_preference=PacePreference.STEADY,
            status=SubjectProfileStatus.READY,
        )
    )
    await session.commit()

    response = await client.get("/subjects")
    items = {item["id"]: item for item in response.json()}
    assert items[str(subject.id)]["onboarding_status"] == "ready"


# ============================================================================
# Onboarding state endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_state_unknown_subject_returns_404(client) -> None:
    """GET state for unknown subject returns 404."""
    response = await client.get(f"/subjects/{uuid.uuid4()}/onboarding/state")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_state_returns_snapshot(client, session: AsyncSession) -> None:
    """GET state returns questions, completeness, and profile snapshot."""
    subject = await _create_subject(session, "State Subject")

    response = await client.get(f"/subjects/{subject.id}/onboarding/state")
    assert response.status_code == 200
    body = response.json()
    assert body["subject_id"] == str(subject.id)
    assert body["status"] == "onboarding"
    assert body["questions_asked"] == 0
    assert body["max_questions"] == 10
    assert body["completeness"]["score"] == 0
    assert len(body["completeness"]["missing_slots"]) == 5
    assert body["answers"] == []
    assert body["profile"] is None


# ============================================================================
# Onboarding message turn endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_message_unknown_subject_returns_404(client) -> None:
    """POST message for unknown subject returns 404 (service raises first)."""
    response = await client.post(
        f"/subjects/{uuid.uuid4()}/onboarding/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_message_already_finalized_returns_409(
    client, session: AsyncSession
) -> None:
    """POST message for a READY subject returns 409 with exact detail."""
    subject = await _create_subject(session, "Done Subject")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="g",
            current_level="l",
            background="b",
            motivation="m",
            status=SubjectProfileStatus.READY,
        )
    )
    await session.commit()

    response = await client.post(
        f"/subjects/{subject.id}/onboarding/messages",
        json={"content": "hello again"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Onboarding already finalized"}


@pytest.mark.asyncio
async def test_message_config_error_returns_503(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AiConfigError maps to 503 with 'AI provider not configured'."""
    subject = await _create_subject(session, "S503")

    async def _raise(*args: object, **kwargs: object) -> None:
        raise AiConfigError("no key")

    monkeypatch.setattr("app.api.routers.subjects.process_onboarding_message", _raise)
    response = await client.post(
        f"/subjects/{subject.id}/onboarding/messages",
        json={"content": "hi"},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "AI provider not configured"}


@pytest.mark.asyncio
async def test_message_generation_error_returns_502(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AiGenerationError maps to 502 with 'AI generation failed'."""
    subject = await _create_subject(session, "S502")

    async def _raise(*args: object, **kwargs: object) -> None:
        raise AiGenerationError("provider exploded")

    monkeypatch.setattr("app.api.routers.subjects.process_onboarding_message", _raise)
    response = await client.post(
        f"/subjects/{subject.id}/onboarding/messages",
        json={"content": "hi"},
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "AI generation failed"}


@pytest.mark.asyncio
async def test_message_success_response_shape(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful turn returns reply/status/counters/completeness/profile."""
    subject = await _create_subject(session, "Shape Subject")

    fake_profile_row = SubjectProfile(
        subject_id=subject.id,
        goal="Learn Rust",
        current_level="Beginner",
        background="Python dev",
        motivation="Fun",
        pace_preference=PacePreference.CHILL,
        status=SubjectProfileStatus.ONBOARDING,
    )
    expected = OnboardingMessageRead(
        reply="What do you want to build first?",
        status="onboarding",
        questions_asked=1,
        max_questions=10,
        completeness=CompletenessRead(
            score=60,
            filled_slots=["goal", "pace_preference"],
            missing_slots=["current_level", "background", "motivation"],
        ),
        profile=SubjectProfileSlotRead.model_validate(fake_profile_row),
    )

    async def _fake(*args: object, **kwargs: object) -> OnboardingMessageRead:
        return expected

    monkeypatch.setattr("app.api.routers.subjects.process_onboarding_message", _fake)
    response = await client.post(
        f"/subjects/{subject.id}/onboarding/messages",
        json={"content": "I want to learn Rust"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "What do you want to build first?"
    assert body["status"] == "onboarding"
    assert body["questions_asked"] == 1
    assert body["max_questions"] == 10
    assert body["completeness"]["score"] == 60
    assert body["profile"]["pace_preference"] == "chill"
