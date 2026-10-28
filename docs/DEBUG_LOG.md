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

---

## Part C: RAG Pipeline Postmortem & Industry-Grade Remediation (WP0–WP9)

### WP0: Baseline & Reproduction Guardrails (`rag-wp0`)
- **Baseline Suite Verification:**
  - `python tools/tasks.py verify`: 91/91 Pytest passed, Ruff clean, Mypy clean (87 files), Import-linter clean, Golden 65/65, Mechanics 41/41, Metamorphic 3/3, Adversarial 9/9.
  - `python eval/run_mutation.py`: 40/40 mutants killed (100%).
  - `python eval/run_retrieval.py`: 32 pairs, Recall@5 100.0%, MRR 0.896, 3 abstain cases 100.0%.
- **Reproduction Probes Added (`tests/unit/test_rag_regressions.py`):**
  1. `test_unknown_syndrome_with_flags_abstains` (RAG-01): **FAILED as expected** (`report.abstained == False`, returned `CHEST_PAIN_01_NODE_4` with score `3.1103` on `kidney_stone` + hypotension/tachycardia).
  2. `test_known_syndrome_never_returns_other_syndrome_chunks` (RAG-01): **FAILED as expected** (`anaphylaxis` + hypotension returned cross-syndrome `chest_pain` chunks).
  3. `test_no_adult_thresholds_applied_to_paediatric` (RAG-03): **FAILED as expected** (4-year-old with HR 120, RR 30 triggered adult `'tachycardia'` and `'tachypnea'` flags).
  4. `test_trailing_section_not_absorbed_into_last_node` (RAG-05): **FAILED as expected** (`## Notes\nunrelated trailing text` bled into `NODE_2`).
  5. `test_node_without_then_is_reported_not_silently_dropped` (RAG-05): **FAILED as expected** (node `2. IF condition c` without `THEN` was silently dropped with `unparsed_lines == ()`).
  6. `test_missing_synthetic_flag_rejected` (RAG-04): **FAILED as expected** (frontmatter missing `synthetic` defaulted silently to `True` instead of raising `ValueError`).
  7. `test_step_drug_must_appear_in_cited_chunk` (RAG-02): **FAILED as expected** (`administer nitroglycerin` citing `HYPOGLYCEMIA_01_NODE_1` was `APPROVED` — citation laundering).
- **Gate Status:** All 7 new probes fail for the exact documented reasons; all 91 pre-existing tests pass.

---

### WP1: Provenance, Frontmatter Schema, Manifest, Quarantine & Corpus CLI (`rag-wp1`)
- **Finding IDs:** RAG-04, RAG-12 (part).
- **Symptoms:**
  - `chunking.py` defaulted `synthetic` to `True` when omitted in YAML frontmatter.
  - `api/routes/protocols.py` hardcoded `synthetic=True` on `ProtocolChunkDto`.
  - `ingest.py` parsed chunks before checking license metadata, split frontmatter naively with `content.split("---")` (breaking on horizontal rules in markdown body), and aborted the entire ingestion run if a single file was malformed.
  - Chunks lacked `version`, `content_hash`, `license`, `attribution`, `source_url`, and `source_status`.
- **Root Cause:** Missing Pydantic validation schema for frontmatter and lack of per-file quarantine reporting in `ingest.py`.
- **Fixes:**
  - Added `ProtocolFrontmatter` (Pydantic `extra="forbid"`, `synthetic: StrictBool` required with no default; `synthetic=False` requires `license`, `attribution`, `source_url`, `version`, `retrieved_at`).
  - Extended `ProtocolChunk` with `title`, `indexed_text`, `version`, `content_hash` (SHA-256), `license`, `attribution`, `source_url`, `retrieved_at`, `reviewed_by`, `source_status`, `unparsed_lines`, `parse_warnings`, and `suspicious_patterns`.
  - Created `data/corpus/manifest.yaml` with SHA-256 `content_hash` per document and controlled syndrome vocabulary.
  - Implemented `ingest_protocols_with_report` returning `IngestReport` with `QuarantinedDocument` records and deterministic `corpus_hash`.
  - Updated `ProtocolChunkDto` and `/api/protocols` to expose `c.synthetic` and provenance fields.
  - Added `triagerag corpus {validate,report,explain,add}` CLI commands in `src/triagerag/cli.py`.
