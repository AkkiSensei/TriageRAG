# TriageRAG Backend Directory Map

> **Clinical Research Prototype Disclaimer**  
> Synthetic data only. Not a medical device. Not for clinical use.

This document provides an exhaustive, authoritative architectural mapping of the `src/triagerag` backend codebase. It details the purpose, safety invariants, public contracts, and corresponding test coverage for every module.

---

## 1. High-Level Architecture & Layer Dependency Hierarchy

TriageRAG enforces a strict unidirectional dependency graph using `import-linter`. Lower layers have zero knowledge of higher layers. Pure engines never import FastAPI, LangGraph, or I/O frameworks.

```
       [ Client / Browser / Frontend UI ]
                       │
                       ▼
         [ Layer 7: API Layer (src/triagerag/api) ]
                       │
                       ▼
   [ Layer 6: Orchestration Layer (src/triagerag/orchestration) ]
            (LangGraph StateGraph, Orchestrator Pipelines)
                       │
       ┌───────────────┼───────────────┬────────────────┐
       ▼               ▼               ▼                ▼
[ Layer 5: Verify ] [ Layer 4: RAG ] [ Layer 3: Engine ] [ Layer 2: Audit ]
(Plan Verifier)    (Lexical BM25,    (Pure Rules, Dose,  (Cryptographic
                    Q&A, Cues)        Scores, Verdict)    SHA-256 Chain)
       │               │               │                │
       └───────────────┴───────┬───────┴────────────────┘
                               ▼
            [ Layer 1: Normalization & Sanitization ]
                   (src/triagerag/normalize)
                               ▼
               [ Layer 0: Contracts & Schemas ]
                   (src/triagerag/contracts)
```

---

## 2. Directory & Module Inventory

### 2.1 Layer 0: Contracts (`src/triagerag/contracts/`)
Defines the immutable domain model, type schemas, enums, and clinical boundaries. Has zero dependencies on any other package in `triagerag`.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for contracts layer. | N/A | `tests/unit/test_contracts.py` |
| `enums.py` | Strict string enums for triage verdicts, alert severity, score bands, consciousness, routes, and rule status. | `Verdict`, `Severity`, `ScoreBand`, `StepStatus`, `Consciousness`, `Route` | `tests/unit/test_contracts.py` |
| `schemas.py` | Pydantic v2 schemas for patient vitals (`Measured[T]`), clinical alerts, EWS score results, plan drafts, verified steps, and the top-level `TriageResponse`. | `Patient`, `Vitals`, `Measured`, `Alert`, `TriageResponse`, `EngineReport` | `tests/unit/test_contracts.py`, `tests/unit/test_patient_data_propagation.py` |
| `data_schemas.py` | Pydantic models for offline YAML clinical data files (formulary entries, acronyms, synonyms, score tables). | `FormularyDrug`, `DoseLimit`, `ConcentrationItem` | `tests/unit/test_contracts.py` |
| `rules_schema.py` | Clinical rule schema definition with mandatory `Provenance` metadata tracking. | `ClinicalRule`, `Provenance`, `RuleCondition` | `tests/unit/test_aub_phase6_schema_v2.py` |
| `scenarios.py` | Test scenario structures for synthetic golden patient profiles. | `ScenarioCase`, `ScenarioSuite` | `tests/unit/test_serialization.py` |
| `wording.py` | Approved clinician-facing plain language dictionaries for triage verdicts. | `get_verdict_entry`, `VERDICT_EXPLANATIONS` | `tests/unit/test_aub_phase1_wording.py` |

---

### 2.2 Layer 1: Normalization (`src/triagerag/normalize/`)
Sanitizes raw patient intake data, resolves pharmaceutical brand/salt aliases, and executes exact Decimal unit conversions.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for normalization layer. | N/A | `tests/unit/test_engine.py` |
| `aliases.py` | Thread-safe alias lookup resolving trade names and informal synonyms to canonical formulary drug IDs. | `AliasResolver`, `resolve_drug_alias` | `tests/unit/test_aub_phase6_classes_and_fdc.py` |
| `clause_parser.py` | Extracts explicit condition-action pairs (`IF ... THEN ...`) from clinical guidelines without regex drift. | `parse_clinical_clauses`, `ParsedClause` | `tests/unit/test_fg1_grounding.py` |
| `sanitizer.py` | Defense-in-depth string sanitizer and untrusted text isolator. Prevents HTML injection (Rule R7). | `sanitize_text`, `strip_html` | `tests/unit/test_frontend_safety_boundary.py` |
| `units.py` | Exact Decimal clinical math converter with magnitude tripwires (10x/1000x guardrails). | `convert_dose`, `check_magnitude_tripwire` | `tests/unit/test_aub_phase6_dose_engine.py` |
| `validators.py` | Normalizes incoming patient payloads into validated `Patient` models, calculating age categories and normalizing missing vitals. | `normalize_patient`, `validate_vital_ranges` | `tests/unit/test_fg2_clinical_inputs.py` |
| `yaml_loader.py` | Custom PyYAML loader that parses all floating-point representations directly into `Decimal(str(...))` (Rule R8). | `DecimalSafeLoader`, `load_yaml_decimal` | `tests/unit/test_aub_phase2_scale_integrity.py` |

