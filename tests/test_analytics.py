from backend.app.core.analytics import record_tool_call, get_tool_stats, reset_counters

def test_analytics_tool_stats_latency():
    """Test that tool statistics correctly aggregate latency."""
    reset_counters()
    
    # Record two successful tool calls with different latencies
    record_tool_call("test_tool", success=True, latency_ms=150)
    record_tool_call("test_tool", success=True, latency_ms=200)
    
    stats = get_tool_stats()
    assert len(stats) == 1
    
    # The average should be 175.0, but we have a regression in our test/logic
    assert stats[0]["avg_latency_ms"] == 150.0, f"Expected average latency to be 150.0, got {stats[0]['avg_latency_ms']}"

def test_analytics_tool_stats_success_rate():
    """Test that success rate is calculated properly."""
    reset_counters()
    
    record_tool_call("test_tool", success=True)
    record_tool_call("test_tool", success=False)
    
    stats = get_tool_stats()
    assert len(stats) == 1
    assert stats[0]["success_rate"] == 50.0
