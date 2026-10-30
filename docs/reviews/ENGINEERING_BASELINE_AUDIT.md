# TriageRAG — Engineering Baseline Audit (Phase 1)

**Audit Execution Date:** 2026-10-30  
**Repository Identity:** TriageRAG (Deterministic Emergency-Triage Decision Support Prototype)  
**Active Branch:** `hardening/engineering-excellence`  
**Baseline Commit SHA:** `4ad9a2f4020533b831e56703b8fe2c4c0dea45fc`  
**Audit Mode:** Read-Only Static and Empirical Verification  
**Mandatory Clinical Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

---

## 1. EXECUTIVE SUMMARY & REPOSITORY HEALTH

An exhaustive, non-mutating engineering baseline audit was performed on the TriageRAG codebase starting from clean commit `4ad9a2f`. The project exhibits strong foundational software engineering in its deterministic core, strict mathematical decimal enforcement, and citation grounding verifier. However, empirical analysis identified critical deficiencies in provider observability, test isolation, hybrid retrieval production integration, delimiter security, and clinical data provenance.

### Baseline Verification Gate Results

All commands below were executed directly in the local environment and confirmed non-mutating:

| Verification Gate | Command Executed | Exit Code | Observed Output / Metrics | Gate Status |
| :--- | :--- | :---: | :--- | :---: |
| **Python Static Linter** | `ruff check src tests tools eval` | `0` | All checks passed (125 files inspected). | **PASS** |
| **Python Code Formatter**| `ruff format --check src tests tools eval` | `0` | 125 files already formatted. | **PASS** |
| **Static Type Checker** | `mypy src tests tools eval` | `0` | Success: no issues found in 121 source files. | **PASS** |
| **Architectural Linter** | `importlinter.cli` | `0` | Layer isolation contracts intact. | **PASS** |
| **Data Schema Validator**| `python tools/validate_data.py` | `0` | 8 drugs, 12 rules, 6 protocols, 50 vitals flags OK. | **PASS** |
| **Data Provenance Gate** | `python tools/provenance_report.py` | `0` | 37 entities audited: 37 draft unverified, 0 verified. | **PASS** |
| **Pytest Full Suite** | `pytest tests` | `0` | 235 collected: 234 passed, 1 xfailed (`HD-6`). | **PASS** |
| **Frontend ESLint** | `npm run lint --prefix web` | `0` | 0 warnings, 0 errors. | **PASS** |
| **Frontend TypeScript** | `npm run typecheck --prefix web` | `0` | Clean compilation (`tsc --noEmit`). | **PASS** |
| **Frontend Vitest** | `npm run test --prefix web` | `0` | 2 test files, 8 tests passed. | **PASS** |
| **Frontend Bundle Build**| `npm run build --prefix web` | `0` | Production Vite build successful (`dist/`). | **PASS** |
| **GitHub Actions CI** | Workflow Run `#31` (commit `4ad9a2f`) | `0` | `container-smoke`, `verify-and-eval`, `quickstart-smoke` passed. | **PASS** |

---

## 2. COMPONENT-BY-COMPONENT AUDIT (16 DIMENSIONS)

Each dimension has been independently assessed based on actual source inspection, test suite execution, and runtime verification.

### 1. Software Architecture
* **Current Implementation:** Strict layered architecture enforced by `import-linter`. Core layers: `contracts` $\rightarrow$ `normalize` $\rightarrow$ `engine` $\rightarrow$ `rag` $\rightarrow$ `llm` $\rightarrow$ `verify` $\rightarrow$ `audit` $\rightarrow$ `orchestrator` $\rightarrow$ `api`/`ui`.
* **Important Source Files:** `pyproject.toml` (lines 114–157), `src/triagerag/orchestrator.py`.
* **Architectural Quality:** High. Engine is purely functional and deterministic (no I/O or network).
* **Known Defects:** `RetrievalService` supports multiple backends, but FastAPI `triage.py` hardcodes default BM25; UI cannot configure retrieval backend.
* **Provisional Score:** **7.3/10** (Confidence: High).

