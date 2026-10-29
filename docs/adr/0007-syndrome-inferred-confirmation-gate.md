# ADR 0007: Downstream Clinician Confirmation Gate on Inferred Syndrome (`SYNDROME_INFERRED`)

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Status
Accepted (2026-10-29) — Fix Gate G3 (`FG-03`, `FG-05`, `FG-15`, `HD-4`)

## Context
When `Patient.suspected_syndrome` is omitted (`None`), protocol retrieval attempts to infer a candidate syndrome from vitals-derived physiological flags subject to two gates:
1. The top normalized relevance score must meet `config.syndrome_inferred_threshold` (stricter than `config.calibrated_threshold`).
2. The relative score margin `(top1 - top2) / top1` between the top two candidate syndromes must meet `config.min_syndrome_margin`.

Previously (`FG-03`), when a vitals-only query cleared both gates, `evaluate_abstention_with_code` returned `(abstained=False, abstain_code=AbstainCode.SYNDROME_INFERRED, reason=...)`, but `verify_plan` and `run_triage` treated `abstained=False` identically to a clinician-supplied syndrome and allowed steps to reach `StepStatus.APPROVED`. Furthermore (`FG-05`), `RetrievalService.retrieve` and `retrieve_protocol_chunks` defaulted `threshold` to `calibrated_threshold`, preventing `syndrome_inferred_threshold` from taking effect.

## Decision
1. **New Step Verdict `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION` (`HD-4` Fail-Closed Default):**
   - When `retrieval_abstain_code == AbstainCode.SYNDROME_INFERRED`, no step in `verify_plan` or `run_triage` (including after HIGH alert overrides) may be assigned `StepStatus.APPROVED`.
   - Any step that passes deterministic drug, dose, contraindication, and clause-scoped citation checks is capped at `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION` with an explicit rejection/confirmation note requiring a clinician to confirm the inferred syndrome before acting.
2. **Mode-Selected Calibrated Thresholds (`FG-05`):**
   - `threshold` defaults to `None` across `RetrievalService.retrieve`, `retrieve_protocol_chunks`, and `evaluate_abstention_with_code`.
   - When `threshold is None`, `evaluate_abstention_with_code` selects `config.calibrated_threshold` for clinician-supplied syndromes (`syndrome_provided=True`) and `config.syndrome_inferred_threshold` for vitals-inferred retrieval (`syndrome_provided=False`).
   - Import-time configuration loading (`DEFAULT_MIN_RETRIEVAL_THRESHOLD`) and test-only `> 1.0` raw-score branches are removed.
3. **Immutable `RetrievalContext` & Cache Hygiene (`FG-15`):**
   - `RetrievalService` builds an immutable `RetrievalContext` bundling `RetrievalConfig`, `VitalsFlagsConfig`, `CorpusManifest`, and `ActionCuesConfig` for its `data_dir` and passes it explicitly through the retrieval pipeline without calling `get_data_dir()` in the hot path.
   - `RetrievalService.reload()` clears all config/manifest caches before rebuilding `RetrievalContext`.

## Consequences
- **No Unconfirmed Auto-Approval:** Vitals-inferred protocol steps can never reach `StepStatus.APPROVED` without explicit clinician syndrome confirmation (`HD-4`).
- **Enforced by Mutation Testing:** Mutants `M38_IGNORE_SYNDROME_INFERRED` and `M39_ALWAYS_USE_CALIBRATED_THRESHOLD` verify that bypassing either gate immediately fails CI.

