# TriageRAG — Forensic Engineering & Hardening Audit (Phases 0–5)

**Audit Date:** 2026-11-01  
**Controlling Specification:** `AUB.md`  
**Starting Commit:** `e674ef4` (Phase 5 complete, Git direct push rules enforced)  
**Execution Context:** Autonomous Forensic Verification & Pre-Phase 6 Hardening  

---

## 1. Executive Summary

Prior to beginning **Phase 6: Engine, Schema V2 and Rule Expansion**, an exhaustive forensic audit of AUB Phases 0 through 5 was performed across the codebase, test suites, evaluation harnesses, and web application frontend.

All safety properties (Rules R1–R12), clinical honesty constraints, deterministic execution guarantees, and test verification gates were verified directly on the real runtime environment.

### Verification Matrix Summary

| Component | Target Requirement | Measured Audit Status | Verdict |
| :--- | :--- | :--- | :--- |
| **Phase 0: Hygiene & Baseline** | Reproducible env, task runner, lockfiles | `.venv`, `tools/tasks.py`, `package-lock.json` verified | **PASS** |
| **Phase 1: Honesty & Explanations** | Honest labels, FakeLLM mock disclosure, no fake certs | All UI disclaimers present, LLM mock status explicit | **PASS** |
| **Phase 2: Patient-Aware Retrieval** | Predicates, BM25 conditioning, abstention | Lexical BM25 + n-gram TF-IDF RRF + sidecars verified | **PASS** |
| **Phase 3: Corpus Expansion** | 36 syndromes, content-addressed IDs, alias map | 36 protocols, 600+ chunks, zero hash collisions | **PASS** |
| **Phase 4: Evaluation Rebuild** | Leakage-free benchmark, abstention recall, metrics | 224 cases, zero test leakage, 1.0000 hard negative recall | **PASS** |
| **Phase 5: Applicability Grounding** | IF/THEN applicability sidecars, verification | 36 sidecars validated, verified against citations | **PASS** |
| **Pytest Full Suite** | Deterministic unit/integration coverage | 431 passed, 1 xfailed (HD-6) in 28.5s | **PASS** |
| **Evaluation Suites** | Golden, mechanics, metamorphic, adversarial | 65/65 golden, 41/41 mechanics, 3/3 meta, 19/19 adv | **PASS** |
| **Frontend Test & Build** | Vitest unit tests, Vite bundle build | 36/36 Vitest tests passing; Vite build clean | **PASS** |

---

## 2. Hardening Measures Implemented

### 2.1 Alias Cache Isolation (`src/triagerag/rag/aliases.py`)
- **Vulnerability Identified:** The node alias loader used an unkeyed `functools.lru_cache()` which assumed a single global data directory. When tests or tools instantiated isolated temporary data directories (e.g. `tmp_path`), previously cached aliases from `data/` could leak into test contexts.
- **Remediation:** Refactored `load_node_aliases` and `load_reverse_node_aliases` to resolve and normalize paths before dispatching to keyed cache loaders `_load_node_aliases_cached(resolved_dir_str)` and `_load_reverse_node_aliases_cached(resolved_dir_str)`. Added `clear_node_alias_cache()` for explicit test isolation.
- **Verification:** Unit test `test_alias_cache_isolation_across_directories` added to `tests/unit/test_aub_phase3_content_ids.py` verifying zero cache leakage across different directories.

### 2.2 Human Decision Preservation
- **HD-6 Invariant:** Non-overridable hard-ceiling dose multiplier remains unresolved. The test `test_overdose_blocks_not_high` in `tests/test_golden_cases.py` remains explicitly marked with `xfail(strict=True)` to honor the unresolved clinical decision without breaking test integrity.
- **HD-7 Invariant:** Candidate rules must remain `PLACEHOLDER_UNRETRIEVED` or `RETRIEVED_UNREVIEWED` with `verified: false`. No automated promotion to active/verified status is permitted.

---

## 3. Pre-Phase 6 System Readiness

With Phases 0–5 thoroughly audited, hardened, and locked in:
1. Pure offline execution is strictly maintained (zero network calls, no API keys).
2. The deterministic engine report remains completely separated from LLM generation.
3. The repository is fully ready for **AUB Phase 6 (T6.0–T6.6)** on branch `aub/phase-6-engine-rules`.
