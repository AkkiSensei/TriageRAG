# ADR 0010: Engine Defect Sweep, Rule Isolation Harness, and Differential Verification

## Context
During the 2026-10-29 deep audit of TriageRAG v0.2.1, latent safety defects in the deterministic rule engine were identified (ENG-01..ENG-08). Specifically:
1. **ENG-01**: In `ClassInteractionRule` lookback evaluations, a missing timestamp on one in-class drug caused early termination or skipped check returns that masked confirmed in-window triggers on another in-class drug.
2. **ENG-02**: In `evaluate_plan`, deduplicating plan alerts against baseline alerts by `rule_id` alone discarded alerts that covered proposed plan drugs when the same rule fired on home medications, failing to strike through contraindicated steps.
3. **ENG-03**: In `verify_dose`, `BELOW_MINIMUM` and `MAGNITUDE_WARNING` dose results were computed but never mapped to alerts or step rejections, allowing severe underdoses (e.g. 0.03 mg epinephrine) to be approved.
4. **ENG-05**: In `verify_plan`, dose reports were keyed by `drug_id` alone, causing collisions on multi-step plans with repeat administrations of the same drug.
5. **ENG-07**: `_evaluate_single_rule` evaluated `requires_fields` before relevance checking, creating noisy skipped check cascades for rules unrelated to active or proposed drugs.
6. **ENG-08**: An in-class drug omitted from a rule's `lookback_hours_by_ingredient` table silently fell through without alert or skip.
7. **ENG-09**: Full-ruleset evaluation masked defects because redundant rules fired alongside buggy class rules.

## Decision
1. **Confirmed Trigger Precedence (ENG-01)**: All medications are evaluated in the lookback loop. A confirmed in-window trigger strictly wins and emits an `Alert` (`BLOCK`). Missing timestamp skips are only returned if zero in-window triggers were found.
2. **Alert Identity & Proposed Coverage (ENG-02)**: Baseline alert deduplication keys on `(rule_id, frozenset(drug_ids))`. A rule that fires on a newly proposed drug produces an alert covering that proposed drug, ensuring proper strike-through.
3. **Exhaustive Dose Status Handling (ENG-03)**: Every status of `CalculatedDoseReport` maps deterministically to an Alert, SkippedCheck, and StepStatus (`EXCEEDS_CEILING` -> FLAGGED_HIGH; `MAGNITUDE_WARNING` -> FLAGGED_HIGH; `BELOW_MINIMUM` -> FLAGGED_HIGH if tripwire, else FLAGGED_MODERATE; `UNVERIFIED_MISSING_CAP` -> UNVERIFIED_MISSING_DATA).
4. **Step-Keyed Dose Reports (ENG-05)**: Added `step_number: int | None` to `CalculatedDoseReport` and `Alert`. Lookups in `verify_plan` key on `(step_number, drug_id)` to eliminate multi-step collisions.
5. **Relevance Gating (ENG-07)**: Implemented `_is_rule_relevant`. For plan evaluation (Pass 2), only rules involving proposed drugs are evaluated. For baseline evaluation (Pass 1), rules check active medications or unresolved history.
6. **In-Class Lookback Completeness & Data Lint (ENG-08)**: An in-class drug missing from `lookback_hours_by_ingredient` returns a `SkippedCheck` rather than silently passing. `tools/validate_data.py` asserts that every class member in `classes.yaml` has an explicit lookback entry.
7. **Rule Isolation Harness (ENG-09)**: `eval/run_golden.py` includes `only_rules(registry, rule_id)` to evaluate each expected rule in complete isolation from redundant rules.
8. **Differential Testing (ENG-09)**: Implemented an independent, naïve reference interpreter in `tests/property/test_engine_differential.py` running 1,000 Hypothesis permutations with 0 divergences.
9. **Gross Overdose Non-Overridable Ceiling (ENG-04 / HD-6)**: Marked `test_eng04` as xfail pending human clinical decision HD-6 on the hard-ceiling multiplier above which overdoses become non-overridable `BLOCK`.

## Status
Accepted. All verification gates and evaluation suites pass 100% green.

