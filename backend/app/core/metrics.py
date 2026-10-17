"""Production-grade In-Memory Metrics Registry and Telemetry Aggregator.

Provides lightweight instrumentation primitives for latency distributions,
error budgets, sliding-window histograms, and health gauges with minimal overhead.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class MetricSample:
    """Represents a point-in-time recorded metric sample."""

    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


class CounterMetric:
    """Thread-safe monotonic incrementing counter."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._lock = threading.Lock()
        self._counts: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)

    def inc(self, amount: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment counter by specified positive amount."""
        if amount < 0:
            raise ValueError(f"Counter increment must be non-negative: {amount}")
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._counts[key] += amount

    def get(self, tags: Optional[Dict[str, str]] = None) -> float:
        """Return current cumulative value for tag set."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            return self._counts.get(key, 0.0)

    def snapshot(self) -> Dict[str, Any]:
        """Produce point-in-time snapshot of counter values."""
        with self._lock:
            return {
                "name": self.name,
                "type": "counter",
                "description": self.description,
                "values": [
                    {"tags": dict(key), "value": val}
                    for key, val in self._counts.items()
                ],
            }


class GaugeMetric:
    """Thread-safe gauge representing instantaneous values."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._lock = threading.Lock()
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def set(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set gauge to absolute value."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._values[key] = float(value)

    def get(self, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Read instantaneous value."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            return self._values.get(key)

    def snapshot(self) -> Dict[str, Any]:
        """Produce point-in-time snapshot of gauge values."""
        with self._lock:
            return {
                "name": self.name,
                "type": "gauge",
                "description": self.description,
                "values": [
                    {"tags": dict(key), "value": val}
                    for key, val in self._values.items()
                ],
            }


class HistogramMetric:
    """Sliding-window histogram supporting quantiles and summary statistics."""

    DEFAULT_BUCKETS: Sequence[float] = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    )

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[Sequence[float]] = None,
        max_samples: int = 1_000,
    ) -> None:
        self.name = name
        self.description = description
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self.max_samples = max_samples
        self._lock = threading.Lock()
        self._samples: Dict[Tuple[Tuple[str, str], ...], deque[float]] = defaultdict(
            lambda: deque(maxlen=self.max_samples)
        )

    def observe(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record an observed measurement into the distribution window."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._samples[key].append(float(value))

    def percentiles(
        self,
        quantiles: Sequence[float] = (0.50, 0.90, 0.95, 0.99),
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Compute nearest-rank quantile estimates from sliding sample window."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            records = sorted(self._samples.get(key, []))

        if not records:
            return {f"p{int(q * 100)}": 0.0 for q in quantiles}

        result: Dict[str, float] = {}
        n = len(records)
        for q in quantiles:
            idx = max(0, min(n - 1, math.ceil(q * n) - 1))
            result[f"p{int(q * 100)}"] = records[idx]
        return result

    def summary(self, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Calculate mean, standard deviation, and count for current tag series."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            records = list(self._samples.get(key, []))

        if not records:
            return {"count": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0, "stddev": 0.0}

        count = len(records)
        mean_val = sum(records) / count
        variance = sum((x - mean_val) ** 2 for x in records) / count
        return {
            "count": float(count),
            "mean": round(mean_val, 4),
            "min": round(min(records), 4),
            "max": round(max(records), 4),
            "stddev": round(math.sqrt(variance), 4),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Export serialized histogram distribution snapshot."""
        with self._lock:
            all_keys = list(self._samples.keys())

        output: List[Dict[str, Any]] = []
        for key in all_keys:
            tag_dict = dict(key)
            output.append(
                {
                    "tags": tag_dict,
                    "summary": self.summary(tags=tag_dict),
                    "percentiles": self.percentiles(tags=tag_dict),
                }
            )
        return {
            "name": self.name,
            "type": "histogram",
            "description": self.description,
            "series": output,
        }


class SummaryMetric:
    """Thread-safe summary tracking rolling counts, totals, and arithmetic averages."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._lock = threading.Lock()
        self._totals: Dict[Tuple[Tuple[str, str], ...], float] = defaultdict(float)
        self._counts: Dict[Tuple[Tuple[str, str], ...], int] = defaultdict(int)

    def observe(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Observe a numeric magnitude into the running aggregate."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._totals[key] += float(value)
            self._counts[key] += 1

    def get_stats(self, tags: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Retrieve total, count, and mean for specified tags."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            total = self._totals.get(key, 0.0)
            count = self._counts.get(key, 0)
        mean = (total / count) if count > 0 else 0.0
        return {"total": total, "count": float(count), "mean": round(mean, 4)}

    def snapshot(self) -> Dict[str, Any]:
        """Produce point-in-time snapshot of summary series."""
        with self._lock:
            all_keys = list(self._counts.keys())
        return {
            "name": self.name,
            "type": "summary",
            "description": self.description,
            "series": [
                {
                    "tags": dict(key),
                    "stats": self.get_stats(tags=dict(key)),
                }
                for key in all_keys
            ],
        }


class MetricsRegistry:
    """Central registry maintaining decoupled application metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, CounterMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._summaries: Dict[str, SummaryMetric] = {}

    def counter(self, name: str, description: str = "") -> CounterMetric:
        """Register or retrieve named counter."""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = CounterMetric(name, description)
            return self._counters[name]

    def gauge(self, name: str, description: str = "") -> GaugeMetric:
        """Register or retrieve named gauge."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = GaugeMetric(name, description)
            return self._gauges[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[Sequence[float]] = None,
        max_samples: int = 1_000,
    ) -> HistogramMetric:
        """Register or retrieve named histogram."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = HistogramMetric(
                    name=name,
                    description=description,
                    buckets=buckets,
                    max_samples=max_samples,
                )
            return self._histograms[name]

    def summary(self, name: str, description: str = "") -> SummaryMetric:
        """Register or retrieve named summary metric."""
        with self._lock:
            if name not in self._summaries:
                self._summaries[name] = SummaryMetric(name, description)
            return self._summaries[name]

    def export_all(self) -> Dict[str, Any]:
        """Export full registry snapshot across all instruments."""
        with self._lock:
            counters = list(self._counters.values())
            gauges = list(self._gauges.values())
            histograms = list(self._histograms.values())
            summaries = list(self._summaries.values())

        return {
            "timestamp": time.time(),
            "counters": [c.snapshot() for c in counters],
            "gauges": [g.snapshot() for g in gauges],
            "histograms": [h.snapshot() for h in histograms],
            "summaries": [s.snapshot() for s in summaries],
        }

    def clear(self) -> None:
        """Reset all metrics in registry."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._summaries.clear()


# Default singleton registry
default_registry = MetricsRegistry()


class TimerContext:
    """Context manager for timing execution blocks and publishing to histogram."""

    def __init__(
        self,
        histogram: HistogramMetric,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        self.histogram = histogram
        self.tags = tags
        self._start_time: float = 0.0

    def __enter__(self) -> "TimerContext":
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed_seconds = time.perf_counter() - self._start_time
        self.histogram.observe(elapsed_seconds, tags=self.tags)


def time_block(
    metric_name: str,
    tags: Optional[Dict[str, str]] = None,
    registry: Optional[MetricsRegistry] = None,
) -> TimerContext:
    """Helper factory for timing code blocks into default or custom registry."""
    reg = registry or default_registry
    hist = reg.histogram(metric_name, description=f"Execution timer for {metric_name}")
    return TimerContext(hist, tags=tags)
