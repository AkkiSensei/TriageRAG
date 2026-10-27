# TriageRAG — Debug Journal & Audit Log

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Baseline Ground Truth (Round 0 / Initial Audit)

### 1. Git & Deployment Failure Diagnosis
- **Failure Symptom:** CI deployment failed on `python tools/tasks.py eval` (Step: Run evaluation suites).
- **Exact Root Cause:** In `eval/run_mutation.py`, the import `from eval.run_golden import _build_patient_from_case` fails with `ModuleNotFoundError: No module named 'eval'` when executed via `python eval/run_mutation.py` because `eval/` is not a package installed in `site-packages` and the repository root was not guaranteed on `PYTHONPATH` during subprocess invocation.
- **Git State:** Tags `gate-1` through `gate-7` verified in commit history (`419ab13`).
- **Committed Runtime Artifacts:** `audit_log.jsonl` and `audit_log.jsonl.lock` are currently tracked in git index, violating isolation and dirtying working tree during test runs.

### 2. Initial Suite Baseline Counts vs HANDOFF Claims

| Suite | HANDOFF.md Claimed | Observed Clean Run | Status / Discrepancy |
|:---|:---:|:---:|:---:|
| **Ruff Linter & Formatter** | Clean | Clean (67 files) | MATCH |
| **Mypy Type Checking** | Clean | Clean (66 files, 0 errors) | MATCH |
| **Layer Isolation (import-linter)** | Intact (2 contracts) | Intact (2 contracts) | MATCH |
| **Data Validation** | 37 entities audited | 37 entities validated | MATCH |
| **Provenance Audit** | 37/37 unverified draft | 37/37 unverified draft | MATCH |
| **Pytest Suites (unit, integration, property, UI smoke)** | 44 passed | 44 passed | MATCH |
| **Shipped Golden Cases (`eval/run_golden.py`)** | 65 passed | 65 passed | MATCH |
| **Mechanics Suite (`eval/run_mechanics.py`)** | 41 passed | 41 passed | MATCH |
| **Metamorphic Suite (`eval/run_metamorphic.py`)** | 3 passed | 3 passed | MATCH |
| **Adversarial Suite (`eval/run_adversarial.py`)** | 9 passed | 9 passed | MATCH |
| **Mutation Testing (`eval/run_mutation.py`)** | 12/12 killed | **CRASHED** (ModuleNotFoundError: 'eval') | **BUG #1 FOUND** |
| **Retrieval Benchmarks (`eval/run_retrieval.py`)** | 32 pairs, 100% R@5, 0.896 MRR | 32 pairs, 100% R@5, 0.896 MRR | MATCH |
| **Ablation Study (`eval/run_ablation.py`)** | Generated `eval/reports/ablation.md` | Generated `eval/reports/ablation.md` | MATCH |

---

## Part A Bug Tracker & Remediation Rounds

### Bug 001: CI Deployment Crash on `eval/run_mutation.py`
- **Symptom:** `ModuleNotFoundError: No module named 'eval'` when `python eval/run_mutation.py` is invoked.
- **Root Cause:** When running `eval/run_mutation.py` directly, `sys.path[0]` is `eval/`. The module attempt `from eval.run_golden import ...` fails. Furthermore, `tools/tasks.py` did not explicitly set `PYTHONPATH` in the execution environment.
- **Fix:** Update `tools/tasks.py` to always pass `PYTHONPATH=REPO_ROOT` in subprocess environments, and provide fallback import `from run_golden import _build_patient_from_case` in `eval/run_mutation.py`.
- **Regression Test:** `python tools/tasks.py eval all`.

### Bug 002: Committed Runtime Audit Artifacts & Missing Isolation
- **Symptom:** `audit_log.jsonl` and lock files appeared in `git status` after running orchestrator tests.
- **Root Cause:** Runtime files were committed to git root in Gate 6. Additionally, `get_audit_path()` was hardcoded to `REPO_ROOT / "audit_log.jsonl"`, preventing tests from redirecting audit trails to ephemeral directories.
- **Fix:** Untracked `audit_log.jsonl*` from git index. Updated `.gitignore` to ignore `var/` and `audit_log.jsonl*`. Implemented `get_audit_path()` in `src/triagerag/config.py` respecting `TRIAGERAG_AUDIT_PATH` env var.
- **Regression Test:** `tests/integration/test_audit_concurrency.py`.

### Bug 003: LLM Repair Loop Missing from Orchestrator
- **Symptom:** Specification Section 9 / Orchestrator design documented a bounded 1-attempt repair loop, but `orchestrator.py` simply struck through failed steps without attempting repair.
- **Root Cause:** Incomplete handoff implementation between Gate 4 and Gate 5.
- **Fix:** Implemented `src/triagerag/llm/repair.py` providing `classify_violation`, `sanitize_repair_violations`, and `attempt_plan_repair`. Wired repair attempt into `src/triagerag/orchestrator.py` lines 193–232. Bounded to exactly 1 attempt; strips all untrusted text to prevent prompt injection.
- **Regression Test:** `tests/unit/test_repair.py` (7 tests verifying sanitization, successful citation correction, and strict preservation of BLOCKED contraindications).

### Bug 004: Lack of Injected Clock & Frozen Orchestrator Config (Rule R12)
- **Symptom:** Orchestrator lacked dependency injection for system time and configuration, hindering deterministic testing and mutation testing.
- **Root Cause:** `run_triage` constructed default options directly without an injected `Clock` protocol.
- **Fix:** Created frozen `OrchestratorConfig` and `Clock` protocol (`SystemClock`, `FixedClock`) in `src/triagerag/contracts/schemas.py`. Injected `clock` and `config` parameters into `run_triage` in `orchestrator.py`.
- **Regression Test:** `tests/unit/test_r_rules_conformance.py` (AST visitor ensuring no uninjected `datetime.now()` in engine).

