"""Router tests for /subjects/{sid}/topics/{tid}/chat"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.subject import Subject
from app.models.topic import Topic, TopicStatus
from app.services.ai import AiConfigError, AiGenerationError

from tests.test_chat_service import _create_subject, _create_topic, _make_ready_profile


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
async def test_post_chat_happy(client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    topic = await _create_topic(session, subject.id)

    async def fake_chat_turn(*_a, **_k):  # type: ignore[no-untyped-def]
        return {
            "reply": "Recursion is ...",
            "messages": [
                {"id": 1, "topic_id": topic.id, "role": "user", "content": "explain recursion", "created_at": "2026-01-01T00:00:00Z"},
                {"id": 2, "topic_id": topic.id, "role": "assistant", "content": "Recursion is ...", "created_at": "2026-01-01T00:00:01Z"},
            ],
        }

    monkeypatch.setattr("app.api.routers.chat.chat_turn", fake_chat_turn)

    resp = await client.post(f"/subjects/{subject.id}/topics/{topic.id}/chat", json={"message": "explain recursion"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Recursion is ..."
    assert len(body["messages"]) == 2


@pytest.mark.asyncio
async def test_get_chat_history_empty(client, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    topic = await _create_topic(session, subject.id)

    resp = await client.get(f"/subjects/{subject.id}/topics/{topic.id}/chat")
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages"] == []
    assert body["topic_id"] == topic.id


@pytest.mark.asyncio
async def test_get_chat_history_ordered(client, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    topic = await _create_topic(session, subject.id)
    for role, content in [("user", "hi"), ("assistant", "hello")]:
        session.add(ChatMessage(topic_id=topic.id, role=role, content=content))  # type: ignore[arg-type]
    await session.commit()

    resp = await client.get(f"/subjects/{subject.id}/topics/{topic.id}/chat")
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["content"] == "hello"
    assert msgs[0]["role"] == "user"


@pytest.mark.asyncio
async def test_post_chat_404_subject(client) -> None:
    resp = await client.post(f"/subjects/{uuid.uuid4()}/topics/999/chat", json={"message": "hi"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_chat_404_topic_mismatch(client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s1 = await _create_subject(session, "S1")
    s2 = await _create_subject(session, "S2")
    t = await _create_topic(session, s1.id)

    async def raise_not_found(*_a, **_k):  # type: ignore[no-untyped-def]
        from app.services.chat import TopicNotFoundError

        raise TopicNotFoundError("not found")

    monkeypatch.setattr("app.api.routers.chat.chat_turn", raise_not_found)

    resp = await client.post(f"/subjects/{s2.id}/topics/{t.id}/chat", json={"message": "hi"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_chat_400_empty(client, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    topic = await _create_topic(session, subject.id)
    resp = await client.post(f"/subjects/{subject.id}/topics/{topic.id}/chat", json={"message": "   "})
    # Pydantic min_length catches? But router also checks stripped; expect 400 or 422
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_post_chat_503(client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    topic = await _create_topic(session, subject.id)

    async def raise_cfg(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AiConfigError("no key")

    monkeypatch.setattr("app.api.routers.chat.chat_turn", raise_cfg)
    resp = await client.post(f"/subjects/{subject.id}/topics/{topic.id}/chat", json={"message": "hi"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_post_chat_502(client, session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    topic = await _create_topic(session, subject.id)

    async def raise_gen(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AiGenerationError("boom")

    monkeypatch.setattr("app.api.routers.chat.chat_turn", raise_gen)
    resp = await client.post(f"/subjects/{subject.id}/topics/{topic.id}/chat", json={"message": "hi"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_chat_404(client) -> None:
    resp = await client.get(f"/subjects/{uuid.uuid4()}/topics/123/chat")
    assert resp.status_code == 404