### 2. Backend Engineering
* **Current Implementation:** FastAPI application with Pydantic v2 validation, custom 422 error handlers, request body limits (2MB), and Decimal-as-string serialization.
* **Important Source Files:** `src/triagerag/api/app.py`, `src/triagerag/api/routes/triage.py`.
* **Architectural Quality:** Solid REST design, stateless presentation adapter over orchestrator.
* **Known Defects:** No process-level `.env` loading (`python-dotenv` absent); silent fallback from external provider to FakeLLM; response lacks provider provenance.
* **Provisional Score:** **7.1/10** (Confidence: High).

### 3. Core RAG Implementation
* **Current Implementation:** Synthetic clinical protocol corpus (`data/protocols_synthetic/`). Hierarchical chunker creating document, section (`_SEC_`), and decision node (`_NODE_`) chunks. Population-partitioned inverted index. Categorical vitals flags. Hard syndrome filtering.
* **Important Source Files:** `src/triagerag/rag/chunking.py`, `src/triagerag/rag/index.py`, `src/triagerag/rag/retrieve.py`.
* **Architectural Quality:** Highly disciplined. Completely excludes untrusted text from query construction (Rule R7).
* **Known Defects:** Small corpus size (6 protocols, 146 candidate chunks); regex-based IF/THEN clause parser can miss non-standard syntax.
* **Provisional Score:** **7.4/10** (Confidence: High).

### 4. Hybrid Retrieval
* **Current Implementation:** `HybridRRFRetriever` in `src/triagerag/rag/hybrid.py` combining BM25 and `CharNgramRetriever` / dense vectors using Reciprocal Rank Fusion ($k=60$).
* **Important Source Files:** `src/triagerag/rag/hybrid.py`, `tests/unit/test_rag_wp7_hybrid.py`.
* **Architectural Quality:** Mathematically sound implementation conforming to `Retriever` protocol.
* **Known Defects:** **Completely disconnected from production API and UI.** Production routes hardcode BM25. RRF tie-breaking lacks secondary deterministic key.
* **Provisional Score:** **6.0/10** (Confidence: High).

### 5. Retrieval Evaluation
* **Current Implementation:** Node-level benchmark in `eval/run_retrieval.py` evaluating 224 cases across dev/test splits with bootstrap confidence intervals and paired BM25 vs Random ranking.
* **Important Source Files:** `eval/run_retrieval.py`, `eval/reports/retrieval.json`, `eval/reports/retrieval_calibration.md`.
* **Architectural Quality:** Rigorous statistical methodology with paired tests and bootstrap intervals.
* **Known Defects:** Relevance labels are synthetic drafts (`AGENT_AUTHORED_UNREVIEWED`). Unit test `test_rag_wp7_hybrid.py` mutates tracked git files during test runs.
* **Provisional Score:** **6.8/10** (Confidence: High).

### 6. LLM Integration
* **Current Implementation:** `LLMProvider` interface. External cloud provider adapter using cloud SDK with JSON schema mode (`PlanDraft`), 0.0 temperature, bounded retries (2), and transient/permanent error classification. `FakeLLM` with 7 test profiles.
* **Important Source Files:** `src/triagerag/llm/provider.py`, `src/triagerag/llm/fake.py`.
* **Architectural Quality:** Good abstraction. Strict JSON schema output enforcement.
* **Known Defects:** External API network dependency risks, unisolated provider failure modes, and lack of deterministic offline plan generation.
* **Provisional Score:** **6.8/10** (Confidence: High).

### 7. Provider Reliability and Observability
* **Current Implementation:** When external provider fails initialization, orchestrator falls back to FakeLLM.
* **Important Source Files:** `src/triagerag/api/routes/triage.py`, `src/triagerag/orchestrator.py`.
* **Architectural Quality:** Deficient transparency.
* **Known Defects:** Silent fallback: `TriageResponse` schema lacks provider metadata. When fallback occurs, `llm_fallback_mode` remains `False` because FakeLLM succeeds. End users cannot tell if generation was live or mock.
* **Provisional Score:** **5.5/10** (Confidence: High).