---

### 2.3 Layer 2: Core Engine (`src/triagerag/engine/`)
Pure, deterministic clinical decision engine. Zero external network calls, zero stochastic behaviors, zero mutable global state.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for engine layer. | N/A | `tests/unit/test_engine.py` |
| `registry.py` | Immutable in-memory registry holding validated rules, formulary items, scoring tables, and coverage gap declarations. | `ClinicalRegistry`, `load_registry` | `tests/unit/test_engine.py`, `tests/unit/test_aub_phase6_candidate_rules.py` |
| `rule_engine.py` | Two-pass deterministic rule evaluator: Pass 1 (intake contraindications, allergies, DDIs) and Pass 2 (proposed intervention verification). | `evaluate_baseline`, `evaluate_plan` | `tests/unit/test_engine.py`, `tests/unit/test_fail_closed_checks.py` |
| `dose_engine.py` | Decimal clinical dosage ceiling verifier enforcing per-kg, fixed, and cumulative limits with tripwires. | `verify_dose`, `calculate_administration_volume` | `tests/unit/test_aub_phase6_dose_engine.py` |
| `scores.py` | Deterministic Early Warning Score (NEWS2/PEWS) calculation mapping physiological vitals to alert bands. | `calculate_early_warning_score` | `tests/unit/test_aub_phase2_scoring.py` |
| `verdict.py` | Pure verdict lattice resolving overall case disposition (`BLOCKED`, `UNVERIFIED`, `CHECKED_ALERTS`, `CHECKED_CLEAR`). | `resolve_verdict_with_reason` | `tests/unit/test_aub_phase1_verdict.py` |

---

### 2.4 Layer 3: Retrieval-Augmented Generation (`src/triagerag/rag/`)
Offline, synthetic protocol retrieval, indexing, chunking, and extractive evidence grounding.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for RAG layer. | N/A | `tests/unit/test_rag.py` |
| `abstain.py` | Calibrated abstention evaluator. Triggers fail-closed abstention when queries have low overlap, high entropy, or missing population. | `evaluate_retrieval_abstention`, `RetrievalConfig` | `tests/unit/test_aub_phase1_abstention.py` |
| `alert_why.py` | Structured explanation generator for clinical alerts, distinguishing confirmed patient facts from unknown vitals and explaining BLOCK rationale. | `explain_alert`, `AlertWhyExplanation` | `tests/unit/test_aub_phase7_why_and_ask_corpus.py` |
| `ask_corpus.py` | Extractive Q&A engine over approved synthetic protocols with stop-word filtering, lexical validation, and fail-closed out-of-domain abstention. | `ask_the_corpus`, `CorpusAskResponse` | `tests/unit/test_aub_phase7_why_and_ask_corpus.py` |
| `chunking.py` | Hierarchical chunker splitting Markdown protocols into document parents and atomic decision child nodes (`IF...THEN`). | `chunk_markdown_protocol`, `ProtocolChunk` | `tests/unit/test_aub_phase3_contextual_chunking.py` |
| `cues.py` | Evaluates clinical cue mappings from data/retrieval/cues.yaml against patient state. | `evaluate_clinical_cues` | `tests/unit/test_aub_phase2_cues.py` |
| `diagnostics.py` | Diagnostic inspector reporting retrieval pipeline stages, token overlap, and BM25 score distributions. | `RetrievalDiagnosticReport` | `tests/unit/test_aub_phase7_diagnostics_and_mmr.py` |
| `evidence.py` | Constructs structured clinical evidence packages for machine verification and clinician display. | `assemble_evidence_report` | `tests/unit/test_fg1_grounding.py` |
| `hybrid.py` | Hybrid lexical retriever combining BM25 and character n-gram backends. | `HybridRetriever`, `build_retriever_backend` | `tests/unit/test_rag_wp7_hybrid.py` |
| `index.py` | In-memory protocol search index with non-negative IDF, acronym expansion, morphology, and parent deduplication. | `ProtocolIndex`, `ClinicalTokenizer` | `tests/unit/test_rag_wp4_index.py` |
| `ingest.py` | Loads and verifies synthetic Markdown protocols from disk, computing cryptographic SHA-256 corpus hashes. | `ingest_protocol_corpus`, `compute_corpus_hash` | `tests/unit/test_rag_wp1_ingestion.py` |
| `node_predicates.py` | Evaluates protocol decision node preconditions (e.g., hemodynamic instability, oxygen saturation thresholds). | `evaluate_node_predicate` | `tests/unit/test_aub_phase2_node_predicates.py` |
| `predicates.py` | Evaluates synthetic clinical predicates over patient vitals, medications, and age. | `evaluate_predicate` | `tests/unit/test_aub_phase2_predicates.py` |
| `query_expansion.py` | Expands clinical queries with synonyms, morphology stems, and acronym equivalents without semantic drift. | `expand_clinical_query` | `tests/unit/test_aub_phase7_query_expansion.py` |
| `retrieve.py` | High-level protocol chunk retrieval coordinator applying hard population and syndrome filters. | `retrieve_protocol_chunks`, `derive_vitals_flags` | `tests/unit/test_rag_wp3_query_and_flags.py` |
| `scoring.py` | BM25 scoring functions with Robertson-Spärck Jones non-negative IDF formulation. | `bm25_score_chunk` | `tests/unit/test_aub_phase4_metrics.py` |
| `service.py` | Unified thread-safe retrieval service facade managing indices and diagnostic explanation traces. | `RetrievalService` | `tests/unit/test_rag_wp8_service_and_audit.py` |

