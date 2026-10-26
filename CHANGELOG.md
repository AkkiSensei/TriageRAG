# Changelog

All notable changes to TriageRAG will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-26

### Added
- Initial project scaffold and core architecture rules (AGENTS.md, .agent/rules/triagerag.md).
- Strict layer isolation contracts via import-linter.
- Frozen Pydantic v2 schemas: Provenance, Measured[T], Age, Patient, Vitals, ExplicitDose, PlanDraft, EngineReport.
- Four-state Verdict lattice: BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.
- Decimal-only numeric loader for YAML with 10x/1000x magnitude tripwires.
- Pure functional RuleEngine and DoseEngine with immutable registry.
- Synthetic guideline corpus with no numeric doses.
- Offline BM25 protocol index with acronym expansion and hard population filter.
- Verified plan pipeline with token scanning, verbatim citation checking, and repair loop.
- Cryptographic SHA-256 audit chain with file locking and tamper detection.
- Streamlit clinical UI (fixed banner, no bare CLEAR, 4 scenarios) and Typer CLI tools.
- Metamorphic testing suite (3 transformations: brand/generic, reordering, equivalent units).
- Adversarial prompt injection suite (9 combinations: isolated, delimited, drug-hijack neutralization).
- Mutation testing runner (12 critical BLOCK/HIGH rules tested with 100.0% kill score).
- Retrieval benchmark suite (32 pairs: 100.0% Recall@5, 0.896 MRR, 100.0% Abstain Accuracy).
- Multi-arm ablation study harness comparing Arm A, Arm B, and Arm C to `eval/reports/ablation.md`.
- Automated gating and cross-platform task runner via `tools/tasks.py`.
