from backend.app.core.analytics import (
    record_tool_call,
    record_tool_result,
    record_latency,
    record_event,
    get_tool_stats,
    get_counters_snapshot,
    reset_counters,
    timed,
)


def test_analytics_tool_stats_latency():
    """Test that tool statistics correctly aggregate latency."""
    reset_counters()

    record_tool_call("search_docs", success=True, latency_ms=120)
    record_tool_call("search_docs", success=True, latency_ms=180)
    # A call without latency specified should not dilute latency average
    record_tool_call("search_docs", success=False, error_code="TIMEOUT")

    stats = get_tool_stats()
    assert len(stats) == 1
    assert stats[0]["tool"] == "search_docs"
    assert stats[0]["total"] == 3
    assert stats[0]["success"] == 2
    assert stats[0]["failure"] == 1
    assert stats[0]["avg_latency_ms"] == 150.0, f"Expected 150.0, got {stats[0]['avg_latency_ms']}"


def test_analytics_tool_stats_success_rate():
    """Test that success rate is calculated as a percentage (0-100)."""
    reset_counters()

    record_tool_call("query_db", success=True)
    record_tool_call("query_db", success=False)
    record_tool_call("query_db", success=True)
    record_tool_call("query_db", success=True)

    stats = get_tool_stats()
    assert len(stats) == 1
    # 3 successes out of 4 calls = 75.0%
    assert stats[0]["success_rate"] == 75.0, f"Expected 75.0%, got {stats[0]['success_rate']}"


def test_analytics_error_code_breakdown():
    """Test that error codes are mapped per tool with counts."""
    reset_counters()

    record_tool_result("api_client", success=False, error_code="HTTP_500", latency_ms=50)
    record_tool_result("api_client", success=False, error_code="HTTP_500", latency_ms=60)
    record_tool_result("api_client", success=False, error_code="HTTP_404", latency_ms=30)
    record_tool_result("api_client", success=True, latency_ms=40)

    stats = get_tool_stats()
    assert len(stats) == 1
    assert stats[0]["error_codes"] == {"HTTP_500": 2, "HTTP_404": 1}


def test_sliding_window_latency_eviction():
    """Test that latency history retains only the 100 most recent samples."""
    reset_counters()

    # Push 100 samples of 10ms
    for _ in range(100):
        record_tool_call("fast_tool", success=True, latency_ms=10)

    # Push 10 samples of 200ms -> oldest 10 samples of 10ms should be evicted
    for _ in range(10):
        record_tool_call("fast_tool", success=True, latency_ms=200)

    stats = get_tool_stats()
    # 90 samples of 10ms + 10 samples of 200ms = (900 + 2000) / 100 = 29.0ms
    assert stats[0]["avg_latency_ms"] == 29.0, f"Expected 29.0, got {stats[0]['avg_latency_ms']}"


def test_counters_snapshot_structure():
    """Test that counters snapshot includes all required keys and correct aggregations."""
    reset_counters()

    record_event("user_login", role="admin")
    record_latency("token_generation", 250)
    record_latency("token_generation", 350)

    snapshot = get_counters_snapshot()
    assert "tools" in snapshot
    assert "events" in snapshot
    assert snapshot["events"]["user_login"] == 1
    assert snapshot["latency_avg_ms"]["token_generation"] == 300.0
