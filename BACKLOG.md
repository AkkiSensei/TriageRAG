# TriageRAG Backlog

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

Prioritized engineering and clinical verification backlog (ordered by safety priority):

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
11. **[P2-RAG] Structured Protocol Flowchart Parser**: Convert visual emergency clinical algorithms/flowcharts into deterministic decision-tree representations.
12. **[P2-EVAL] Retrieval Score Threshold Calibration**: Empirically calibrate BM25 and dense retrieval score cutoffs on clinical query distributions to minimize abstain false-positives while preventing hallucinated retrievals.
13. **[P2-EVAL] Real-Model Ablation Study**: Execute full 3-arm ablation with live frontier LLMs (Gemini, Claude, GPT-4) comparing naive generation vs unverified RAG vs TriageRAG verified pipeline.
14. **[P2-FEATURE] Continuous Vital Sign Trend Analysis**: Detect physiological deterioration trends (e.g. delta MAP over 30 mins) rather than static snapshot scores.
15. **[P3-UX] Voice Dictation Normalizer for Bedside Triage**: Add offline Whisper-based transcription pipeline with prompt-injection filtering.
16. **[P3-SAFETY] Multi-Ingredient Combination Titration**: Expand dose engine to evaluate dynamically titrated infusions (e.g. norepinephrine with dextrose carrier) and additive osmolarity.
17. **[P3-SECURITY] Hardware-Backed Cryptographic Audit Signatures**: Support TPM/PKCS#11 key signing for audit chain records in addition to SHA-256 hash chaining.
18. **[P3-FEATURE] Pediatric Weight-Estimation Formula Validation**: Add Broselow tape and Luscombe/Owens formula validation with strict `source: estimated` badging.
19. **[P3-EVAL] Automated Mutation Test Runner in CI**: Integrate continuous mutation testing (`eval/run_mutation.py`) into weekly CI builds to guarantee 100% mutant kill rate for BLOCK/HIGH rules.
20. **[P3-UX] FHIR Export of Verified Plan**: Export approved verified plan steps into standard FHIR `CarePlan` and `MedicationRequest` resources.
21. **[P3-DATA] Cephalosporin R2 Side-Chain Cross-Reactivity Mapping**: Refine beta-lactam cross-reactivity matrix to include R2 side-chain homology in addition to R1 side-chain groupings.
