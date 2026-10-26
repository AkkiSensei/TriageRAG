# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Phase:** Phase 7 (Eval Harness, Full Verification & Docs Complete)
- **Status:** All gates green (`gate-1` through `gate-7`). Repository fully built and runnable offline.

## Work Completed Across All 7 Gated Phases

1. **Phase 1: Scaffold & Architecture Lock (`gate-1`)**
   - Rules files (`AGENTS.md` and `.agent/rules/triagerag.md`) verbatim with Rules R1-R12.
   - Project configuration (`pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`).
   - Core docs (`docs/LIMITATIONS.md`, `DATA_PROVENANCE.md`, `MODEL_CARD.md`, `ARCHITECTURE.md`, ADRs 0001-0004).
   - Cross-platform task runner (`tools/tasks.py`) supporting `lint`, `typecheck`, `lint-imports`, `validate-data`, `test`, `eval`, `ui`, `verify`.

2. **Phase 2: Contracts, Loaders, Data Schemas, Seed Data & Fixtures (`gate-2`)**
   - Frozen Pydantic v2 schemas (`Provenance`, `Measured[T]`, `Age`, `Patient`, `Vitals`, `ExplicitDose`, `PlanDraft`, `EngineReport`).
   - Pure string-to-Decimal YAML loader (`DecimalSafeLoader`) with zero float conversion.
   - Seed clinical data: 8 formulary drugs, 12 rules, scoring tables, 14 aliases, acronyms, and side-chain cephalosporin grouping.
   - 6 original synthetic protocol documents with no numeric doses.
   - 41 mechanics test cases for fictional drugs in `tests/fixtures/mechanics/`.
   - Data validation and provenance reporting tools (`tools/validate_data.py`, `tools/provenance_report.py`, `tools/add_rule.py`).

3. **Phase 3: Engine, Scores, Dose Engine, Rule Engine & Golden Suite (`gate-3`)**
   - Pure functional `ClinicalRegistry` (immutable registry injection).
   - Four-state Verdict lattice (`BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR`).
   - Physiological early-warning score calculation with AVPU + `C` (new confusion).
   - Pure Decimal dose engine with neonate/paediatric/adult paths, weight caps, and 10x magnitude tripwires.
   - Pass 1 & Pass 2 rule engine checking `requires_fields`, absolute lookbacks, and withhold semantics.
   - 65/65 passed in shipped ruleset golden cases; 41/41 passed in mechanics suite; 6/6 passed in Hypothesis property suite.

4. **Phase 4: Synthetic Protocols & RAG (`gate-4`)**
   - Markdown protocol ingestion and decision-node chunking preserving IF-THEN integrity.
   - `ClinicalTokenizer` with acronym preservation and expansion.
   - Partitioned `BM25ClinicalIndex` with hard population isolation.
   - Structured query builder deriving flags strictly from vitals (forbidding `chief_complaint_untrusted`).
   - Score-based and population-based abstention evaluator.

5. **Phase 5: LLM, Verify, Orchestrator, Audit & Overrides (`gate-5`)**
   - Deterministic `FakeLLM` with 7 profiles (`COMPLIANT`, `INVENT_DRUG`, `PROSE_LEAK`, `INVALID_CITATION`, `IGNORE_BLOCK`, `OBEY_COMPLAINT`, `NAIVE_FREE_TEXT`) and optional `GeminiProvider`.
   - Verbatim span citation validator and lexical overlap scorer.
   - Drug scanner checking narrative text for forbidden drug tokens.
   - Master orchestrator `run_triage` coordinating Pass 1, retrieval, drafting, machine verification, and repair.
   - Cryptographic SHA-256 append-only JSONL audit chain with file locking and tamper detection.
   - Strict block on BLOCK overrides; HIGH alerts require logged justification.

6. **Phase 6: UI & CLI (`gate-6`)**
   - Typer CLI (`triagerag run|validate-data|eval|audit-verify`) with Rich tables and mandatory disclaimer.
   - Streamlit clinical UI with fixed top banner from `EngineReport`, no bare "CLEAR" wording, "UNSOURCED DRAFT" & "SYNTHETIC" badges, struck-through blocks, and 4 preloaded scenarios.
   - Integration tests with `streamlit.testing.v1.AppTest` passing cleanly.

7. **Phase 7: Full Evaluation Harness & Ablation (`gate-7`)**
   - Metamorphic suite (3/3 passed: brand/generic equivalence, list reordering invariance, equivalent units tripwire).
   - Adversarial prompt injection suite (9/9 passed: 100% byte-identical EngineReports under isolated and delimited modes; drug hijack neutralization).
   - Mutation testing runner (12/12 killed, 100.0% mutation score across critical BLOCK and HIGH rules).
   - Retrieval evaluation suite (32 benchmark pairs: 100.0% Recall@5, 0.896 MRR, 100.0% Abstain Accuracy).
   - Ablation evaluation suite (comparing Arms A, B, and C with mandatory FakeLLM caveat in `eval/reports/ablation.md`).

## Exact Commands to Resume / Verify

```bash
# 1. Activate environment
.\.venv\Scripts\Activate.ps1

# 2. Run full verification gates (ruff, mypy, import-linter, validate-data, provenance, pytest, golden, mechanics, metamorphic, adversarial)
python tools/tasks.py verify

# 3. Run all evaluation suites (golden, mechanics, metamorphic, adversarial, mutation, retrieval, ablation)
python tools/tasks.py eval all

# 4. Launch the Streamlit interactive UI
python tools/tasks.py ui

# 5. Run CLI triage execution
triagerag run data/golden/shipped_ruleset_cases.yaml 1
```
