# TriageRAG Backlog

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

Prioritized engineering and clinical verification backlog (ordered by safety priority):

### Open Human Decisions (Fail-Closed Defaults Active)

- **HD-1 [P0-CLINICAL] Vitals Flag Thresholds, Sources & Age Bands (`FG-02`)**: Authoritative clinical source, numerical cut-offs, and paediatric age-band definitions (`paediatric_1m_1y`, `paediatric_1_5y`, `paediatric_5_12y`, `paediatric_12_18y`) for every vitals flag across adult, paediatric, and neonate populations in `data/retrieval/vitals_flags.yaml`. **Fail-closed default active:** all rules are `status: NEEDS_SOURCE` with `threshold: null` and `verified: false`; zero flags are emitted until human clinician signoff.
- **HD-2 [P0-CLINICAL] Chronological Age Population Boundaries & Months-to-Days Convention (`FG-04`)**: Authoritative neonate/paediatric/adult chronological age cut-offs and months→days conversion factor in `data/retrieval/vitals_flags.yaml::age_classification`. **Fail-closed default active:** ages are normalized to days (`days_per_month: 30`, `days_per_year: 365`, `neonate_max_days: 28`, `adult_min_days: 6570`); ambiguous `0 months` / `0 years` inputs are flagged (`is_ambiguous_boundary=True`), classified into the more restrictive `neonate` population, and abstain on the boundary.
- **HD-3 [P0-CLINICAL] Clinical ECE Calibration Target & Acceptance Policy (`FG-07`, ADR 0008)**: Clinical governance consensus on acceptable Expected Calibration Error (ECE) and abstention-recall targets on real patient distributions. **Fail-closed default active:** Synthetic prototype ECE is reported as an observational metric with 95% bootstrap CIs; no clinical PASS label is claimed without prospective real-world calibration data.
- **HD-4 [P0-CLINICAL] Downstream Approval Policy for Vitals-Inferred Syndromes (`FG-03`, ADR 0007)**: Clinical governance decision on whether `AbstainCode.SYNDROME_INFERRED` may ever permit auto-approved plan steps without explicit clinician syndrome entry. **Fail-closed default active:** when `abstain_code == SYNDROME_INFERRED`, no step may reach `StepStatus.APPROVED`; maximum permitted step status is `StepStatus.REQUIRES_CLINICIAN_CONFIRMATION`.
- **HD-5 [P1-EVAL] Neural Embedding & Cross-Encoder Model Selection & Licensing (`FG-14`, ADR 0009)**: Choice of offline local embedding model and license review (e.g., BGE-small, MiniLM) for neural dense retrieval and reranking. **Fail-closed default active:** prototype retains pure-Python `CharNgramRetriever` and `LexicalOverlapReranker` with zero network calls and honest naming.
- **HD-6 [P0-CLINICAL] Hard-Ceiling Multiple for Non-Overridable Overdose BLOCK (ENG-04)**: Define hard-ceiling threshold multiple (e.g., requested > 2x ceiling or magnitude tripwire true) at which an overdose transitions from overridable `HIGH` alert to non-overridable `BLOCK` alert. **Fail-closed default active:** `ENG-04` test remains strict `xfail`; overdoses > ceiling currently produce `Severity.HIGH` with mandatory logged clinical justification until human clinical decision is formalized.
- **HD-7 [P0-GOVERNANCE] Clinical Reviewer Sign-Off Procedure & Dual Control for BLOCK Rules**: Clinical governance protocol for onboarded clinician/pharmacist verification of candidate rules, with mandatory dual sign-off (two reviewers or author + reviewer) for non-overridable `Severity.BLOCK` rules. **Fail-closed default active:** no candidate rule is marked `verified: true` without explicit human reviewer ID and verification timestamp.
- **HD-8 [P1-CLINICAL] Reaction Type BLOCK vs HIGH for Unknown Penicillin Reactions (ENG-13)**: Governance decision on whether documented penicillin allergy with `reaction_type: "unknown"` should remain non-overridable `BLOCK` on 1st-gen cephalosporins or convert to `HIGH` (requiring documented clinician override). **Fail-closed default active:** conservative `BLOCK` retained for unknown reaction types.
- **HD-9 [P1-LEGAL] Evidence Corpus Adoption & Repository License Split**: Legal review and boundary specification for bundling openFDA label chunks (Tier 2) and open guideline text (Tier 3: WHO / ICMR). **Fail-closed default active:** synthetic corpus + openFDA only; raw guidelines and index caches git-ignored with scripted ingestion only.
- **HD-10 [P1-EVAL] Neural Dense Model Licensing & Offline Architecture**: Extends HD-5 to establish vetted open-weights embedding models (e.g. BGE-small / MiniLM) and cross-encoders for retrieval surfaces R-2 and R-3. **Fail-closed default active:** lexical implementations remain active with honest naming.
- **HD-11 [P2-CLINICAL] Obstetric Emergency Module Inclusion**: Scope decision on incorporating obstetric emergency rules (e.g., carboprost/ergometrine/oxytocin/MgSO4 contraindications). **Fail-closed default active:** out of scope for baseline emergency triage ruleset.
- **HD-12 [P2-I18N] Hinglish & Indian Brand Scope**: Depth of Hinglish colloquial triage complaint normalization and Indian multi-ingredient FDC mapping. **Fail-closed default active:** alias-level normalization only; no unverified colloquial phrasing triggers clinical routing.
- **HD-13 [P2-OPS] Streamlit UI Lifecycle**: Decision to retain Streamlit interface alongside modern React/FastAPI console. **Fail-closed default active:** Streamlit maintained as internal developer and clinical debugging tool (`tools/tasks.py ui`).

