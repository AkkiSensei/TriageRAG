# ADR 0015: Schema V2 and Deterministic Rule Engine Expansion

## Status
Accepted

## Context
In AUB Phase 6, TriageRAG's deterministic safety engine required significant expansion to support the breadth of emergency clinical rule logic identified during the independent technical audit (Audit §5.3, Part II - A).

The existing engine (12 shipped rules) covered drug-drug pairs, class interactions, allergy cross-reactivity, population categories, and simple single-vital interlocks. However, real emergency protocols and formulary safety checks depend on:
1. Patient conditions and comorbidity contraindications (e.g., AV block, active asthma, cardiogenic shock, active bleeding).
2. Laboratory interlocks with explicit units and operator thresholds (e.g., serum potassium > 5.5 mmol/L, QTc interval > 500 ms, eGFR < 30 mL/min).
3. Route and concentration limits (e.g., IV promethazine concentration <= 25 mg/mL, IM heparin prohibition, route volume limits such as IM > 3 mL warning).
4. Organ function restrictions (renal and hepatic staging).
5. Administration rate limits (e.g., IV phenytoin <= 50 mg/min, IV vancomycin <= 10 mg/min, IV potassium chloride <= 20 mEq/h).
6. Dosing interval lookbacks and frequency limits across planned steps and prior medication history.
7. Fixed-Dose Combination (FDC) ingredient resolution and Indian brand alias mapping (e.g., Augmentin, Dolo 650, Combiflam, Deriphyllin).
8. Evidence-grounded candidate rule mining with deterministic integrity validators.

Crucially, under Human Decision Gate **HD-7**, no candidate rule may be promoted to `REVIEWED` or `VERIFIED` without human clinical sign-off, and `BLOCK` severity rules require two independent sign-offs (dual control). Furthermore, under **HD-6**, the overdose hard-ceiling multiple remains open, so tests asserting unoverridable overdose must remain `@pytest.mark.xfail(strict=True)`.

## Decision

1. **Dual Trust Policy Modes (T6.0):**
   - Implemented `TrustMode.STRICT` (default) and `TrustMode.DEMO` in `src/triagerag/contracts/enums.py`.
   - In `STRICT` mode, unverified candidate rules are completely ignored, and unverified counts are surfaced.
   - In `DEMO` mode, candidate rules evaluate with explicit `UNSOURCED DRAFT` badges on UI and CLI wristbands.
   - Codified in `docs/safety/TRUST_POLICY.md`.

2. **Schema V2 Rules and Patient Extensions (T6.1):**
   - Added 6 new rule models in `src/triagerag/contracts/rules_schema.py`:
     - `ConditionContraindicationRule`
     - `LabInterlockRule`
     - `RouteConcentrationRule`
     - `OrganFunctionRule`
     - `CoAdministrationRule`
     - `RateLimitRule`
   - Extended `Patient` schema with `conditions: dict[str, Literal["yes", "no", "unknown"]]`, `labs: dict[str, MeasuredLab]`, `renal_impairment`, `hepatic_impairment`.
   - Extended `PlanStepDraft` with `concentration_mg_per_ml`, `diluent`, `rate_mg_per_min`, `frequency_hours`, `relative_time_minutes`.
   - Preserved 100% backward compatibility for all existing 12 shipped rules.

3. **Dose Engine Expansion (T6.2):**
   - Implemented `calculate_administration_volume` computing volume in mL with unit consistency.
   - Enforced route volume tripwire: IM injections > 3.0 mL emit `MODERATE` route volume warnings.
   - Implemented `verify_dosing_intervals`: checks minimum repeat intervals between planned steps and verifies lookbacks against `patient.medications` with absolute timestamp math.
   - Implemented `verify_administration_rate` evaluating `rate_mg_per_min` against formulary limits.
   - Harmonized `daily_max` mass semantics across weight-based and fixed dosing.

4. **Medication Class Taxonomy & FDC Expansion (T6.3):**
   - Expanded `data/classes.yaml` with Waves 1, 2, and 3 emergency generics from AUB §11.
   - Added 34 single-ingredient and multi-ingredient Indian brand aliases to `data/aliases.yaml` (e.g., Augmentin, Dolo 650, Combiflam, Deriphyllin, Calpol, Novamox).
   - Enhanced `AliasResolver` with strength token stripping and FDC multi-ingredient expansion.
   - Implemented LASA (Look-Alike/Sound-Alike) safety tripwire: pairs in `LASA_PAIRS` are strictly protected from fuzzy auto-resolution.

5. **Source-Traceable Candidate Batches (T6.4):**
   - Authored 40 candidate rules across 3 batches adhering to AUB Part II - A:
     - `data/rules_candidates/batch_1.yaml` (15 rules: CV-05, CV-12, CV-17, CNS-01, CNS-04, CNS-11, CNS-12, AC-01, AC-02, EN-01, EN-03, ID-01, DUP-03, DUP-04, AN-08)
     - `data/rules_candidates/batch_2.yaml` (15 rules: CV-09, CV-10, CV-16, CV-18, AN-01, AN-02, AN-03, AC-06, EN-12, ID-19, VL-05, CV-14, CV-19, CNS-16, AN-09)
     - `data/rules_candidates/batch_3.yaml` (10 rules: NE-01, NE-03, ID-10, EN-06, AC-08, AN-10, EN-11, EN-09, NE-02, CNS-14)
   - Every candidate rule carries `source_status: PLACEHOLDER_UNRETRIEVED`, `verified: false`, `reviewer: null`, `content_origin: AGENT_DRAFT_UNSOURCED`.

6. **Rule Coverage Matrix and Alert Fatigue Gate (T6.5):**
   - Created `tools/rule_coverage.py` asserting every active rule has >= 3 positive, >= 3 negative, and >= 1 boundary test cases passing in isolation (`only_rules`).
   - Expanded `data/golden/shipped_ruleset_cases.yaml` from 65 to 86 cases.
   - Monitored alert fatigue: 0.52 alerts per synthetic patient, with 0.0% false-alert rate on negatives.

7. **Evidence-Grounded Rule Mining Pipeline (T6.6):**
   - Created `tools/mine_rules.py` ingesting Tier-2 regulatory SPL evidence chunks (`data/corpus/evidence_chunks.json`).
   - Enforced 5 deterministic validators:
     1. `quote in chunk` (verbatim substring match)
     2. `numbers in quote` (numeric values verified in quote text)
     3. `ids resolve` (drug and class IDs resolve in registry)
     4. `schema valid` (validates against Schema V2 models)
     5. `no duplicate semantic key` (prevents redundant rule interactions)
   - 100% of auto-sourced rules passed all 5 deterministic validators.
   - Published clinician review queue to `docs/REVIEW_QUEUE.md` under HD-7 governance.
   - Benchmarked against 30-rule gold set (`data/rules_candidates/mining_gold_set.yaml`).

## Consequences
- The deterministic safety engine can evaluate realistic emergency clinical protocols with condition, lab, rate, concentration, and route checks.
- Zero clinical facts are invented; unreviewed rules remain fail-closed and explicitly badged.
- CI automatically protects against coverage decay and alert fatigue.
- Ready for research showcase and Phase 7 extensions.
