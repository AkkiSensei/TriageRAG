# TriageRAG OpenTelemetry Developer & Observability Guide

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

---

## 1. Overview & Safety Architecture

TriageRAG integrates OpenTelemetry distributed tracing into its LangGraph workflow engine and FastAPI HTTP layer while upholding strict clinical and data privacy invariants:

- **Rule R1 (Code Decides; LLM Explains):** Telemetry observes operational execution timing and stage completion; it never participates in clinical calculation, score bands, drug-safety checks, or protocol verification.
- **Rule R2 (Fail-Closed Zero Data Leakage):** Telemetry is subject to a strict attribute allowlist. Patient identifiers, demographics, vitals, weights, clinical scores, rule alert counts, BLOCK status, medications, doses, and abstention reasons are **strictly purged** before span export.
- **Rule R7 (Untrusted Input Isolation):** Free-text complaints and unvalidated inputs never appear in span names, attributes, or events.
- **Rule R11 (Inviolable BLOCK):** Telemetry failures cannot alter verdicts or downgrade clinical blocks.
- **Rule R12 (Determinism & Offline Safety):** Tracing relies entirely on local/loopback exporters (`in_memory`, `console`, `otlp_http` to `localhost`/`127.0.0.1`/`::1`). Cloud and external endpoints are actively rejected.

---

## 2. 3-Tier Span Parenting Hierarchy

Every traced request produces a deterministic 3-tier span tree:

```
[ Tier 1: Root HTTP Span ]
   http.request (route: /api/triage, method: POST)
       │
       ▼
[ Tier 2: Workflow Execution Span ]
   langgraph.workflow.execution (workflow: triage_state_graph)
       │
       ├─► langgraph.node.normalise
       ├─► langgraph.node.intake_safety_checks
       ├─► langgraph.node.retrieve
       │     └─► [event: routing.evaluated (edge: route_after_retrieve)]
       ├─► langgraph.node.form_plan
       ├─► langgraph.node.verify
       │     └─► [event: routing.evaluated (edge: route_after_verify)]
       ├─► langgraph.node.seal_decision
       ├─► langgraph.node.audit
       └─► langgraph.node.explain
```

### Generalized Operational Stage Names
To prevent timing side-channels and clinical outcome inference, internal mutually exclusive nodes are mapped to generalized operational stage names:

| LangGraph Internal Node | Exported Span Stage Name | Rationale |
|:---|:---|:---|
| `normalise` | `langgraph.node.normalise` | Normalizes synthetic patient demographics and vitals |
| `intake_safety_checks` | `langgraph.node.intake_safety_checks` | Evaluates rule safety checks on intake data |
| `retrieve` | `langgraph.node.retrieve` | Performs lexical BM25 protocol retrieval |
| `draft_plan` | `langgraph.node.form_plan` | Generalized plan formation stage (avoids outcome leakage) |
| `abstain_fallback` | `langgraph.node.form_plan` | Generalized plan formation stage (avoids outcome leakage) |
| `verify` | `langgraph.node.verify` | Verifies proposed care steps against formulary |
| `block_seal` | `langgraph.node.seal_decision` | Generalized decision sealing (masks BLOCK outcome) |
| `unverified_seal` | `langgraph.node.seal_decision` | Generalized decision sealing (masks UNVERIFIED outcome) |
| `verified_seal` | `langgraph.node.seal_decision` | Generalized decision sealing (masks VERIFIED outcome) |
| `audit` | `langgraph.node.audit` | Generates immutable audit trail record |
| `explain` | `langgraph.node.explain` | Renders human-readable clinical explanation |

---

## 3. Privacy Invariants: Strict Attribute Allowlist

Telemetry attributes pass through `sanitize_span_attributes()` in `src/triagerag/orchestration/telemetry.py`. Any attribute not on the allowlist is dropped. Types are strictly validated; arbitrary objects are never converted to strings.

### Permitted Attributes

| Attribute Key | Type | Allowed Values | Description |
|:---|:---|:---|:---|
| `triagerag.node.name` | `str` | `normalise`, `intake_safety_checks`, `retrieve`, `form_plan`, `verify`, `seal_decision`, `audit`, `explain` | Generalized node stage name |
| `triagerag.node.status` | `str` | `completed`, `failed` | Node execution terminal status |
| `triagerag.workflow.name` | `str` | `triage_state_graph` | Fixed workflow identifier |
| `triagerag.workflow.status` | `str` | `completed`, `failed` | Workflow terminal status |
| `triagerag.routing.edge` | `str` | `route_after_retrieve`, `route_after_verify` | Routing edge evaluated (emitted in events) |
| `http.method` | `str` | `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`, `HEAD` | Standard HTTP method |
| `http.route` | `str` | Any valid path (e.g. `/api/triage`) | Static endpoint route path |
| `http.status_code` | `int` | Standard HTTP status codes (e.g. `200`, `422`) | HTTP response status code |
| `error.type` | `str` | `application_error`, `telemetry_error` | Coarse-grained error taxonomy |

