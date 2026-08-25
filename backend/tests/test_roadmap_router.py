"""Router tests for /subjects/{id}/roadmap (no real LLM)."""

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
from app.models.topic import Topic, TopicStatus
from app.services.ai import AiConfigError, AiGenerationError
from tests.test_roadmap_service import _create_subject


@pytest.fixture
async def client(session: AsyncSession):
    async def _override_get_session() -> AsyncSession:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_roadmap_201_create(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST creates roadmap returns 201."""
    subject = await _create_subject(session, "Router 201 Subject")
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

    fake_result = {
        "subject_id": str(subject.id),
        "topics": [
            {
                "id": i + 1,
                "subject_id": str(subject.id),
                "title": f"Topic {i + 1}",
                "order_index": i + 1,
                "prerequisite_ids": [] if i == 0 else [1],
                "status": "active" if i == 0 else "pending",
            }
            for i in range(6)
        ],
        "active_topic_id": 1,
    }

    async def _fake_generate(*_a, **_k):  # type: ignore[no-untyped-def]
        return fake_result

    monkeypatch.setattr("app.api.routers.roadmap.generate_roadmap", _fake_generate)

    resp = await client.post(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 201
    body = resp.json()
    assert body["subject_id"] == str(subject.id)
    assert len(body["topics"]) == 6
    assert body["active_topic_id"] == 1
    assert body["topics"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_post_roadmap_idempotent_200(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST when roadmap already exists returns 200 without calling service."""
    subject = await _create_subject(session, "Idempotent Router")
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
    # Insert topics directly
    for i in range(3):
        session.add(
            Topic(
                subject_id=subject.id,
                title=f"T{i + 1}",
                order_index=i + 1,
                prerequisite_ids=[],
                status=TopicStatus.ACTIVE if i == 0 else TopicStatus.PENDING,
            )
        )
    await session.commit()

    called = False

    async def _should_not_be_called(*_a, **_k):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        raise AssertionError("generate_roadmap should not be called on idempotent hit")

    monkeypatch.setattr(
        "app.api.routers.roadmap.generate_roadmap", _should_not_be_called
    )

    resp = await client.post(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 200
    assert not called
    body = resp.json()
    assert len(body["topics"]) == 3


@pytest.mark.asyncio
async def test_get_roadmap_empty_returns_200(client, session: AsyncSession) -> None:
    """GET returns 200 with empty topics when not yet generated."""
    subject = await _create_subject(session, "Empty GET")
    resp = await client.get(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_id"] == str(subject.id)
    assert body["topics"] == []
    assert body["active_topic_id"] is None


@pytest.mark.asyncio
async def test_get_roadmap_with_topics_ordered(client, session: AsyncSession) -> None:
    """GET returns topics ordered by order_index."""
    subject = await _create_subject(session, "Ordered GET")
    # Insert out of order to verify ordering
    for oi, title in [(3, "C"), (1, "A"), (2, "B")]:
        session.add(
            Topic(
                subject_id=subject.id,
                title=title,
                order_index=oi,
                prerequisite_ids=[],
                status=TopicStatus.PENDING,
            )
        )
    await session.commit()
    # Manually set first to active
    from sqlmodel import select as _select

    stmt = (
        _select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.order_index)
    )  # type: ignore[attr-defined]
    topics = list((await session.exec(stmt)).all())
    topics[0].status = TopicStatus.ACTIVE
    session.add(topics[0])
    await session.commit()

    resp = await client.get(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 200
    body = resp.json()
    assert [t["order_index"] for t in body["topics"]] == [1, 2, 3]
    assert [t["title"] for t in body["topics"]] == ["A", "B", "C"]
    assert body["active_topic_id"] == topics[0].id


@pytest.mark.asyncio
async def test_get_roadmap_404(client) -> None:
    """GET unknown subject → 404."""
    resp = await client.get(f"/subjects/{uuid.uuid4()}/roadmap")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_roadmap_404(client) -> None:
    """POST unknown subject → 404."""
    resp = await client.post(f"/subjects/{uuid.uuid4()}/roadmap")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_roadmap_409_maps_not_ready(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """409 when onboarding not finalized."""
    subject = await _create_subject(session, "409 Subject")

    async def _raise_not_ready(*_a, **_k):  # type: ignore[no-untyped-def]
        from app.services.roadmap import RoadmapNotReadyError

        raise RoadmapNotReadyError("Onboarding not finalized")

    monkeypatch.setattr("app.api.routers.roadmap.generate_roadmap", _raise_not_ready)
    resp = await client.post(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Onboarding not finalized"


@pytest.mark.asyncio
async def test_post_roadmap_502_maps_generation_error(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """502 when generation fails."""
    subject = await _create_subject(session, "502 Subject")
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

    async def _raise_gen(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AiGenerationError("boom")

    monkeypatch.setattr("app.api.routers.roadmap.generate_roadmap", _raise_gen)
    resp = await client.post(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "AI generation failed"


@pytest.mark.asyncio
async def test_post_roadmap_503_maps_config_error(
    client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 when provider not configured."""
    subject = await _create_subject(session, "503 Subject")
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

    async def _raise_cfg(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AiConfigError("no key")

    monkeypatch.setattr("app.api.routers.roadmap.generate_roadmap", _raise_cfg)
    resp = await client.post(f"/subjects/{subject.id}/roadmap")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "AI provider not configured"