### Bug 005: Cross-Platform Line Ending Drift
- **Symptom:** Inconsistent line endings (`CRLF` vs `LF`) across developer machines.
- **Root Cause:** No `.gitattributes` file in repository.
- **Fix:** Added `.gitattributes` enforcing `* text=auto eol=lf`.

### Bug 006: Incomplete Mutation Testing Suite (Rule R10)
- **Symptom:** Mutation testing only contained 12 rule-dropping mutants and 0 code-level mutants, falling short of verifying the full execution semantics of the clinical engine.
- **Root Cause:** Initial implementation stubbed code mutations.
- **Fix:** Expanded `eval/run_mutation.py` to synthesize and evaluate 28 code-level mutants covering verdict lattice precedence, `requires_fields` interlocks, lookback windows, withhold exemptions, citation groundings, drug-scan tokens, population filters, BLOCK override guards, dose arithmetic, and cryptographic audit integrity.
- **Outcome:** **40/40 mutants killed (100% combined kill score: 12/12 rule mutants, 28/28 code mutants)**.

### Bug 007: Rule R7 `unsafe_allow_html=True` in Streamlit UI
- **Symptom:** AST scan in `tests/unit/test_r_rules_conformance.py` flagged `unsafe_allow_html=True` in `src/triagerag/ui/components.py:85`.
- **Root Cause:** Top banner rendered an alert badge using raw HTML div styling with `unsafe_allow_html=True`, violating Rule R7.
- **Fix:** Replaced HTML injection with native Streamlit Markdown badges (`:red[...]`, `:orange[...]`, `:blue[...]`) and native Streamlit metric columns.
- **Regression Test:** `test_r7_no_unsafe_allow_html_in_ui` in `tests/unit/test_r_rules_conformance.py`.

### Bug 008: Premature `NEEDS_SOURCE` Skip in Rule Engine (Rule R2)
- **Symptom:** Every patient in the hospital without metoprolol was receiving an `UNVERIFIED` verdict with a `SkippedCheck` for `VITALS_METOPROLOL_BRADYCARDIA_NULL_THRESHOLD`.
- **Root Cause:** In `_evaluate_single_rule`, `rule.status == RuleStatus.NEEDS_SOURCE` was evaluated before checking if the rule was clinically applicable to the patient's active medications or proposed plan. Because the rule had `NEEDS_SOURCE`, it unconditionally emitted a skip for unrelated patients.
- **Fix:** Moved rule applicability gating (checking whether drug or class is in `active_drugs` / `active_classes`) *before* checking vitals thresholds and `NEEDS_SOURCE`. Rules only evaluate vitals/sources if the drug is clinically relevant to that patient.
- **Regression Test:** `tests/integration/test_orchestrator.py` (checked-clear scenario returns `CHECKED_CLEAR`).

### Bug 009: Pediatric Weight-Based Dose Math Conversion Error (Rule R8)
- **Symptom:** Dose verification for weight-based pediatric doses (e.g., `mg/kg`) crashed during Pint unit conversion with dimensionality errors when comparing against absolute mass ceilings (`mg`).
- **Root Cause:** `verify_dose` passed `requested_dose` directly to `convert_dose` without first multiplying by `patient.weight_kg`.
- **Fix:** In `src/triagerag/engine/dose_engine.py`, added weight scaling: when `dose_unit` is `mg_per_kg` or `mcg_per_kg`, the dose is scaled by `patient.weight_kg.value` to compute total administered mass in `mg` prior to ceiling comparison.
- **Regression Test:** `tests/unit/test_contracts.py` and `tests/unit/test_engine.py`.

### Bug 010: Preloaded HIGH Scenario Allergy Misconfiguration
- **Symptom:** Preloaded `HIGH` scenario failed to trigger the expected high-risk alert for `ALLERGY_PENICILLIN_CEPH_R1_DISSIMILAR`.
- **Root Cause:** Rule YAML required `reaction_types: ["anaphylaxis_ige"]`, but the test scenario specified `reaction_type="mild_rash"`.
- **Fix:** Updated the scenario in `src/triagerag/contracts/scenarios.py` to specify `reaction_type="anaphylaxis_ige"` and aligned ceftriaxone formulary limits in `data/formulary/ceftriaxone.yaml`.
- **Regression Test:** `tests/integration/test_orchestrator.py::test_orchestrator_scenario_high_with_override`.

---

## Final Verification Summary

- **Pytest Suite:** 75 passed (0 failed, 0 skipped) in ~9.7s.
- **Linters:** Ruff check clean, Ruff format clean, Mypy clean (74 source files, 0 errors).
- **Import Layer Isolation:** Clean (0 contract violations).
- **Golden Suite:** 65/65 passed (100%).
- **Mechanics Suite:** 41/41 passed (100%).
- **Metamorphic Suite:** 3/3 passed (100%).
- **Adversarial Suite:** 9/9 passed (100% byte-identical EngineReports & prompt isolation).
- **Mutation Suite:** 40/40 killed (100% combined: 12/12 rule mutants, 28/28 code mutants).
- **Retrieval Suite:** 32 benchmark pairs, Recall@5 100%, MRR 0.896, Abstain accuracy 100%.
- **Provenance Audit:** 37/37 entities audited, 37 unverified draft, 0 false claims.
