# TriageRAG — Mutation Testing Report

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## 1. Executive Summary

| Category | Mutants Evaluated | Mutants Killed | Score | Threshold | Status |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Shipped Rule Mutants** | 12 | 12 | **100.0%** | 100.0% | [OK] |
| **Code-Level Mutants** | 37 | 37 | **100.0%** | >=90.0% | [OK] |
| **Total Combined Mutants** | 49 | 49 | **100.0%** | >=95.0% | [OK] |

## 2. Invariants Verified by Code Mutants

- **Verdict Lattice:** BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
- **Fail Closed (Rule R2):** Missing fields emit SkippedCheck; unmapped -> UNVERIFIED.
- **Lookback Windows:** Direction, expiry boundaries, and time elapsed.
- **Withhold Semantics:** Withholding contraindicated agents is APPROVED, not BLOCKED.
- **Citation Grounding (Rule R3):** Exact substring, chunk_id, and doc_id matching.
- **Lexicon Prose Scan (Section 10):** Exact and fuzzy drug leak detection.
- **Interlocks & Overrides (Rule R11):** BLOCK override forbidden; raises error.
- **Dose Arithmetic (Rule R8):** Ceilings, conversions, and magnitude error tripwires.
- **Cryptographic Audit (Section 11):** Hash-chain links, tamper detection, genesis ref.
