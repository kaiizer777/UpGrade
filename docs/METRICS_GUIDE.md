# Metrics and Telemetry Guide

## Overview

The `backend.app.core.metrics` module provides a thread-safe, in-memory telemetry system designed for high-throughput instrumentation with zero external infrastructure dependencies.

### Instrument Types

1. **Counters (`CounterMetric`)**: Monotonically increasing numbers used to count events, errors, or requests.
   ```python
   from backend.app.core.metrics import default_registry

   requests_counter = default_registry.counter("http_requests_total")
   requests_counter.inc(tags={"endpoint": "/health", "status": "200"})
   ```

2. **Gauges (`GaugeMetric`)**: Instantaneous values that can go up and down (memory usage, queue depths, pool connections).
   ```python
   pool_gauge = default_registry.gauge("db_connections_active")
   pool_gauge.set(14.0, tags={"pool": "primary"})
   ```

3. **Histograms (`HistogramMetric`)**: Sample observations over configurable sliding windows, computing percentiles ($p50$, $p90$, $p95$, $p99$) and summary statistics ($mean$, $stddev$, $min$, $max$).
   ```python
   latency_hist = default_registry.histogram("request_latency_seconds")
   latency_hist.observe(0.042, tags={"route": "/api/v1/users"})
   percentiles = latency_hist.percentiles()
   ```

4. **Summaries (`SummaryMetric`)**: Rolling aggregates tracking counts, numeric totals, and arithmetic averages.
   ```python
   payload_summary = default_registry.summary("payload_bytes_total")
   payload_summary.observe(1024, tags={"action": "export"})
   stats = payload_summary.get_stats()
   ```

### Execution Timing Block

To measure execution time of blocks or functions, use the `time_block` context manager:

```python
from backend.app.core.metrics import time_block

with time_block("query_execution_seconds", tags={"query": "user_lookup"}):
    perform_expensive_operation()
```

### Exporting Metrics

The registry provides a complete JSON-serializable snapshot of all registered metrics:

```python
snapshot = default_registry.export_all()
print(snapshot["timestamp"])
print(snapshot["counters"])
print(snapshot["gauges"])
print(snapshot["histograms"])
print(snapshot["summaries"])
```

### Thread Safety

All metric instruments utilize internal threading locks to guarantee atomic mutations under high concurrent access without corrupting internal state or ring buffers.
