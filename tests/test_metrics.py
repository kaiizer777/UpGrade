"""Unit tests for production-grade metrics registry and telemetry aggregator."""

import time
import pytest
from backend.app.core.metrics import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    SummaryMetric,
    MetricsRegistry,
    default_registry,
    time_block,
)


def test_counter_metric_basic_increment():
    counter = CounterMetric("http_requests_total", description="Total HTTP requests")
    assert counter.get() == 0.0

    counter.inc()
    assert counter.get() == 1.0

    counter.inc(2.5)
    assert counter.get() == 3.5


def test_counter_metric_tagged_increments():
    counter = CounterMetric("api_calls")
    counter.inc(1.0, tags={"handler": "users", "method": "GET"})
    counter.inc(2.0, tags={"handler": "users", "method": "GET"})
    counter.inc(1.0, tags={"handler": "orders", "method": "POST"})

    assert counter.get(tags={"handler": "users", "method": "GET"}) == 3.0
    assert counter.get(tags={"handler": "orders", "method": "POST"}) == 1.0
    assert counter.get(tags={"handler": "unknown"}) == 0.0


def test_counter_negative_increment_raises():
    counter = CounterMetric("bad_counter")
    with pytest.raises(ValueError, match="non-negative"):
        counter.inc(-1.0)


def test_counter_snapshot():
    counter = CounterMetric("test_counter", description="A test counter")
    counter.inc(5.0, tags={"env": "prod"})
    snap = counter.snapshot()

    assert snap["name"] == "test_counter"
    assert snap["type"] == "counter"
    assert len(snap["values"]) == 1
    assert snap["values"][0]["value"] == 5.0
    assert snap["values"][0]["tags"] == {"env": "prod"}


def test_gauge_metric_operations():
    gauge = GaugeMetric("memory_usage_mb", description="Resident memory")
    assert gauge.get() is None

    gauge.set(256.0)
    assert gauge.get() == 256.0

    gauge.set(512.5)
    assert gauge.get() == 512.5

    gauge.set(128.0, tags={"node": "worker-1"})
    assert gauge.get(tags={"node": "worker-1"}) == 128.0
    assert gauge.get() == 512.5


def test_gauge_snapshot():
    gauge = GaugeMetric("cpu_gauge")
    gauge.set(42.0, tags={"core": "0"})
    snap = gauge.snapshot()

    assert snap["name"] == "cpu_gauge"
    assert snap["type"] == "gauge"
    assert len(snap["values"]) == 1
    assert snap["values"][0]["value"] == 42.0
    assert snap["values"][0]["tags"] == {"core": "0"}


def test_histogram_percentiles_and_summary():
    hist = HistogramMetric("response_time_ms")
    # Record 100 deterministic observations from 1 to 100
    for i in range(1, 101):
        hist.observe(float(i))

    p = hist.percentiles(quantiles=(0.50, 0.90, 0.99))
    assert p["p50"] == 50.0
    assert p["p90"] == 90.0
    assert p["p99"] == 99.0

    summ = hist.summary()
    assert summ["count"] == 100.0
    assert summ["min"] == 1.0
    assert summ["max"] == 100.0
    assert summ["mean"] == 50.5


def test_histogram_empty_summary():
    hist = HistogramMetric("empty_hist")
    summ = hist.summary()
    assert summ["count"] == 0.0
    assert summ["mean"] == 0.0
    assert summ["min"] == 0.0

    p = hist.percentiles()
    assert p["p50"] == 0.0


def test_histogram_sliding_window_bound():
    hist = HistogramMetric("bounded_hist", max_samples=10)
    for i in range(20):
        hist.observe(float(i))

    summ = hist.summary()
    assert summ["count"] == 10.0
    assert summ["min"] == 10.0
    assert summ["max"] == 19.0


def test_summary_metric_stats_and_snapshot():
    summary = SummaryMetric("payload_bytes", description="Payload sizes")
    summary.observe(100.0, tags={"route": "/upload"})
    summary.observe(200.0, tags={"route": "/upload"})
    summary.observe(300.0, tags={"route": "/upload"})

    stats = summary.get_stats(tags={"route": "/upload"})
    assert stats["count"] == 3.0
    assert stats["total"] == 600.0
    assert stats["mean"] == 200.0

    snap = summary.snapshot()
    assert snap["name"] == "payload_bytes"
    assert snap["type"] == "summary"
    assert len(snap["series"]) == 1
    assert snap["series"][0]["stats"]["count"] == 3.0


def test_metrics_registry_retrieval_and_export():
    registry = MetricsRegistry()

    c1 = registry.counter("req_total")
    c2 = registry.counter("req_total")
    assert c1 is c2

    g1 = registry.gauge("queue_depth")
    g2 = registry.gauge("queue_depth")
    assert g1 is g2

    h1 = registry.histogram("query_duration")
    h2 = registry.histogram("query_duration")
    assert h1 is h2

    s1 = registry.summary("byte_size")
    s2 = registry.summary("byte_size")
    assert s1 is s2

    c1.inc(10)
    g1.set(5)
    h1.observe(0.2)
    s1.observe(1024)

    export = registry.export_all()
    assert "timestamp" in export
    assert len(export["counters"]) == 1
    assert len(export["gauges"]) == 1
    assert len(export["histograms"]) == 1
    assert len(export["summaries"]) == 1

    registry.clear()
    empty_export = registry.export_all()
    assert len(empty_export["counters"]) == 0
    assert len(empty_export["gauges"]) == 0
    assert len(empty_export["histograms"]) == 0
    assert len(empty_export["summaries"]) == 0


def test_timer_context_block():
    registry = MetricsRegistry()
    with time_block("operation_elapsed", tags={"op": "db_fetch"}, registry=registry):
        time.sleep(0.01)

    hist = registry.histogram("operation_elapsed")
    summ = hist.summary(tags={"op": "db_fetch"})
    assert summ["count"] == 1.0
    assert summ["mean"] >= 0.008  # at least ~8ms elapsed