- **Tests:** `tests/unit/test_rag_wp1_ingestion.py` (4 tests) + `test_missing_synthetic_flag_rejected` in `tests/unit/test_rag_regressions.py` — all PASS.

---

### WP2: Grammar-Based Chunker, Round-Trip Invariant & Contextual Headers (`rag-wp2`)
- **Finding IDs:** RAG-05, RAG-06.
- **Symptoms:**
  - Trailing non-decision sections (`## Notes`) bled into the final `IF...THEN` child node.
  - Decision nodes starting with `IF` but lacking a `THEN` clause were silently dropped without warning.
  - Child decision nodes lacked document title/section/syndrome context in the index.
- **Root Cause:** Regex `r"(^\d+\.\s+IF\s+.*?)(?=(?:^\d+\.\s+IF|\Z))"` ran to `\Z` (end of document) and silently skipped matches without `"THEN "`.
- **Fixes:**
  - Replaced regex splitter with a line-by-line grammar state machine (`chunk_protocol_markdown`) supporting `ELSE IF`, `ELSE`, and indented sub-step bullets (`-`, `*`, `a)`), while terminating nodes on headings (`#`–`######`), blockquotes (`>`), horizontal rules (`---`), or subsequent numbered items.
  - Implemented `verify_round_trip_invariant(content, chunks)` ensuring every non-empty body line is accounted for in structural headers, a single child node, or `parent.unparsed_lines`.
  - Added contextual header indexing (`"{title} › {section} › {syndrome} › {chunk_id}\n{text}"`) in `chunk.indexed_text` while keeping `chunk.text` verbatim for span citations.
  - Added `chunk_decision_graph_json` adapter for structured JSON decision flowcharts.
- **Tests:** `tests/unit/test_rag_wp2_chunker.py` (4 unit tests), `tests/property/test_chunker_properties.py` (500 Hypothesis generated protocol documents), `test_trailing_section_not_absorbed_into_last_node` and `test_node_without_then_is_reported_not_silently_dropped` in `tests/unit/test_rag_regressions.py` — all PASS.

---

### WP3: Per-Population Vitals Flags, Syndrome Vocabulary & Hard Syndrome Filter (`rag-wp3`)
- **Finding IDs:** RAG-01 (part), RAG-03, RAG-14, RAG-15 (part).
- **Symptoms:**
  - `retrieve.py::derive_vitals_flags` hardcoded adult clinical thresholds (`SBP < 90`, `HR > 100`, `RR > 22`, etc.) and applied them to all populations, causing a 4-year-old with HR 120 / RR 30 to be flagged with adult `tachycardia` and `tachypnea` (violating Rule R3).
  - `suspected_syndrome` was only repeated 3x as BM25 tokens, allowing unknown syndromes (`kidney_stone`) with abnormal vitals to retrieve unrelated protocols (`CHEST_PAIN_01_NODE_4`, score 3.11 vs 0.30) and known syndromes (`anaphylaxis` + hypotension) to return cross-syndrome chunks (`chest_pain`).
- **Root Cause:** Lack of data-driven per-population vitals flag tables with `Provenance`, lack of a controlled syndrome vocabulary, and soft keyword matching instead of hard syndrome filtering.
- **Fixes:**
  - Created `data/retrieval/vitals_flags.yaml` defining per-population (`adult`, `paediatric`, `neonate`) vitals flag rules with full `Provenance` and `RuleStatus` (`ACTIVE` vs `NEEDS_SOURCE`). Unsourced thresholds (`threshold: null, status: NEEDS_SOURCE`) fail closed and emit nothing; paediatric/neonate never fall back to adult values.
  - Created `data/retrieval/config.yaml` with `Provenance` and `calibration_run_id`, removing all magic clinical/retrieval numeric literals from `src/triagerag/rag/*.py`.
  - Added `AbstainCode` enum (`NONE`, `NO_POPULATION_COVERAGE`, `UNKNOWN_SYNDROME`, `LOW_CONFIDENCE`, `AMBIGUOUS_MARGIN`, `EMPTY_QUERY`, `INDEX_UNAVAILABLE`, `SYNDROME_INFERRED`) to `src/triagerag/contracts/enums.py` and extended `RetrievalReport`.
  - Enforced hard syndrome filtering when `suspected_syndrome` is known, `AbstainCode.UNKNOWN_SYNDROME` when unknown, and top-1/top-2 syndrome relative margin + `SYNDROME_INFERRED` when `suspected_syndrome` is omitted.