---

### 2.5 Layer 4: LLM Interface (`src/triagerag/llm/`)
Deterministic LLM abstraction layer. Governed strictly by Rule R1 ("Code decides; LLM explains"). Zero live external API calls in default offline mode.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for LLM layer. | N/A | `tests/unit/test_aub_phase5_fake_llm.py` |
| `cassette.py` | Deterministic cassette player for golden test replay and regression verification. | `CassettePlayer`, `record_cassette` | `tests/unit/test_aub_phase7_provider_cassettes.py` |
| `draft.py` | Safe plan drafting orchestrator extracting proposed care steps from retrieved protocol evidence. | `draft_plan_safe` | `tests/unit/test_aub_phase5_fake_llm.py` |
| `fake.py` | Deterministic offline mock LLM emitting pre-computed valid and invalid plans for regression testing. | `FakeLLM`, `FakeLLMProfile` | `tests/unit/test_aub_phase5_fake_llm.py` |
| `prompts.py` | Immutable prompt templates enforcing strict JSON output schemas and narrative isolation (Rule R7). | `build_drafting_prompt` | `tests/unit/test_explainability_and_intake_hardening.py` |
| `provider.py` | Abstract protocol defining the LLM provider contract. | `LLMProvider` | `tests/unit/test_aub_phase5_fake_llm.py` |
| `repair.py` | Machine verification feedback loop attempting targeted repairs on rejected draft steps. | `attempt_plan_repair`, `sanitize_repair_violations` | `tests/unit/test_repair.py` |

---

### 2.6 Layer 5: Plan Verification (`src/triagerag/verify/`)
Deterministic machine verifier checking proposed care steps against clinical safety rules, formulary limits, and protocol citations.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for verify layer. | N/A | `tests/unit/test_verifier_edge_cases.py` |
| `applicability.py` | Verifies whether a cited protocol decision node applies to the patient's current physiological state. | `verify_node_applicability`, `ApplicabilityStatus` | `tests/unit/test_aub_phase5_applicability.py` |
| `citations.py` | Validates verbatim chunk citations, lexical overlap thresholds ($\ge 0.35$), and child-node specificity. | `verify_citation`, `verify_step_support` | `tests/unit/test_aub_phase1_citations.py` |
| `drug_scan.py` | Scans free-text narrative instructions for unauthorized or unlisted drug mentions (anti-leak protection). | `scan_narrative_for_drug_leaks` | `tests/unit/test_route_and_verification_hardening.py` |
| `plan_verifier.py` | Primary verification coordinator executing Pass 2 rule checks, route validation, dose checks, and status lattice mapping. | `verify_plan` | `tests/unit/test_verifier_edge_cases.py` |
| `qualifiers.py` | Verifies clinical condition qualifiers (e.g., "if systolic BP < 90") attached to care steps. | `verify_step_qualifiers` | `tests/unit/test_aub_phase5_qualifiers.py` |

---