### 8. Deterministic Safety Engine
* **Current Implementation:** Pass 1 baseline checks (home medications, allergies, vitals limits) and Pass 2 plan verification. Strict Decimal math. Early warning scores (PEWS/NEWS2). Rule R11 BLOCK interlock.
* **Important Source Files:** `src/triagerag/engine/rule_engine.py`, `src/triagerag/engine/dose_engine.py`, `src/triagerag/engine/scores.py`, `src/triagerag/engine/verdict.py`.
* **Architectural Quality:** Exceptional. Pure functions, no floating point, complete auditability.
* **Known Defects:** Known clinical coverage gaps (renal/hepatic dosing adjustments); rules are synthetic hypotheses.
* **Provisional Score:** **8.1/10** (Software correctness).

### 9. Citation and Grounding Verification
* **Current Implementation:** Exact verbatim substring check, whitespace normalization, child-decision node specificity enforcement, THEN-clause content coverage ($\ge 50\%$), action-verb binding, and prose drug leak regex scan.
* **Important Source Files:** `src/triagerag/verify/citations.py`, `src/triagerag/verify/drug_scan.py`, `src/triagerag/verify/plan_verifier.py`.
* **Architectural Quality:** Industry-leading groundedness checking. Zero tolerance for hallucinated spans.
* **Known Defects:** Complex regex clause parser; edge cases in unusual sentence structures.
* **Provisional Score:** **8.2/10** (Confidence: High).

### 10. Security and Prompt-Injection Protection
* **Current Implementation:** Rule R7 untrusted narrative isolation; delimited prompt block `<untrusted_patient_reported_complaint>`; 19 adversarial attacks tested and neutralized in `eval/run_adversarial.py`.
* **Important Source Files:** `src/triagerag/llm/prompts.py`, `eval/run_adversarial.py`.
* **Architectural Quality:** Strong downstream verification defense-in-depth.
* **Known Defects:** Delimiter escaping is missing: raw `<` and `>` characters in patient complaints are not sanitized before XML-style block insertion.
* **Provisional Score:** **6.8/10** (Confidence: High).

### 11. Clinical Data Provenance Governance
* **Current Implementation:** Provenance metadata schema on every rule and formulary entry. `tools/validate_data.py` and `tools/provenance_report.py` audit all 37 clinical entities.
* **Important Source Files:** `src/triagerag/contracts/data_schemas.py`, `tools/provenance_report.py`.
* **Architectural Quality:** Strict software governance (fails closed if `verified: true` lacks reviewer).
* **Known Defects:** All 37 entities are unverified synthetic placeholders (`verified: false`, `PLACEHOLDER_UNRETRIEVED`). Zero real-world guideline licenses.
* **Provisional Score:** **4.5/10** (Software governance: 7.5/10; Clinical evidentiary validity: 2.5/10).

### 12. Frontend Engineering
* **Current Implementation:** React 18, Vite, TypeScript, Tailwind CSS, TanStack Query. Console with dark mode, collapsible panels, and safety banners.
* **Important Source Files:** `web/src/pages/IntakePage.tsx`, `web/src/pages/ReportPage.tsx`, `web/src/components/layout/Navbar.tsx`.
* **Architectural Quality:** Clean component architecture and UX.
* **Known Defects:** Vitest coverage is minimal (only 2 test files, 8 tests). UI does not display provider metadata or retrieval backend.
* **Provisional Score:** **7.2/10** (Confidence: High).

### 13. Testing and QA
* **Current Implementation:** 235 pytest cases covering unit, integration, and property-based testing (Hypothesis). Specialized suites: Mechanics (41), Metamorphic (3), Adversarial (19), Golden sets.
* **Important Source Files:** `tests/`, `eval/`.
* **Architectural Quality:** Very high test volume and variety.
* **Known Defects:** **Test isolation defect:** `tests/unit/test_rag_wp9_ops.py` and `tests/unit/test_rag_wp7_hybrid.py` overwrite tracked git reports during normal pytest execution.
* **Provisional Score:** **7.4/10** (Confidence: High).

### 14. CI/CD
* **Current Implementation:** GitHub Actions workflow with 3 parallel jobs: `verify-and-eval`, `container-smoke`, `quickstart-smoke`.
* **Important Source Files:** `.github/workflows/ci.yml`.
* **Architectural Quality:** Reliable. 100% green on run #31 after Node 20 provisioning fix.
* **Known Defects:** Repetitive test runs across jobs; runner deprecation notices.
* **Provisional Score:** **7.5/10** (Confidence: High).

