# TriageRAG

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

TriageRAG is a research prototype exploring emergency-triage decision support through deterministic verification combined with machine-guided plan drafting.

## Core Architecture Principles

1. **R1: Code decides; the LLM explains.** Scores, alerts, dose mathematics, drug identity, and safety verdicts come strictly from deterministic Python code. The LLM emits only draft proposals (`PlanDraft`).
2. **R2: Fail closed.** Missing, unknown, or unresolved data yields `UNVERIFIED`, never a clean bill of health. "No rule fired" means "no rule in this ruleset fired", not "safe".
3. **R3: No invented clinical facts.** Every rule, alias, formulary ceiling, score table, and threshold carries `Provenance` metadata.
4. **R4: Unknown is first-class.** `Measured[T]` encapsulates measured, estimated, and unknown clinical values. Absolute timestamps are used for lookback windows.
5. **R5: LLM-optional.** If the LLM or vector index fails or is unavailable, the full deterministic EngineReport and extractive protocol text still render (`llm_fallback_mode=True`).
6. **R6: Strict isolation.** Engine and contracts never import LLM or RAG packages.
7. **R7: Untrusted input.** Free-text complaint is strictly excluded by default from engine logic and retrieval queries.
8. **R8: Decimal-only clinical math.** High-precision decimal arithmetic with 10x/1000x magnitude tripwires.
9. **R9: Synthetic corpus.** Bundled emergency protocols contain synthetic text with zero hardcoded numeric doses.
10. **R10: Measured, not claimed.** Continuous automated testing verifies rule implementation against the golden dataset.
11. **R11: No override of BLOCK.** No code path permits overriding a `BLOCK` severity alert. `HIGH` severity requires logged clinician rationale.
12. **R12: Determinism.** The engine is pure and functional with injected registry and clock.

## Quickstart

```bash
# Verify repo integrity and run all tests
python tools/tasks.py verify

# Run evaluation suites
python tools/tasks.py eval

# Launch the Streamlit web interface
python tools/tasks.py ui
```
