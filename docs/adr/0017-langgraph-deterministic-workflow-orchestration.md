# ADR 0017: Deterministic Multi-Stage Workflow Orchestration using LangGraph

## Status
Accepted

## Context
TriageRAG's decision support pipeline requires rigorous, deterministic orchestration across seven clinical stages: normalisation, intake safety checks, protocol retrieval, extractive plan drafting, machine verification with dose calculations, cryptographic audit logging, and explanation synthesis.

Previously, these stages were coordinated through a linear procedural function (`run_triage_linear`). While clean and decoupled, this implementation lacked formal graph-based state transitions, inspectable step-by-step conditional routing, and standard workflow visualization tooling expected of modern agentic RAG architectures.

To satisfy research and production requirements, TriageRAG required:
1. Integration of **LangGraph (`langgraph>=0.2.0`)** as the core workflow orchestration framework.
2. A strongly-typed shared state graph (`TriageGraphState`) preserving all existing clinical Pydantic schemas.
3. Explicit conditional routing for safety-critical clinical boundaries:
   - Fail-closed protocol abstention (Rule R2): routing directly to an abstention fallback node when retrieval confidence or clinical predicates fail, safely bypassing LLM plan generation.
   - Verdict disposition lattice (Rule R11): deterministic branching to dedicated disposition seals (`block_seal` for inviolable BLOCK alerts, `unverified_seal` for missing vital signs or unconfirmed histories, `verified_seal` for approved clear plans).
4. Pure offline, deterministic execution with zero external LLM or vector DB network calls (strictly adhering to Rule R1 "Code decides; the LLM explains" and HD-10 / HD-14 restrictions).
5. 100% decision, mathematical, and cryptographic hash equivalence with the reference linear pipeline.
6. Real FastAPI production path integration at `POST /api/triage` and runtime workflow introspection at `GET /api/triage/workflow`.

## Decision

1. **State Isolation & Typed Graph State:**
   - Implemented `TriageGraphState(TypedDict)` in `src/triagerag/orchestration/langgraph_workflow.py`.
   - Domain models (`Patient`, `ClinicalRegistry`, `RetrievalReport`, `EngineReport`, `TriageResponse`, `ScoreResult`) are reused directly without loss of type safety.
   - Each graph invocation executes on an isolated state instance with read-only clinical registry access. Multi-thread concurrency tests across 12 alternating worker threads confirm zero cross-request data contamination.

2. **11 Application Processing Nodes (13 Total Keys):**
   - The workflow contains 11 processing nodes plus 2 boundary pseudo-nodes (`__start__`, `__end__`):
     1. `normalise`: Patient physiological validation, unit standardization, and EWS scoring.
     2. `intake_safety_checks`: Pass 1 deterministic intake, allergy, DDI, and formulary filters.
     3. `retrieve`: Protocol candidate chunk retrieval via BM25 with population filtering (ECE remains observational under HD-12).
     4. `draft_plan`: Extractive plan drafting using the configured `FakeLLM` mock provider.
     5. `abstain_fallback`: Fail-closed abstention path that sets `llm_fallback_mode=True` without calling the generator.
     6. `verify`: Pass 2 machine verification, dose limit checks, and verdict lattice evaluation.
     7. `block_seal`: Dedicated non-overridable BLOCK path seal enforcing Rule R11.
     8. `unverified_seal`: Dedicated fail-closed UNVERIFIED path seal enforcing Rule R2.
     9. `verified_seal`: Dedicated verified disposition seal for `CHECKED_CLEAR` and `CHECKED_ALERTS`.
     10. `audit`: In-memory SHA-256 state hashing and sequential hash chaining for run integrity.
     11. `explain`: Final `EngineReport` compilation and `TriageResponse` synthesis.

3. **Explicit Conditional Routing:**
   - **Conditional Edge 1 (`route_after_retrieve`):** Evaluates `retrieval_report.abstained` or empty chunks. If true, routes to `abstain_fallback`; if candidate chunks exist, proceeds to `draft_plan`.
   - **Conditional Edge 2 (`route_after_verify`):** Inspects `overall_verdict`.
     - `BLOCKED` $\rightarrow$ `block_seal` (inviolable BLOCK interlock; overrides strictly rejected).
     - `CHECKED_CLEAR` / `CHECKED_ALERTS` $\rightarrow$ `verified_seal`.
     - Any missing or unverified state $\rightarrow$ `unverified_seal` (Rule R2 fail-closed boundary).
   - All seal paths re-converge deterministically at `audit` and `explain` before reaching `END`.

4. **Production Routing in FastAPI and Orchestrator:**
   - `run_triage(...)` in `src/triagerag/orchestrator.py` delegates directly to `run_triage_graph(...)`, making LangGraph the primary execution path.
   - `run_triage_linear` and `run_triage_legacy` are preserved verbatim as reference baselines for regression and equivalence verification.
   - `POST /api/triage` invokes `run_triage(...)`, executing the compiled StateGraph.
   - `GET /api/triage/workflow` exposes compiled node inventories and live Mermaid diagram syntax for runtime observability.

5. **Layered Architectural Isolation (import-linter):**
   - Core clinical modules (`triagerag.contracts`, `triagerag.normalize`, `triagerag.engine`) remain pure and strictly forbid importing `langgraph` or `langchain`.
   - LangGraph dependencies are restricted exclusively to `triagerag.orchestration` and the service layer.

## Consequences

- **Full Execution Observability:** Every graph run records non-sensitive execution metrics (node sequence, completion status, duration in milliseconds, routing branches chosen) with zero patient PII.
- **Strict Equivalence:** 100% mathematical and clinical verdict identity is maintained across all synthetic test scenarios (`CLEAN`, `BLOCK`, `UNVERIFIED`, `HIGH`).
- **Empirical Execution Overhead:** Measured across 200 benchmark iterations: linear baseline mean = 2.18 ms (p95 = 3.61 ms); LangGraph compiled pipeline mean = 5.35 ms (p95 = 8.60 ms); framework state-dict coordination overhead = ~3.17 ms mean (comfortably within clinical emergency limits).
- **Deterministic Offline Guarantees:** No external network requests, API keys, or cloud dependencies are introduced.