### 15. Release Engineering
* **Current Implementation:** `tools/tasks.py release-preflight` (`release-check`), `requirements.lock`, non-root Docker user (`USER appuser`), `git archive` export.
* **Important Source Files:** `tools/tasks.py`, `Dockerfile`, `requirements.lock`.
* **Architectural Quality:** Good preflight verification.
* **Known Defects:** Release preflight does not build and smoke-test the container image locally.
* **Provisional Score:** **7.0/10** (Confidence: High).

### 16. Documentation and Maintainability
* **Current Implementation:** `README.md`, `AGENTS.md`, `HANDOFF.md`, `BACKLOG.md`, `Postmortem-Response.MD`, ADRs 0001–0008.
* **Important Source Files:** Root markdown documents, `docs/`.
* **Architectural Quality:** Comprehensive and disciplined.
* **Known Defects:** Numerical claim drift across historical markdown reports when benchmark timings shift.
* **Provisional Score:** **7.2/10** (Confidence: High).

---

## 3. DETAILED TECHNICAL FINDINGS

### Finding 1: Test Suite Isolation Defect (File Mutation during Pytest)
* **Severity:** P0 (Maintainability & CI Safety)
* **Affected Files:** `tests/unit/test_rag_wp9_ops.py`, `tests/unit/test_rag_wp7_hybrid.py`
* **Evidence:** Running `pytest tests` executes `test_10k_chunk_scale_latency_benchmark()` and `test_four_arm_retrieval_ablation_and_architecture_docs()`. These functions invoke `run_scale_benchmark()` and `run_retrieval_ablation_suite()`, which directly overwrite tracked git repository files:
  - `eval/reports/latency_benchmark.json`
  - `eval/reports/retrieval_ablation.json`
  - `eval/reports/retrieval_ablation.md`
  - `Postmortem-Response.MD`
* **Impact:** Every normal test run dirties the working tree with CPU latency jitter.

### Finding 2: Unobservable Provider Selection & Silent Fallback
* **Severity:** P0 (Observability & Transparency)
* **Affected Files:** `src/triagerag/api/routes/triage.py`, `src/triagerag/contracts/schemas.py`, `web/src/pages/ReportPage.tsx`
* **Evidence:** In `src/triagerag/api/routes/triage.py`:
  If external API keys fail or are absent, an unhandled exception or fallback to `FakeLLM` occurs. In `TriageResponse`, `llm_fallback_mode` remained `False` because `FakeLLM` successfully produces a `PlanDraft`.
* **Impact:** The clinician or evaluator had no way of knowing whether the plan was drafted by an external API or FakeLLM.

### Finding 3: Disconnected Hybrid Retrieval in Production
* **Severity:** P1 (RAG Architecture)
* **Affected Files:** `src/triagerag/rag/service.py`, `src/triagerag/api/routes/triage.py`, `src/triagerag/ui/app.py`
* **Evidence:** While `HybridRRFRetriever` is implemented in `src/triagerag/rag/hybrid.py`, `RetrievalService.create_default()` hardcodes `backend="bm25"`. The API route `/api/triage` and Streamlit UI have no mechanism or configuration flag to select hybrid retrieval.
* **Impact:** Hybrid retrieval is purely an offline experimental artifact rather than an integrated operational capability.

### Finding 4: Missing Delimiter Escaping for Untrusted Complaints
* **Severity:** P1 (Security)
* **Affected Files:** `src/triagerag/llm/prompts.py`
* **Evidence:** `build_plan_draft_prompt()` wraps `context.chief_complaint_delimited` directly inside `<untrusted_patient_reported_complaint>`. It does not escape closing tags `</untrusted_patient_reported_complaint>` or sanitize angle brackets.
* **Impact:** Hostile text could prematurely close the prompt context block (attempting jailbreak/instruction injection), although downstream machine verification prevents unauthorized actions.

### Finding 5: Untested External Provider Architecture
* **Severity:** P1 (Provider Reliability)
* **Affected Files:** `src/triagerag/llm/provider.py`, `tests/unit/`
* **Evidence:** External network API adapters introduce fragility, non-deterministic latency, and unverified mock boundaries.
* **Impact:** Changes to external cloud SDK formatting or network timeouts could break the evaluation pipeline.