### Prohibited Attributes (Zero Tolerance)
The following attributes are **strictly forbidden** from exported spans and span events:
- No patient IDs, names, or MRNs
- No patient hash prefixes or salted identifiers
- No patient age, sex, weight, or pregnancy status
- No vital signs (heart rate, blood pressure, SpO2, temperature)
- No medication names, doses, routes, frequencies, or timestamps
- No allergy history or reaction types
- No early warning scores (NEWS2, PEWS) or score bands
- No safety alert counts, alert codes, or BLOCK indicators
- No final clinical verdicts (`BLOCK`, `UNVERIFIED`, `VERIFIED`)
- No protocol chunk counts, retrieved texts, or search queries
- No exception messages, traceback strings, or local variable frames

---

## 4. Guaranteed Non-Interference Architecture

Clinical calculation integrity is protected by `TraceNodeContextManager`:

```python
class TraceNodeContextManager:
    """Wraps node execution ensuring telemetry errors never crash triage."""

    def __enter__(self) -> Any:
        try:
            self._span = self._cm.__enter__()
            return self._span
        except Exception as exc:
            logger.warning("Telemetry span creation failed: %s", exc)
            return _NoOpSpan()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        # Record coarse error taxonomy without leaking message
        if exc_val is not None:
            with contextlib.suppress(Exception):
                self._span.set_attribute("error.type", "application_error")
                self._span.set_attribute("triagerag.node.status", "failed")
        # Ensure __exit__ returns False: genuine application errors MUST propagate
        return False
```

### Safety Properties:
1. **Never swallow application errors:** `__exit__` unconditionally returns `False`, ensuring genuine application bugs bubble up cleanly.
2. **Never leak exception details:** Spans are created with `record_exception=False` and `set_status_on_exception=False`. Exception messages and stack traces are never attached to exported telemetry.
3. **Telemetry errors are caught and logged:** Initialization failures, exporter disconnects, or serialization bugs log a warning and fallback gracefully to `_NoOpSpan`.

---

## 5. Optional Dependency & Zero Core Burden

Core TriageRAG operates with zero dependency on `opentelemetry-*` packages. All telemetry classes fallback to an internal, pure-Python standard library implementation (`_NoOpSpan`, `_NoOpTracer`).

### Installation
To enable OpenTelemetry tracing in production or benchmarking environments:

```bash
pip install -e ".[telemetry]"
```

Declared dependencies in `pyproject.toml`:
```toml
[project.optional-dependencies]
telemetry = [
    "opentelemetry-api==1.45.1",
    "opentelemetry-sdk==1.45.1",
    "opentelemetry-exporter-otlp-proto-http==1.45.1",
]
```

---

## 6. Configuration & Environment Variables

| Variable | Default | Permitted Values | Description |
|:---|:---|:---|:---|
| `TRIAGERAG_TELEMETRY_ENABLED` | `false` | `true`, `false`, `1`, `0` | Master switch for OpenTelemetry tracing |
| `TRIAGERAG_TELEMETRY_EXPORTER` | `in_memory` | `in_memory`, `console`, `otlp_http` | Telemetry exporter backend |
| `TRIAGERAG_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` | Local loopback URI | OTLP HTTP collector destination |

### Local Loopback Endpoint Validation
Under Rule R12, the OTLP exporter enforces loopback destinations:
- **Allowed:** `http://localhost:4318/...`, `http://127.0.0.1:4318/...`, `http://[::1]:4318/...`
- **Rejected:** Cloud collector endpoints (e.g., `https://api.honeycomb.io`, `https://otlp.datadog.com`). Attempting to configure external endpoints raises `ValueError` and halts initialization.

---

## 7. W3C Distributed Context Propagation

TriageRAG implements the standard W3C Trace Context recommendation:
- **Incoming Propagation:** The FastAPI ASGI middleware extracts incoming `traceparent` headers via `TraceContextTextMapPropagator().extract()`. If present, graph execution spans are automatically parented to the external request span.
- **Outgoing Headers:** Responses carry:
  - `traceparent`: W3C compliant context header injected via `TraceContextTextMapPropagator().inject()`.
  - `X-Trace-Id`: Random 32-character hex trace identifier for log correlation.

---

## 8. Latency Benchmarking (`tools/benchmark_telemetry.py`)

A reproducible benchmark script evaluates telemetry latency overhead across $N=100$ iterations using a standardized synthetic patient.

### Running the Benchmark
```bash
python tools/benchmark_telemetry.py -n 100 -w 10
```

### Empirical Results (Windows 11, Python 3.13.7)

| Configuration | Sample (N) | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | StdDev |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Config 1: Telemetry Disabled** | 100 | **11.057** | **9.776** | **18.307** | 33.585 | 33.585 | 4.273 |
| **Config 2: In-Memory Tracing** | 100 | **14.901** | **12.732** | **29.277** | 54.998 | 54.998 | 6.770 |
| **Config 3: Console Exporter** | 100 | **24.284** | **15.265** | **75.219** | 174.732 | 174.732 | 27.509 |

