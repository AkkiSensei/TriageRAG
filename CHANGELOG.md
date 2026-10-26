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
- Cryptographic SHA-256 audit chain.
- Streamlit clinical UI and Typer CLI tools.
