"""Tests for analytics module and /admin/stats endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.analytics import (
    get_counters_snapshot,
    get_tool_stats,
    record_event,
    record_latency,
    record_tool_call,
    record_tool_result,
    reset_counters,
    timed,
)
from app.main import app


@pytest.fixture(autouse=True)
def clean_counters() -> None:
    reset_counters()
    yield
    reset_counters()


def test_record_tool_result_success_and_failure() -> None:
    record_tool_result("test_tool", success=True, latency_ms=45)
    record_tool_result(
        "test_tool", success=False, error_code="VALIDATION_ERROR", latency_ms=12
    )

    stats = get_tool_stats()
    assert len(stats) == 1
    tool_stat = stats[0]
    assert tool_stat["tool"] == "test_tool"
    assert tool_stat["success"] == 1
    assert tool_stat["failure"] == 1
    assert tool_stat["total"] == 2
    assert tool_stat["success_rate"] == 50.0
    assert tool_stat["avg_latency_ms"] == 28.5
    assert tool_stat["error_codes"] == {"VALIDATION_ERROR": 1}


def test_record_tool_call_alias() -> None:
    record_tool_call("alias_tool", success=True, latency_ms=100)
    snapshot = get_counters_snapshot()
    assert snapshot["tool_success"]["alias_tool"] == 1
    assert snapshot["tool_failure"].get("alias_tool", 0) == 0


def test_record_latency_and_timed() -> None:
    record_latency("feed_gen", 120)
    record_latency("feed_gen", 180)

    with timed("chat_turn"):
        pass

    snapshot = get_counters_snapshot()
    assert snapshot["latency_avg_ms"]["feed_gen"] == 150.0
    assert "chat_turn" in snapshot["latency_avg_ms"]


def test_record_event() -> None:
    record_event("feed_generated", topic_id=1, post_count=5)
    snapshot = get_counters_snapshot()
    assert snapshot["events"]["feed_generated"] == 1


@pytest.mark.asyncio
async def test_admin_stats_endpoint() -> None:
    record_tool_result("save_answer", success=True, latency_ms=30)
    record_tool_result(
        "create_roadmap", success=False, error_code="TOOL_ERROR", latency_ms=50
    )
    record_event("test_event")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "tool_success" in data
        assert "tool_failure" in data
        assert "events" in data
        assert "latency_avg_ms" in data

        tools = {t["tool"]: t for t in data["tools"]}
        assert "save_answer" in tools
        assert tools["save_answer"]["success"] == 1
        assert "create_roadmap" in tools
        assert tools["create_roadmap"]["failure"] == 1
        assert tools["create_roadmap"]["error_codes"] == {"TOOL_ERROR": 1}