**Detailed Overhead & Benchmark Limitations:**
- **In-Memory p95 Overhead:** In-memory p95 overhead is **+10.970 ms** against the disabled baseline (29.277 ms vs 18.307 ms). Mean overhead is **+3.844 ms** (+2.956 ms at p50).
- **Optimization Target Status:** The preliminary optimization ceiling target of $\le 1.50\,\text{ms}$ at p95 was **NOT met** under this Windows Python 3.13 environment due to span creation and object allocation overhead. In-memory p99 and maximum latency reached **54.998 ms**.
- **Console Exporter Overhead:** Console p95 latency reached **75.219 ms** and p99/max reached **174.732 ms** (mean overhead +13.227 ms), dominated by synchronous stdout JSON serialization and stream flushing per span.
- **OTLP Exporter Status:** OTLP HTTP performance was **not measured** because Docker was unavailable on the local host to host a Jaeger collector.
- **Output Report:** The full empirical output is persisted to `eval/reports/telemetry_benchmark.json`.

---

## 9. Residual Side-Channel Limitations

While the strict allowlist and generalized stage names prevent direct attribute leakage of clinical outcomes, two residual side channels remain:

1. **Timing Side-Channel:**
   - Although mutually exclusive branches are collapsed to identical operational stage names (`form_plan`, `seal_decision`), execution time differences between fast paths (e.g. immediate BLOCK or missing data early aborts) and complete paths (e.g. exhaustive BM25 retrieval across multiple syndrome chunks followed by complex formulary checks) introduce measurable timing variance.
   - An external observer with high-precision timestamp access could statistically differentiate rapid contraindication paths from deep retrieval verification paths based on span durations.
2. **Exceptional Termination Side-Channel:**
   - If an unhandled exception occurs inside a node, the span records `triagerag.node.status: failed` and `error.type: application_error` on that specific node span before the exception propagates.
   - While the exception message and traceback are strictly withheld, the identity of the failing operational stage (e.g., failure during `verify` vs `retrieve`) is revealed in telemetry, disclosing the precise stage of clinical calculation failure.

---

## 10. Local Jaeger Docker Setup

To visualize traces locally without cloud dependencies:

### Prerequisites
- Docker & Docker Compose installed on host machine.

### `docker-compose.telemetry.yml`
```yaml
version: '3.8'
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "127.0.0.1:16686:16686" # Web UI
      - "127.0.0.1:4318:4318"   # OTLP HTTP receiver
```

### Starting Jaeger & TriageRAG
```bash
# 1. Start Jaeger locally
docker compose -f docker-compose.telemetry.yml up -d

# 2. Start TriageRAG with OTLP exporter
set TRIAGERAG_TELEMETRY_ENABLED=true
set TRIAGERAG_TELEMETRY_EXPORTER=otlp_http
set TRIAGERAG_OTLP_ENDPOINT=http://localhost:4318/v1/traces
python -m uvicorn triagerag.api.app:app --host 127.0.0.1 --port 8000

# 3. View traces in Jaeger UI
# Open http://localhost:16686 in your browser
```

---

## 11. Automated Acceptance Test Gates

The OpenTelemetry subsystem is protected by three dedicated test suites spanning 28 automated test cases:

1. `tests/unit/test_telemetry.py` (13 tests):
   - Gate 1: Mandatory allowlist sanitizer & invalid type drops
   - Gate 5: Zero-dependency fallback (`_NoOpTracer` without opentelemetry installed)
   - Gate 7: Telemetry exception non-interference & genuine exception propagation
   - Gate 9: Loopback endpoint verification (rejection of cloud endpoints)
   - Gate 10: Fail-closed unknown node name mapping
   - Gate 11: Idempotent initialization & thread-safe lifecycle
   - Gate 12: W3C context injection & extraction

2. `tests/unit/test_workflow_telemetry.py` (7 tests):
   - Gate 2: Canonical paths (Paths A, B, C, D) emit exact 8 operational spans
   - Gate 3: Span parenting hierarchy (`workflow.execution` -> 8 `node.<stage>` spans)
   - Gate 6: Behavioral and clinical equivalence (tracing enabled vs disabled)
   - Gate 8: Concurrent multi-threaded execution trace isolation

3. `tests/integration/test_telemetry_api.py` (8 tests):
   - Gate 1: HTTP root span zero sensitive exception marker leakage
   - Gate 3: Full 3-tier API hierarchy (`http.request` -> `workflow.execution` -> nodes)
   - Gate 4: Fast HTTP rejection isolation (413/422 emit zero graph spans)
   - Gate 7: API non-interference during simulated tracer failure
   - Gate 12: Incoming W3C `traceparent` context inheritance and outgoing response headers

