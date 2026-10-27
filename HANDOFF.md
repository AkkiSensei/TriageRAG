# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** Part A Iterative Debugging & Hardening Complete (`debug-complete`). Transitioning to Part B (React Frontend Console).
- **Verification:** All gates green (`gate-1` through `gate-7` + `debug-complete`). 75/75 pytest tests green, 40/40 mutants killed (100%), 0 lint/mypy/import-linter errors.

## Key Updates in Part A (Debugging & Hardening)

1. **Bug Resolution & Clinical Engine Hardening (see `docs/DEBUG_LOG.md`):**
   - **CI & Deployment:** Fixed `ModuleNotFoundError: 'eval'` in `eval/run_mutation.py` by ensuring `PYTHONPATH` propagation in `tools/tasks.py`.
   - **Audit Trail Isolation:** Removed committed `audit_log.jsonl*` runtime artifacts; added configurable `get_audit_path()` via `TRIAGERAG_AUDIT_PATH` env var.
   - **LLM Repair Loop:** Implemented bounded 1-attempt repair loop in `src/triagerag/llm/repair.py` (`classify_violation`, `sanitize_repair_violations`, `attempt_plan_repair`) wired into `orchestrator.py` with full untrusted text stripping.
   - **Determinism & Pure Clocks (Rule R12):** Created frozen `OrchestratorConfig` and `Clock` protocol (`SystemClock`, `FixedClock`) injected into `run_triage`.
   - **Mutation Testing (Rule R10):** Expanded `eval/run_mutation.py` from 12 rule mutants to 40 total mutants (12 rule + 28 code-level mutants). **100% kill score (40/40)** across verdict lattice, lookbacks, withhold exemptions, citation groundings, drug-scan tokens, population filters, BLOCK override guards, dose math, and cryptographic audit.
   - **HTML Injection Elimination (Rule R7):** Removed all `unsafe_allow_html=True` calls from Streamlit components; replaced with native Streamlit markdown badges.
   - **Rule Applicability Gating (Rule R2):** Evaluates clinical applicability before `NEEDS_SOURCE` checks to prevent false `UNVERIFIED` skips for patients not receiving the drug/class.
   - **Weight-Based Pediatric Math (Rule R8):** Added automatic scaling by `patient.weight_kg` for weight-based units (`mg_per_kg`, `mcg_per_kg`) before formulary ceiling checks.
   - **HIGH Scenario Allergy Reaction:** Updated scenario to `anaphylaxis_ige` and aligned ceftriaxone formulary limits.

2. **Expanded Test Suite (75 Tests Total):**
   - `tests/unit/test_r_rules_conformance.py`: AST scans for no floats in dose engine, pure engine isolation (no network, no `datetime.now`), no `unsafe_allow_html`, no bare "CLEAR", and functional BLOCK override guard.
   - `tests/unit/test_serialization.py`: Exact Decimal string preservation across JSON round-trips.
   - `tests/integration/test_audit_concurrency.py`: Multiprocessing concurrent writes under file lock and cryptographic tamper detection (modify, delete, reorder).
   - `tests/unit/test_repair.py`: Sanitization and repair loop behavior.
   - `tests/unit/test_retrieval_edge_cases.py`: Empty index, missing population abstention, case/punctuation variants.
   - `tests/unit/test_verifier_edge_cases.py`: Normal English word substring isolation, typo leak detection, whitespace/unicode normalization.
   - `tests/property/test_pipeline_fuzz.py`: Hypothesis fuzzing verifying pipeline stability, fail-closed invariant, and complaint isolation.

## Verification Metrics

| Suite | Metric | Result |
|:---|:---:|:---:|
| **Linters & Formatters** | Ruff check & format | Clean (74 files) |
| **Type Checking** | Mypy strict mode | Clean (74 files, 0 errors) |
| **Layer Isolation** | Import-linter | Clean (2 contracts intact) |
| **Data Validation** | `tools/validate_data.py` | 37 entities valid |
| **Provenance Audit** | `tools/provenance_report.py` | 37/37 unverified draft |
| **Pytest Suite** | Unit, integration, property, UI smoke | **75 passed** |
| **Shipped Golden Cases** | `eval/run_golden.py` | 65/65 passed (100%) |
| **Mechanics Suite** | `eval/run_mechanics.py` | 41/41 passed (100%) |
| **Metamorphic Suite** | `eval/run_metamorphic.py` | 3/3 passed (100%) |
| **Adversarial Suite** | `eval/run_adversarial.py` | 9/9 passed (100%) |
| **Mutation Testing** | `eval/run_mutation.py` | **40/40 killed (100%)** |
| **Retrieval Benchmarks** | `eval/run_retrieval.py` | 32 pairs, 100% R@5, 0.896 MRR |
| **Ablation Study** | `eval/run_ablation.py` | Generated `eval/reports/ablation.md` |

## Exact Commands to Resume / Verify

```bash
# 1. Run full verification gates
python tools/tasks.py verify

# 2. Run all evaluation suites
python tools/tasks.py eval all

# 3. Launch Streamlit UI
python tools/tasks.py ui

# 4. Run CLI triage execution
python -m triagerag run data/golden/shipped_ruleset_cases.yaml 1
```
