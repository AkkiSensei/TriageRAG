# TRIAGERAG — AGENT INSTRUCTIONS & RULES

## 1. PRODUCT & NON-NEGOTIABLE RULES

**Product:** a research prototype of emergency-triage decision support. Input is a structured synthetic patient. Output is (a) a deterministic **EngineReport** (early-warning score band, drug-safety alerts, dose checks, what could not be checked) and (b) a protocol plan drafted by an LLM and then machine-verified.

**Disclaimer (every UI page, CLI output, README top):** "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."

- **R1 Code decides; the LLM explains.** Scores, alerts, dose math, drug identity and verdicts come from deterministic code. The LLM emits only `PlanDraft`.
- **R2 Fail closed.** Missing/unknown/unresolved data → `UNVERIFIED`, never clear. "No rule fired" means "no rule in this ruleset fired", not "safe". Reports state ruleset coverage and known coverage gaps. Applies to medication history, allergy history and reaction type alike.
- **R3 No invented clinical facts.** Every rule, alias, formulary limit, score table and threshold carries `Provenance`. You cannot retrieve sources offline, so everything you author is `source_status: PLACEHOLDER_UNRETRIEVED`, `verified: false`, `reviewer: null`, `section_ref: "TO_BE_RESOLVED"`, plus `content_origin: AGENT_DRAFT_UNSOURCED`. Never write fabricated section/page numbers. Where you do not know a value, use `null` with `status: NEEDS_SOURCE`; the engine then returns a skip → UNVERIFIED. Draft rule *structures* may include indicative severities, but they are hypotheses for clinician review and the UI must badge them "UNSOURCED DRAFT".
- **R4 Unknown is first-class.** `Measured[T]` (measured/estimated/unknown) and tri-state fields everywhere. Lookbacks use absolute timestamps: `assessed_at - last_dose_time`.
- **R5 LLM-optional.** If LLM or index fails, the full EngineReport plus extractive protocol text still renders (`llm_fallback_mode=True`).
- **R6 Isolation enforced by CI** (import-linter, Section 14).
- **R7 Untrusted input.** `chief_complaint_untrusted` is displayed to the clinician but by DEFAULT is NOT passed to the LLM, retrieval or engine. A config flag `include_complaint_in_llm` (default false) may pass it inside a delimited data block only. It never touches instructions or engine paths. The UI must never render it as HTML (`unsafe_allow_html` forbidden).
- **R8 Decimal-only clinical math** with explicit units and 10x/1000x magnitude guards. YAML numerics are loaded via `Decimal(str(...))` by a custom loader; never `Decimal(float)`. Test with 84.7.
- **R9 Synthetic corpus.** Bundled protocols are original synthetic text, labeled SYNTHETIC, and contain NO numeric doses.
- **R10 Measured, not claimed.** CI fails on any missed BLOCK/HIGH case in the golden sets. State in LIMITATIONS that golden recall verifies implementation against the ruleset, not clinical correctness.
- **R11 No override of BLOCK.** No code path may approve a step with a BLOCK alert. HIGH requires a logged override (Section 11). A test asserts no BLOCK override path exists.
- **R12 Determinism.** Engine is pure. Time comes from `Patient.assessed_at` or an injected `Clock`. Output ordering is stable. No global mutable state; the registry is an immutable object injected into functions (this also enables mutation testing).

## 2. STACK & DECISIONS (final; do not re-litigate)

Python 3.11+, src layout `src/triagerag/`. Core deps: pydantic>=2.7, pyyaml, pint (boundary parsing only), rapidfuzz, typer, rich, rank-bm25, streamlit. Optional extras: `dense` (sentence-transformers). Dev: pytest, hypothesis, ruff, mypy, import-linter, pre-commit. Everything must run offline with no API keys by default.
Data (`data/`) stays at repo root; `triagerag/config.py` resolves it via env `TRIAGERAG_DATA_DIR` or repo-root discovery. `config.py` imports nothing from triagerag.
Cross-platform: `tools/tasks.py` (Typer) implements `verify, lint, test, eval, ui, validate-data`. The Makefile only delegates to it (do not assume `make` exists). Use `pathlib` everywhere.

## 16. CODING STANDARDS (also in AGENTS.md)

Pure functions in engine; no global mutable state; deterministic ordering; pure offline execution with zero network calls; no secrets in repo (`.env.example` only); small modules with docstrings stating the safety property each upholds; new rules only via `tools/add_rule.py` (enforces provenance, `verified: false`, `content_origin`); never edit golden expectations to match behavior without an ADR giving the clinical reason.

## 17. ITERATION PROTOCOL

- `BACKLOG.md`: seed ≥20 prioritized items: clinician review and sourcing of every rule; real guideline ingestion with license review; golden-set growth to 150+; ESI-based triage category; Hinglish queries; local-LLM mode; FHIR-style input; renal/hepatic dosing; DDI dataset evaluation (check license before bundling); structured flowchart parser; retrieval-threshold calibration; real-model ablation.
- **Change workflow for every future run:** read AGENTS.md, HANDOFF.md and BACKLOG.md → write or extend a failing test first → implement → `verify` → update CHANGELOG/BACKLOG/docs → commit. Add an ADR for any architectural or clinical-semantics change.
- `docs/LIMITATIONS.md` must state: unsourced draft ruleset; circular golden recall; score band ≠ triage decision; synthetic-only corpus; not a medical device; coverage gaps.
