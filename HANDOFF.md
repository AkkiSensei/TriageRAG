# TriageRAG Session Handoff

> **Disclaimer:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Current State

- **Current Status:** Part A Iterative Debugging (`debug-complete`), Part B React Frontend Console (`fe-gate-1` through `fe-gate-7`), Part C RAG Postmortem Hardening (`rag-wp0` through `rag-wp9`), and Part D Fix Gates `fg-0` (Re-baseline), `fg-1` (Grounding Soundness), `fg-2` (Clinical Inputs Fail Closed), and `fg-3` (Abstention Logic & Context Hygiene: FG-03, FG-05, FG-15, HD-4) **COMPLETE**. Next gate: `fg-4` (Evaluation That Can Fail: FG-06, FG-07, HD-3).
- **Verification:** All gates green:
  - 171/171 Pytest tests green (including unit, integration, property, UI smoke, safety boundary, WP0–WP9 RAG suites, FG-1 grounding suite, FG-2 clinical inputs suite, and FG-3 abstention/context suite).
  - 8/8 Vitest frontend unit & component tests green.
  - 51/51 mutants killed (100% kill score: 12 rule mutants + 39 code mutants, including M34–M39).
  - 65/65 Golden cases green (100%).
  - 41/41 Mechanics cases green (100%).
  - 3/3 Metamorphic transformations green.
  - 19/19 Adversarial prompt injection & citation laundering cases neutralized (0 approved).
  - 160-case WP5 Node-Level Retrieval Benchmark green (100.0% Test Node Recall@5, 0.0000 Wrong-Protocol Rate, 100.0% Abstain Accuracy).
  - 10,000-chunk Synthetic Scale Benchmark green (`p95 = 5.648 ms < 50.0 ms`).
  - 0 lint / format errors (Python ruff & TypeScript eslint).
  - 0 type errors (Python mypy strict & TypeScript tsc).
  - 0 import isolation contract violations (import-linter).
  - Vite production build succeeds with clean chunking (~293KB, well below 2MB threshold).

## Architecture Highlights

1. **Part A: Master Debugging & Mutation Hardening (tagged `debug-complete`):**
   - 40-mutant kill suite (`eval/run_mutation.py`) covering verdict lattice, lookbacks, withhold exemptions, citation groundings, drug-scan tokens, population filters, BLOCK override guards, dose math, and cryptographic audit.
   - Bounded 1-attempt LLM repair loop (`src/triagerag/llm/repair.py`).
   - Deterministic execution with pure clocks (`src/triagerag/orchestrator.py`).
   - Strict Decimal math with 10x/1000x tripwires (`src/triagerag/engine/dose.py`).

2. **Part B: TriageRAG Console (tagged `fe-gate-1` through `fe-gate-7`):**
   - **FastAPI Presentation Adapter (`src/triagerag/api/`):** REST API with typed Pydantic models matching core domain contracts, exact string Decimal preservation, and OpenAPI schema generation (`web/openapi/openapi.json`).
   - **Modern Clinical Console (`web/`):** Built with React 18, TypeScript, Tailwind CSS, Vite, Lucide React, and React Query.
   - **React Bits Integration with Strict Safety UX Boundaries (ADR 0005):**
     - Decorative/educational micro-animations (`Particles`, `SplitText`, `BlurText`, `ShinyText`, `Magnet`, `SpotlightCard`, `CountUp`, `ClickSpark`) used in hero, navigation, and metrics.
     - **Inviolable S1 UX Guard:** Safety banners, alerts, blocked drugs, skipped checks, and disclaimers are **NEVER** animated, delayed, or obscured.
     - **Accessibility Guard:** `prefers-reduced-motion` and global user toggle (`useMotionOk()`, `<Motion>`) disable all animations instantly.
   - **Clinical Features:**
     - `PatientIntakeForm`: Tri-state uncertainty inputs (`measured`, `estimated`, `unknown`), golden scenario loader, and quarantined untrusted complaint box.
     - `SafetyBanner`: Static high-contrast banner with qualified wording (`CHECKED CLEAR (ruleset coverage: N active rules)`); never renders bare "CLEAR".
     - `ScoreCard`: Physiological early warning score with exact subscores and clinical band enums (`RED`, `ORANGE`, `YELLOW`, `GREEN`, `UNSCORED`).
     - `AlertsList`: Visual severity hierarchy, strikethrough for blocked drugs, and strict prohibition of BLOCK overrides.
     - `OverrideModal`: Audit-logged justification workflow for HIGH alerts requiring >= 15 character rationale.
     - `RedTeamPage`: Adversarial testing playground simulating prompt injections and demonstrating R7 engine isolation and R1 plan verification.
     - `RulesetPage` & `ProtocolsPage`: Searchable registries with provenance drawers and synthetic corpus watermarks.
     - `EvidencePage`: Live metrics dashboard displaying mutant matrices and ablation results.
     - `AuditPage`: SHA-256 Merkle audit trail viewer with one-click cryptographic chain verification.
     - `ErrorBoundary`: Fail-closed React component boundary preventing inconsistent clinical UI rendering upon unexpected exceptions.

## Verification Metrics Summary

| Verification Suite | Scope | Target | Result | Status |
|:---|:---|:---:|:---:|:---:|
| **Python Linters** | Ruff check & format | 0 warnings | Clean | PASS |
| **Python Typing** | Mypy strict mode | 0 errors | Clean | PASS |
| **Layer Contracts** | Import-linter | 0 violations | Clean | PASS |
| **Backend Tests** | Pytest unit, integration, property | 100% | 131/131 passed | PASS |
| **Safety Boundary Tests** | AST scans & rule checks | 100% | 4/4 passed | PASS |
| **Golden Ruleset** | Shipped clinical cases | 100% | 65/65 passed | PASS |
| **Mechanics Suite** | Edge cases & unit trips | 100% | 41/41 passed | PASS |
| **Metamorphic Suite** | Equivalence transformations | 100% | 3/3 passed | PASS |
| **Adversarial Suite** | Prompt injection attacks | 100% | 9/9 passed | PASS |
| **Mutation Testing** | Code & rule mutant kill rate | 100% | 45/45 killed | PASS |
| **Retrieval Benchmark** | 160-case node-level (98 dev / 62 test) | R@5 >= 90%, WrongProto == 0 | 100% R@5, 0.0 WrongProto | PASS |
| **Scale Latency** | 10,000-chunk lexical search | p95 < 50 ms | p95 = 5.65 ms | PASS |
| **Frontend Linters** | ESLint with strict safety rules | 0 warnings | Clean | PASS |
| **Frontend Typing** | TypeScript (`tsc --noEmit`) | 0 errors | Clean | PASS |
| **Frontend Tests** | Vitest unit & component specs | 100% | 8/8 passed | PASS |
| **Production Build** | Vite production bundle | < 2 MB | ~293 KB | PASS |

## Verification & Execution Commands

```bash
# Full backend & evaluative verification
python tools/tasks.py verify

# Full frontend verification (lint, typecheck, vitest, build)
python tools/tasks.py web-verify

# Run mutation testing suite (40 mutants)
python eval/run_mutation.py

# Launch FastAPI backend API (port 8000)
python tools/tasks.py api

# Launch React frontend dev server (port 5173)
python tools/tasks.py web-dev

# Launch Streamlit fallback UI
python tools/tasks.py ui
```