### 2.7 Layer 6: Orchestration (`src/triagerag/orchestration/` and `src/triagerag/orchestrator.py`)
Deterministic stateful execution coordinator implementing the LangGraph StateGraph workflow (ADR 0017).

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `langgraph_workflow.py` | LangGraph `StateGraph` implementation featuring 11 deterministic processing nodes, conditional edges, and seal invariants. | `build_triage_graph`, `compile_triage_graph`, `run_triage_graph`, `TriageGraphState` | `tests/unit/test_langgraph_orchestration.py`, `tests/unit/test_patient_data_propagation.py` |
| `orchestrator.py` | Pure functional stage decomposition (Stages 1-7) serving as node implementations and linear reference benchmark. | `run_triage`, `run_triage_linear`, `stage_normalise`, `stage_intake_checks`, `stage_retrieve`, `stage_draft`, `stage_verify`, `stage_audit`, `stage_explain` | `tests/unit/test_aub_phase1_orchestrator_pipeline.py`, `tests/unit/test_patient_data_propagation.py` |

---

### 2.8 Layer 7: Audit Logging (`src/triagerag/audit/`)
Cryptographic tamper-evident linear SHA-256 hash chaining with cross-platform advisory file locking and head-hash anchoring.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `__init__.py` | Package marker for audit layer. | N/A | `tests/unit/test_audit.py` |
| `chain.py` | Implements append-only SHA-256 hash chaining, canonical JSON serialization, Windows `msvcrt` and POSIX `fcntl` locking, and head-hash verification. | `append_audit_entry`, `verify_audit_chain`, `file_lock`, `compute_canonical_hash` | `tests/unit/test_audit.py`, `tests/unit/test_audit_regressions.py` |

---

### 2.9 Layer 8: API & Web Service (`src/triagerag/api/`)
Stateless FastAPI presentation adapter exposing REST endpoints, enforcing rate limits, request size limits, and security headers.

| File | Purpose & Responsibilities | Key Endpoints | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `app.py` | FastAPI application factory, CORS setup, security middleware, 422/500 handlers, and SPA static hosting. | Root `/`, `/api`, static `/assets` | `tests/unit/test_explainability_and_intake_hardening.py` |
| `schemas.py` | API request/response Data Transfer Objects (DTOs). | `TriageApiRequest`, `ExplainApiRequest`, `AuditEntryDto` | `tests/unit/test_serialization.py` |
| `security.py` | Sliding window rate limiter, security headers middleware, and payload guards. | `SlidingWindowRateLimiter`, `create_security_middleware` | `tests/unit/test_aub_phase7_security.py` |
| `routes/triage.py` | Triage execution, workflow graph metadata, alert explanation, and retrieval inspector endpoints. | `POST /api/triage`, `GET /api/triage/workflow`, `POST /api/triage/explain`, `POST /api/triage/alert-why` | `tests/unit/test_patient_data_propagation.py`, `tests/unit/test_langgraph_orchestration.py` |
| `routes/corpus.py` | Extractive protocol Q&A endpoint. | `POST /api/corpus/ask` | `tests/unit/test_aub_phase7_why_and_ask_corpus.py` |
| `routes/audit.py` | Audit entry query and cryptographic integrity verification endpoints. | `GET /api/audit/entries`, `POST /api/audit/verify` | `tests/unit/test_audit.py` |
| `routes/protocols.py` | Protocol inspection and chunk listing endpoints. | `GET /api/protocols`, `GET /api/protocols/{doc_id}` | `tests/unit/test_rag_wp1_ingestion.py` |
| `routes/registry.py` | Shipped clinical ruleset and formulary introspection endpoints. | `GET /api/registry/rules`, `GET /api/registry/formulary` | `tests/unit/test_engine.py` |
| `routes/scenarios.py` | Synthetic patient scenario library endpoints. | `GET /api/scenarios`, `GET /api/scenarios/{id}` | `tests/unit/test_serialization.py` |
| `routes/eval.py` | Golden test evaluation runner endpoint. | `POST /api/eval/run` | `tests/unit/test_aub_phase4_gates.py` |
| `routes/health.py` | Healthcheck and readiness probe endpoints. | `GET /health`, `GET /ready` | `tests/unit/test_explainability_and_intake_hardening.py` |

---

### 2.10 Root & Utilities (`src/triagerag/`)
Global configuration and CLI entry points.

| File | Purpose & Responsibilities | Key Symbols / Classes | Corresponding Test File |
| :--- | :--- | :--- | :--- |
| `config.py` | Zero-dependency environment variable and path discovery (`TRIAGERAG_DATA_DIR`, `TRIAGERAG_AUDIT_PATH`). | `get_data_dir`, `get_audit_path`, `get_retrieval_backend` | `tests/unit/test_contracts.py` |
| `cli.py` | Rich CLI application for command-line triage, verification, and audit inspection. | `app` (Typer CLI) | `tests/unit/test_engine.py` |