### Active Roadmap (Audit 2026-10-29 Work Packages)

- **[COMPLETED] WP-0: Engine Defect Sweep & Deterministic Safety Interlocks**:
  - Closed ENG-01 (confirmed lookback precedence over missing timestamps).
  - Closed ENG-02 (plan alert deduplication on `(rule_id, frozenset(drug_ids))` preserving proposed drug coverage).
  - Closed ENG-03 (exhaustive dose status handling for `BELOW_MINIMUM` and `MAGNITUDE_WARNING`).
  - Preserved ENG-04 as strict `xfail` pending `HD-6`.
  - Closed ENG-05 (step-keyed dose reports preventing repeat-dose collisions).
  - Closed ENG-07 (relevance-gating skips in Pass 2 plan verification).
  - Closed ENG-08 (fail-closed skip on lookback class omission + data-lint).
  - Added golden isolation harness `only_rules` (65/65 passed).
  - Implemented differential reference interpreter + Hypothesis property suite (1,000 cases, 0 divergences).
- **[NEXT] WP-1: Evaluation Integrity & Falsifiable Benchmarks**:
  - Add random-baseline validity gate to retrieval benchmark (CI failure if random Recall@5 >= 0.6).
  - Separate oracle-routed and unrouted tracks.
  - Implement leave-one-document-out split.
  - Replace git-SHA dependency with content-hash lock file (`dataset.lock`, OPS-02).
  - Generate README and HANDOFF metrics directly from artifact JSON files.
- **WP-2: Schema v2 (Conditions, Labs, Route/Concentration, New Rule Types)**:
  - Add `conditions`, `labs`, `route`, `product_concentration`, `diluent`, and `rate` to schema.
  - Implement 3-valued Kleene condition evaluation and route/concentration interlocks.
- **WP-3: Synthetic Corpus Generator (Tier 1)**:
  - Generate >=40 syndromes covering pediatric/neonate, near-duplicates, and distractors (>=600 chunks).
- **WP-4: Evidence Corpus (Tier 2 - openFDA Drug Labels)**:
  - Rate-limited, cached openFDA label ingestion with SPL section chunking (>=150 generics, >=1,500 chunks).
- **WP-5: Real Dense Retrieval & Reranker**:
  - Deploy vetted offline neural embeddings and cross-encoder behind existing retriever protocol.
- **WP-6: Retrieval Surfaces R-2 (Evidence-for-Alert) & R-3 (Ask-the-Corpus)**:
  - Add label evidence drawer in UI and extractive, cited, abstaining open-domain Q&A endpoint.
- **WP-7: RAG-Grounded Rule Mining Pipeline**:
  - Automated rule proposition from label chunks with deterministic quote, number, and schema validators.
- **WP-8: Rule Catalogue Batches**:
  - Implement candidate rules from catalogue in verified batches with golden and mutation test coverage.
- **WP-9: Real-LLM Hardening & Multi-Model Ablation**:
  - Production provider hardening (timeouts, bounded retries, telemetry) and 3-arm real-model ablation study.
- **WP-10: Indian-Context Layer**:
  - >=150 Indian brand/FDC aliases, Fahrenheit conversion, and localized LASA lookups.
- **WP-11: Security/Ops Hardening & Docs-as-Code**:
  - API rate-limiting, audit head cryptographic anchoring, dependency cleanup, and automated doc sync.