- **Tests:** `tests/unit/test_rag_wp3_query_and_flags.py` (3 tests incl. AST scan across all `rag/*.py` files) + `test_unknown_syndrome_with_flags_abstains`, `test_known_syndrome_never_returns_other_syndrome_chunks`, `test_no_adult_thresholds_applied_to_paediatric` in `tests/unit/test_rag_regressions.py` — all PASS.

---

### WP4: Index & Scoring Refactor, Morphology/Synonyms & Parent Deduplication (`rag-wp4`)
- **Finding IDs:** RAG-07, RAG-09.
- **Symptoms:**
  - `BM25Okapi` on small shards (paediatric sepsis with 4 chunks) yielded `0.0` or negative IDF scores when terms appeared in `>= N/2` chunks (e.g., parent + 1 child).
  - Search returned both whole-document parent chunks and their child decision nodes in `top_k`, duplicating context and wasting tokens.
  - `BM25Okapi.get_scores` leaked `numpy.float64` values and required `# type: ignore[assignment]`.
  - `ClinicalTokenizer` lacked morphological stemming, clinical/Hinglish synonyms, and expanded 2-letter acronyms (`hr`) case-insensitively.
- **Root Cause:** Direct reliance on `BM25Okapi` standard IDF formula over un-deduplicated parent+child pools and thin lexical normalization.
- **Fixes:**
  - Replaced `BM25Okapi` scoring with pure-Python `_PopulationBM25Stats` implementing non-negative smoothed IDF (`ln(1 + (N - df + 0.5)/(df + 0.5)) > 0`) over deduplicated child decision nodes, guaranteeing both strictly positive scores on small pools and 100% score/ranking invariance when other populations are modified.
  - Added `expand_parents(chunks)` to attach parent `ProtocolChunk` context once without duplicating parent + child in `top_k`, plus `explain_search()` for per-term BM25 contribution inspection.
  - Created `data/retrieval/synonyms.yaml` (with `Provenance`) covering clinical morphology (`hypotensive` -> `hypotension`), British/US variants, drug synonyms (`adrenaline` -> `epinephrine`), and Hinglish triage terms (`bukhar` -> `fever`, `saans`/`dama` -> `severe_asthma`), plus conservative suffix stemming and case rules for 2-letter acronyms (`HR`, `PE`, `RR`).
  - Defined `@runtime_checkable class Retriever(Protocol)` and eliminated `# type: ignore` from `src/triagerag/rag/`.
- **Tests:** `tests/unit/test_rag_wp4_index.py` (5 unit & Hypothesis property tests) — all PASS.

---

### WP5: Evaluation Overhaul (160-Case Node-Level Benchmark) & Calibration (`rag-wp5`)
- **Finding IDs:** RAG-01 (calibration & margin), RAG-10.
- **Symptoms:**
  - Legacy `eval/run_retrieval.py` only had 32 near-identical queries targeting whole-document parent chunk IDs (`ANAPHYLAXIS_01`), only 3 abstain cases (none with unknown syndrome + abnormal vitals), and instantiated `BM25ClinicalIndex(chunks)` without production config parity.