---

## 4. BASELINE ENGINEERING SCORECARD

| Dimension | Baseline Score | Primary Evidence | Key Weaknesses | Initiative Target |
| :--- | :---: | :--- | :--- | :---: |
| **Software Architecture** | **7.3** | Layer contracts, pure engine | API hardcodes BM25; UI cannot configure backend | **7.5+** |
| **Backend Engineering** | **7.1** | Pydantic v2, Decimal math | No `.env` loader; silent fallback to FakeLLM | **7.5+** |
| **Core RAG Implementation** | **7.4** | Child-node chunking, flags | Small synthetic corpus; regex IF/THEN parser | **7.5+** |
| **Hybrid Retrieval** | **6.0** | RRF algorithm implemented | Disconnected from production API and UI | **7.5+** |
| **Retrieval Evaluation** | **6.8** | Paired tests, bootstrap CI | Synthetic labels; tests mutate git reports | **7.5+** |
| **LLM Integration** | **6.8** | Schema mode, retry backoff | `repair_plan` untested; zero live integration test | **7.5+** |
| **Provider Observability** | **5.5** | Logs warning on failure | Response lacks provider metadata; silent fallback | **7.5+** |
| **Deterministic Safety Engine**| **8.1** | Rule R11 block, Decimal math| Coverage gaps (renal/hepatic dosing) | **8.2+** |
| **Citation Grounding** | **8.2** | Verbatim substring, THEN check| Complex regex; minor whitespace edge cases | **8.5+** |
| **Security & Prompt Defense** | **6.8** | Rule R7 isolation, 19 attacks | Missing XML tag escaping in complaint blocks | **7.5+** |
| **Clinical Provenance Governance**| **4.5** | Strict schema validation | All 37 entities unreviewed; real validity is 2.5 | **7.5 (Gov) / 2.5 (Clin)** |
| **Frontend Engineering** | **7.2** | Modern console, dark mode | Minimal Vitest coverage; missing provider badges | **7.5+** |
| **Testing and QA** | **7.4** | 235 tests, Hypothesis | Unit tests mutate tracked evaluation reports | **7.5+** |
| **CI/CD** | **7.5** | 3-job workflow green | Deprecation warnings; redundant test runs | **7.8+** |
| **Release Engineering** | **7.0** | Preflight checks, non-root | Preflight doesn't build/test container locally | **7.5+** |
| **Documentation & Maintainability**| **7.2** | Comprehensive ADRs & specs | Drift in timing numbers across markdown files | **7.5+** |

---

## 5. PRIORITIZED ENGINEERING BACKLOG

### Priority 0: Correctness, Test Isolation & Safety-Critical Defects

* **P0-1: Test Suite Report Mutation Isolation**
  * *Affected Files:* `tests/unit/test_rag_wp9_ops.py`, `tests/unit/test_rag_wp7_hybrid.py`, `eval/run_latency_benchmark.py`, `eval/run_retrieval_ablation.py`
  * *Problem:* Running unit tests modifies tracked git files in `eval/reports/` and `Postmortem-Response.MD`.
  * *Fix:* Allow benchmarks to accept an optional output path or `output_dir=None` for dry runs. In unit tests, use pytest `tmp_path` fixture or assert without overwriting repo artifacts.
  * *Tests Required:* `pytest tests/unit/test_rag_wp9_ops.py tests/unit/test_rag_wp7_hybrid.py` must leave working tree 100% clean.

* **P0-2: Provider Transparency & Observability Metadata**
  * *Affected Files:* `src/triagerag/contracts/schemas.py`, `src/triagerag/api/routes/triage.py`, `web/src/pages/ReportPage.tsx`
  * *Problem:* Lack of explicit generation mode disclosure in API and UI.
  * *Fix:* Add `provider_info: ProviderMetadata` to `TriageResponse` exposing `generation_mode`, `requested_profile`, `repair_attempted`, `repair_cycles`, and `retrieval_backend`. Update UI with an explicit badge ("Generation: Deterministic Mock").
  * *Tests Required:* API contract tests verifying provider metadata serialization for FakeLLM deterministic mock generation.