- **WP-12: Interactive Demo & Portfolio Showcase**:
  - 5-minute automated walkthrough, architecture diagrams, and published reliability plots.

### Prioritized Backlog Items

1. **[P0-CLINICAL] Human Clinician Review of Seed Ruleset**: Review and replace `PLACEHOLDER_UNRETRIEVED` provenance on all 10 seed rules with real peer-reviewed literature citations and verified reviewer signoffs.
2. **[P0-CLINICAL] Formulary Ceiling & Dose Sourcing**: Review and source adult/paediatric per-dose, daily maximums, and concentration limits currently marked `status: NEEDS_SOURCE`.
3. **[P0-SAFETY] Golden Set Expansion to 150+ Cases**: Expand `data/golden/shipped_ruleset_cases.yaml` from 60 to ≥150 adversarial, edge-case, and boundary scenarios covering all age groups.
4. **[P1-LEGAL] Real Guideline Ingestion with License Review**: Build an ingestion pipeline for vetted open-access clinical protocols into `data/protocols_real/` with license provenance checks.
5. **[P1-FEATURE] Emergency Severity Index (ESI) Integration**: Integrate deterministic ESI-based 5-level triage category calculation distinct from continuous physiological early-warning score bands.
6. **[P1-SAFETY] Renal & Hepatic Dosing Rules**: Implement GFR and Child-Pugh based dose-adjustment curves and contraindication interlocks.
7. **[P1-LOCAL] Local LLM Mode**: Add support for local offline quantized LLMs (e.g. via Ollama / llama.cpp) using structured JSON output.
8. **[P1-DATA] FHIR R4 Bundle Ingestion**: Ingest standard FHIR R4 `Patient`, `Condition`, `Observation`, and `MedicationStatement` resources directly into `triagerag.contracts.schemas.Patient`.
9. **[P2-I18N] Multilingual & Hinglish Query Normalization**: Expand alias and chief complaint normalization to handle Hinglish and code-switched colloquial descriptions.
10. **[P2-SAFETY] DDI Dataset Evaluation & Licensing Review**: Evaluate standard Drug-Drug Interaction datasets (e.g., DrugBank / openFDA) with strict copyright review before integration.
11. **[COMPLETED in WP2/WP7] Structured Protocol Flowchart Parser**: Implemented `chunk_decision_graph_json()` adapter in `src/triagerag/rag/chunking.py`.
12. **[IN PROGRESS] Retrieval Score Threshold Calibration & ECE Targets (`FG-07`, `HD-3`, ADR 0008)**: Calibrated BM25 score cutoffs on dev split of expanded 224-case benchmark (`calibration_run_CALIB_FG4_DEV_SWEEP_V1.json`). ECE and reliability curves are tracked as observational research metrics pending prospective clinical cohort calibration (`HD-3`).
13. **[P2-EVAL] Real-Model Ablation Study**: Execute full 3-arm ablation with live frontier LLMs (Gemini, Claude, GPT-4) comparing naive generation vs unverified RAG vs TriageRAG verified pipeline.
14. **[P2-FEATURE] Continuous Vital Sign Trend Analysis**: Detect physiological deterioration trends (e.g. delta MAP over 30 mins) rather than static snapshot scores.
15. **[P3-UX] Voice Dictation Normalizer for Bedside Triage**: Add offline Whisper-based transcription pipeline with prompt-injection filtering.
16. **[P3-SAFETY] Multi-Ingredient Combination Titration**: Expand dose engine to evaluate dynamically titrated infusions (e.g. norepinephrine with dextrose carrier) and additive osmolarity.
17. **[P3-SECURITY] Hardware-Backed Cryptographic Audit Signatures**: Support TPM/PKCS#11 key signing for audit chain records in addition to SHA-256 hash chaining.
18. **[P3-FEATURE] Pediatric Weight-Estimation Formula Validation**: Add Broselow tape and Luscombe/Owens formula validation with strict `source: estimated` badging.
19. **[P3-EVAL] Automated Mutation Test Runner in CI**: Integrate continuous mutation testing (`eval/run_mutation.py`) into weekly CI builds to guarantee 100% mutant kill rate for BLOCK/HIGH rules.
20. **[P3-UX] FHIR Export of Verified Plan**: Export approved verified plan steps into standard FHIR `CarePlan` and `MedicationRequest` resources.
21. **[P3-DATA] Cephalosporin R2 Side-Chain Cross-Reactivity Mapping**: Refine beta-lactam cross-reactivity matrix to include R2 side-chain homology in addition to R1 side-chain groupings.
