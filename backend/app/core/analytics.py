"""Basic analytics / counters via structured INFO logging.

In-memory counters for tool success/failure rates and generation latency.
All events are logged at INFO level for aggregation (cloud logging, etc.).
No external dependency; trivial to swap for real analytics sink.
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger("upgrade.analytics")

# In-memory counters (process-local)
_tool_success: Counter[str] = Counter()
_tool_failure: Counter[str] = Counter()
_event_counts: Counter[str] = Counter()
_latency_ms: dict[str, list[int]] = defaultdict(list)


def record_tool_result(tool_name: str, success: bool) -> None:
    """Increment per-tool success/failure counter and log at INFO."""
    if success:
        _tool_success[tool_name] += 1
    else:
        _tool_failure[tool_name] += 1
    total = _tool_success[tool_name] + _tool_failure[tool_name]
    success_rate = (_tool_success[tool_name] / total * 100) if total else 0
    logger.info(
        "analytics tool=%s success=%s total=%s success_rate=%.1f%% fail=%s ok=%s",
        tool_name,
        success,
        total,
        success_rate,
        _tool_failure[tool_name],
        _tool_success[tool_name],
    )


def record_event(event: str, **fields: object) -> None:
    """Increment generic event counter and emit INFO log with fields."""
    _event_counts[event] += 1
    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    extra = f" {kv}" if kv else ""
    logger.info("analytics event=%s count=%s%s", event, _event_counts[event], extra)


def record_latency(operation: str, latency_ms_val: int) -> None:
    """Record generation latency and log at INFO."""
    _latency_ms[operation].append(latency_ms_val)
    # keep last 100
    if len(_latency_ms[operation]) > 100:
        _latency_ms[operation].pop(0)
    avg = sum(_latency_ms[operation]) / len(_latency_ms[operation])
    logger.info(
        "analytics latency operation=%s ms=%s avg_ms=%.1f samples=%s",
        operation,
        latency_ms_val,
        avg,
        len(_latency_ms[operation]),
    )


@contextmanager
def timed(operation: str) -> Generator[None]:
    """Context manager that records latency for an operation."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        record_latency(operation, elapsed_ms)


def get_counters_snapshot() -> dict:
    """Return snapshot of counters for health/debug endpoints."""
    return {
        "tool_success": dict(_tool_success),
        "tool_failure": dict(_tool_failure),
        "events": dict(_event_counts),
        "latency_avg_ms": {
            k: (sum(v) / len(v) if v else 0) for k, v in _latency_ms.items()
        },
    }


def reset_counters() -> None:
    """Reset all counters (for tests)."""
    _tool_success.clear()
    _tool_failure.clear()
    _event_counts.clear()
    _latency_ms.clear()