- **Root Cause:** Doc-level targets and tiny benchmark size hid node-level ranking degeneracy and wrong-syndrome abstention failures.
- **Fixes:**
  - Created `eval/retrieval/dataset.yaml` (via `eval/retrieval/build_dataset.py`) with **160 structured patient cases** (98 `dev` [60%], 62 `test` [40%], stratified with seed 42) across all 10 mandatory case families from Appendix B, with graded node-level relevance (`2` = directly actionable node, `1` = supporting node, `0` = irrelevant).
  - Replaced `eval/run_retrieval.py` to evaluate the shared production `RetrievalService.create_default()` factory, computing node-level Recall@5, MRR, nDCG@5 with 95% bootstrap confidence intervals, Abstain Precision/Recall, Hard-Negative Abstain Recall (`1.0000`), Wrong-Protocol Rate (`0.0000` on test), Expected Calibration Error (ECE `0.1456`), latency p50/p95 (`p95 = 12.238 ms`), and cross-run determinism.
  - Generated `eval/reports/retrieval.json`, `eval/reports/retrieval_baseline.json`, and `eval/reports/retrieval_calibration.md`.
- **Tests:** `tests/unit/test_rag_wp5_eval.py` (2 tests verifying 160-case structure, 10 mandatory families, production parity, and zero wrong-protocol rate) — all PASS.


### WP6 — Grounding Verification (`rag-wp6`)
- **Findings Addressed:** RAG-02 (citation laundering, action-cue polarity, overlap gate, child-node specificity), RAG-11 (corpus-borne prompt injection defense).
- **Root Cause:** `verify_citation` only checked whether `quoted_span` was a substring of `chunk.text` and computed `lexical_overlap` without enforcing a threshold, without checking whether a cited chunk actually mentioned the step's `drug_id` or action polarity (`administer` vs `withhold`), and without requiring child-node specificity when child decision nodes existed. Furthermore, retrieved protocol chunks were interpolated directly into LLM prompts without delimiter isolation or sanitization.
- **Remediation:**
  1. Created `data/retrieval/action_cues.yaml` with `Provenance`, `min_overlap_threshold: 0.08`, `min_span_chars: 10`, `administer_cues`, and `withhold_cues`.
  2. Enhanced `src/triagerag/verify/citations.py` (`verify_citation` + `verify_step_support`) and `src/triagerag/verify/plan_verifier.py` (`support_reason` recorded on `VerifiedStep`).
  3. Updated `src/triagerag/llm/prompts.py` (`sanitize_protocol_chunk_for_prompt` + `<untrusted_retrieved_protocol_data>` delimiter) and `src/triagerag/llm/fake.py` (`_select_supporting_chunk_and_span`).
  4. Extended `eval/run_mutation.py` with 5 new grounding/RAG mutants (`M29`–`M33`), achieving **45/45 killed (100.0%)**.
- **Tests:** `tests/unit/test_rag_regressions.py` (all 7/7 probes GREEN) and `tests/unit/test_rag_wp6_grounding.py` (4/4 GREEN).


### WP7 — Hybrid & Rerank Experiment (`rag-wp7`)
- **Findings Addressed:** RAG-08 (claimed hybrid RRF / reranker vs. lexical-only implementation).
- **Root Cause:** `docs/ARCHITECTURE.md` claimed `BM25 / RRF Retrieval` while only `BM25ClinicalIndex` was implemented and no comparative ablation across lexical, dense, hybrid RRF, and reranked arms existed.
- **Remediation:**
  1. Implemented `DenseRetriever`, `HybridRRFRetriever` (`hybrid_rrf` and `hybrid_rrf_rerank`), and `build_retriever_backend` in `src/triagerag/rag/hybrid.py`, all conforming to `@runtime_checkable class Retriever(Protocol)` and enforcing identical query-time hard population and syndrome filters.
  2. Created `eval/run_retrieval_ablation.py` evaluating all 4 arms on the 160-case WP5 dataset and writing `eval/reports/retrieval_ablation.json` and `eval/reports/retrieval_ablation.md`:
     - `bm25`: 100.0% R@5, 0.8840 MRR, 0.9242 nDCG@5, 0.0000 Wrong-Protocol Rate
     - `dense`: 99.0% R@5, 0.8873 MRR, 0.9174 nDCG@5, 0.0000 Wrong-Protocol Rate
     - `hybrid_rrf`: 96.1% R@5, 0.8578 MRR, 0.8973 nDCG@5, 0.0000 Wrong-Protocol Rate
     - `hybrid_rrf_rerank`: 100.0% R@5, 0.8971 MRR, 0.9297 nDCG@5, 0.0000 Wrong-Protocol Rate
  3. Updated `docs/ARCHITECTURE.md` to accurately reflect the `Retriever` protocol, default `BM25ClinicalIndex`, optional `DenseRetriever` / `HybridRRFRetriever`, and ablation results.