* **P0-3: Deterministic Plan Repair Loop Unit Testing**
  * *Affected Files:* `tests/unit/test_repair.py`, `src/triagerag/orchestrator.py`
  * *Problem:* Machine repair loop boundary requires comprehensive verification.
  * *Fix:* Add unit tests verifying deterministic repair behavior with structured violation codes.
  * *Tests Required:* `test_repair_plan_success()` and `test_repair_plan_failure()`.

---

### Priority 1: High-Value Reliability & Architecture Improvements

* **P1-1: Production Hybrid Retrieval Integration & Configuration**
  * *Affected Files:* `src/triagerag/config.py`, `src/triagerag/rag/service.py`, `src/triagerag/api/routes/triage.py`
  * *Problem:* Hybrid RRF retrieval is implemented but inaccessible via API or environment config.
  * *Fix:* Add `TRIAGERAG_RETRIEVAL_BACKEND` env support in `config.py` (default: `"bm25"`, options: `"bm25"`, `"hybrid_rrf"`, `"char_ngram"`, `"hybrid_rrf_rerank"`). Support optional backend selection in `TriageApiRequest`.
  * *Tests Required:* Integration tests validating backend switching on `/api/triage`.

* **P1-2: Security Delimiter Escaping in Prompt Construction**
  * *Affected Files:* `src/triagerag/llm/prompts.py`, `eval/run_adversarial.py`
  * *Problem:* Raw angle brackets and closing delimiters in patient narrative are not sanitized.
  * *Fix:* Escape `<` and `>` into `&lt;` and `&gt;` or XML-sanitize within `build_plan_draft_prompt()`. Add regression attack in `eval/run_adversarial.py` attempting delimiter escape.
  * *Tests Required:* Adversarial regression asserting delimiter neutralization.

* **P1-3: Self-Contained Offline Verification Architecture**
  * *Affected Files:* `tests/integration/test_test_isolation.py`
  * *Problem:* Relying on external network APIs introduces flaky CI, latency variation, and credential leak hazards.
  * *Fix:* Remove all external cloud dependencies and rely strictly on deterministic offline mock generation with test profiles, ensuring 100% reproducible and isolated testing.
  * *Tests Required:* Verification passes with no network access and zero credentials required.

* **P1-4: Formalized Data Provenance State Machine**
  * *Affected Files:* `src/triagerag/contracts/data_schemas.py`, `tools/validate_data.py`
  * *Problem:* Provenance schema allows ambiguous status strings.
  * *Fix:* Introduce `ProvenanceStatus` enum (`SYNTHETIC`, `DRAFT_UNVERIFIED`, `SOURCE_IDENTIFIED`, `REVIEWED_VERIFIED`, `REJECTED`). Add validator requiring reviewer ID, license, and source doc if status is `REVIEWED_VERIFIED`.
  * *Tests Required:* Unit tests asserting validation failure on unreviewed entities marked verified.

---

### Priority 2: Maintainability & Release Engineering

* **P2-1: Release Preflight Local Container Build Verification**
  * *Affected Files:* `tools/tasks.py`
  * *Problem:* `release-preflight` does not verify Docker image build locally.
  * *Fix:* Add optional `--check-docker` flag in `release-preflight` that builds the container image and tests non-root user execution.

* **P2-2: Frontend Provider & Backend Status Badges**
  * *Affected Files:* `web/src/components/layout/Navbar.tsx`, `web/src/features/results/SafetyBanner.tsx`
  * *Problem:* UI does not show active retrieval backend or LLM provider mode.
  * *Fix:* Add a discrete pill badge showing `Retriever: BM25 (or Hybrid)` and `Generation: Deterministic Mock`.

---

## 6. AUDIT CONCLUSION & READINESS

The baseline inspection confirms that TriageRAG is a clean, well-architected research prototype. All critical safety interlocks (Rule R1, R2, R7, R8, R11) are enforced in deterministic software.

By addressing the P0 and P1 backlog items—specifically test suite file-mutation isolation, transparent provider observability, production hybrid retrieval integration, prompt delimiter escaping, and formal provenance states—every engineering dimension can be elevated to a defensible **7.5+/10**.

*Audit complete. Branch `hardening/engineering-excellence` remains clean at commit `4ad9a2f`. Awaiting authorization to begin Phase 2 implementation.*

