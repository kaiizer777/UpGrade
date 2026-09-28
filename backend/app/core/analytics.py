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
_tool_errors: dict[str, Counter[str]] = defaultdict(Counter)
_tool_latencies: dict[str, list[int]] = defaultdict(list)
_event_counts: Counter[str] = Counter()
_latency_ms: dict[str, list[int]] = defaultdict(list)


def record_tool_result(
    tool_name: str,
    success: bool,
    error_code: str | None = None,
    latency_ms: int = 0,
) -> None:
    """Increment per-tool success/failure counter, record error code & latency, and log at INFO."""
    if success:
        _tool_success[tool_name] += 1
    else:
        _tool_failure[tool_name] += 1
        if error_code:
            _tool_errors[tool_name][error_code] += 1

    if latency_ms > 0:
        _tool_latencies[tool_name].append(latency_ms)
        if len(_tool_latencies[tool_name]) > 100:
            _tool_latencies[tool_name].pop(0)

    total = _tool_success[tool_name] + _tool_failure[tool_name]
    success_rate = (_tool_success[tool_name] / total * 100) if total else 0.0
    tool_lats = _tool_latencies[tool_name]
    avg_tool_lat = (sum(tool_lats) / len(tool_lats)) if tool_lats else 0.0

    logger.info(
        "analytics tool_call tool=%s success=%s error_code=%s latency_ms=%d total=%d success_rate=%.1f%% fail=%d ok=%d avg_latency_ms=%.1f",
        tool_name,
        success,
        error_code or "none",
        latency_ms,
        total,
        success_rate,
        _tool_failure[tool_name],
        _tool_success[tool_name],
        avg_tool_lat,
    )


def record_tool_call(
    tool_name: str,
    success: bool,
    error_code: str | None = None,
    latency_ms: int = 0,
) -> None:
    """Alias for record_tool_result."""
    record_tool_result(
        tool_name=tool_name,
        success=success,
        error_code=error_code,
        latency_ms=latency_ms,
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


def get_tool_stats() -> list[dict[str, object]]:
    """Return list of aggregated per-tool metrics."""
    all_tools = sorted(
        set(_tool_success.keys())
        | set(_tool_failure.keys())
        | set(_tool_latencies.keys())
    )
    stats: list[dict[str, object]] = []
    for name in all_tools:
        succ = _tool_success[name]
        fail = _tool_failure[name]
        total = succ + fail
        rate = (succ / total * 100) if total else 0.0
        lats = _tool_latencies[name]
        avg_lat = (sum(lats) / len(lats)) if lats else 0.0
        stats.append(
            {
                "tool": name,
                "success": succ,
                "failure": fail,
                "total": total,
                "success_rate": round(rate, 2),
                "avg_latency_ms": round(avg_lat, 2),
                "error_codes": dict(_tool_errors[name]),
            }
        )
    return stats


def get_counters_snapshot() -> dict[str, object]:
    """Return snapshot of counters for health/debug endpoints."""
    return {
        "tools": get_tool_stats(),
        "tool_success": dict(_tool_success),
        "tool_failure": dict(_tool_failure),
        "events": dict(_event_counts),
        "latency_avg_ms": {
            k: round(sum(v) / len(v), 2) if v else 0.0
            for k, v in _latency_ms.items()
        },
    }


def reset_counters() -> None:
    """Reset all counters (for tests)."""
    _tool_success.clear()
    _tool_failure.clear()
    _tool_errors.clear()
    _tool_latencies.clear()
    _event_counts.clear()
    _latency_ms.clear()