- **Tests:** `tests/unit/test_rag_wp7_hybrid.py` (2/2 PASS).


### WP8 — Service, Observability, Reproducibility (`rag-wp8`)
- **Findings Addressed:** RAG-12 (audit trail missing retrieval metadata & duplicate `formulary_version`), RAG-13 (fragmented index construction & module-global `_INDEX`), RAG-14 (`assert prov is not None` in orchestrator), RAG-15 (Streamlit UI `"paediatric_sepsis_screen"` mismatch).
- **Root Cause:** `api/routes/triage.py`, `api/routes/protocols.py`, `cli.py`, and `ui/app.py` each built their own `BM25ClinicalIndex` directly from disk; `orchestrator.py` borrowed `registry.rules[0].provenance` with `assert prov is not None` for unscored populations and passed `formulary_version=registry.version` to `append_audit_entry` without logging retrieval query, filters, stage scores, `corpus_hash`, `index_version`, `config_hash`, or `abstain_code`.
- **Remediation:**
  1. Wired `RetrievalService.create_default(get_data_dir())` into `api/routes/triage.py` (including new `POST /api/triage/explain`), `api/routes/protocols.py`, `cli.py`, and `ui/app.py` (and fixed `"paediatric_sepsis_screen"` -> `"paediatric_sepsis"`).
  2. Added deterministic `formulary_version` SHA-256 hash calculation to `ClinicalRegistry`.
  3. Replaced `registry.rules[0].provenance` and `assert prov is not None` in `src/triagerag/orchestrator.py` with `_UNAVAILABLE_SCORE_PROVENANCE`.
  4. Extended `AuditRecord`, `append_audit_entry`, and `AuditEntryDto` with `retrieval_query`, `retrieval_filters`, `retrieval_stage_scores`, `corpus_hash`, `index_version`, `config_hash`, and `abstain_code`.
  5. Authored `docs/adr/0006-rag-hardening-and-support-verification.md`.
- **Tests:** `tests/unit/test_rag_wp8_service_and_audit.py` (4/4 PASS).


### WP9 — Ease of Use & Ops (`rag-wp9`)
- **Findings Addressed:** RAG-16 (lack of retrieval explainability CLI/UI, containerization, and 10k-chunk scale latency verification).
- **Root Cause:** Operators lacked a CLI `retrieve --explain` diagnostic command, UI retrieval inspection panel showing `abstain_code` and `corpus_hash`, Docker/DevContainer packaging, and 10,000-chunk scale benchmark verification.
- **Remediation:**
  1. Added `triagerag retrieve --scenario <ID> --explain` (and `--syndrome` / `--population`) to `src/triagerag/cli.py`.
  2. Updated `web/src/features/results/RetrievalView.tsx` and `web/src/types/api.ts` to render the Retrieval Inspector diagnostic banner (`abstain_code`, `query`, `backend`, `index_version`, `corpus_hash`) and abstention alerts.
  3. Optimized `BM25ClinicalIndex` with precomputed syndrome index partitions (`indices_by_syndrome`) and cached config parameters, and created `eval/run_latency_benchmark.py` verifying 10,000-chunk scale performance (`p50 = 3.945 ms`, `p95 = 5.648 ms` < `50.0 ms` target) and writing `eval/reports/latency_benchmark.json`.
  4. Added `Dockerfile`, `docker-compose.yml`, `.devcontainer/devcontainer.json`, `pyproject.toml` dependency groups (`core`, `rag`, `ui`, `api`, `llm`, `dense`, `dev`), and `demo` task in `tools/tasks.py` and `Makefile`.
- **Tests:** `tests/unit/test_rag_wp9_ops.py` (4/4 PASS).

