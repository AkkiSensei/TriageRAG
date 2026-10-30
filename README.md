# 🩺 TriageRAG: Deterministic Emergency Decision Support

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React + Vite](https://img.shields.io/badge/React_18-Vite-61DAFB.svg?style=for-the-badge&logo=react)](https://vitejs.dev)
[![CI](https://github.com/AkkiSensei/TriageRAG/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AkkiSensei/TriageRAG/actions)
[![Mutant Kill Rate](https://img.shields.io/badge/Mutation%20Score-52%2F52%20(100%25)-purple.svg?style=for-the-badge)](https://github.com/AkkiSensei/TriageRAG)
[![Math Precision](https://img.shields.io/badge/Precision-Exact%20Decimal%20Only-orange.svg?style=for-the-badge)](https://github.com/AkkiSensei/TriageRAG)

<br/>

**Code decides. The LLM explains.**

*An emergency clinical decision support system that never lets a language model make safety-critical decisions.*

[Key Features](#-the-core-breakthrough) • [Live Clinical Flow](#-the-2-page-clinical-workflow) • [Safety Architecture](#-safety-architecture) • [Evidence & Benchmarks](#-empirical-benchmarks) • [Quickstart](#-quickstart)

</div>

---

## ⚡ The Core Breakthrough

Most medical AI prototypes pipe patient data into an LLM and pray it doesn’t hallucinate a lethal dosage or overlook a fatal drug interaction.

**TriageRAG flips this upside down.**

Safety rules, physiological scores (NEWS2), dose arithmetic, and contraindication interlocks are executed **strictly in pure, deterministic Python code**. The LLM is used **only** as an extractive draftsman to propose protocol text from retrieved guidelines—and every single word it drafts must pass a **rigorous machine verification gate** before a clinician ever sees it.

```
       ┌────────────────────────────────────────────────────────┐
       │             Structured Synthetic Patient               │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │             Pass 1: Deterministic Engine               │
       │  • NEWS2 Early Warning Score (with AVPU+C confusion)   │
       │  • Absolute Drug-Drug Interlocks (Sildenafil + Nitrate)│
       │  • Exact Decimal Math with 10x Magnitude Tripwires     │
       └─────────────┬────────────────────────────┬─────────────┘
                     │                            │
       Formulary Minus Blocked Drugs       Vitals-Derived Flags
                     │                            │
                     ▼                            ▼
  ┌──────────────────────────────────────┐     ┌────────────────────────────────┐
  │     Offline Clinical Protocol RAG    │     │  Quarantined Triage Narrative  │
  │  • Hard Population Isolation (Adult) │     │  • Zero HTML injection allowed │
  │  • Atomic IF/THEN Decision Nodes     │     │  • Isolated from engine paths  │
  └──────────────────┬───────────────────┘     └───────────────┬────────────────┘
                     │                                         │
                     └───────────────────┬─────────────────────┘
                                         ▼
                       ┌──────────────────────────────────┐
                       │        LLM Plan Drafter          │
                       │  • Generates PlanDraft JSON      │
                       │  • Allowed drug IDs only         │
                       │  • Verbatim chunk citations (R3) │
                       └─────────────────┬────────────────┘
                                         │
                                         ▼
                       ┌──────────────────────────────────┐
                       │    Pass 2: Machine Verification  │
                       │  • Groundedness citation check   │
                       │  • Prose drug leak scanner       │
                       │  • Withhold semantics preserved  │
                       │  • Structured repair feedback    │
                       └─────────────────┬────────────────┘
                                         │
                                         ▼
                       ┌──────────────────────────────────┐
                       │    EngineReport & Audit Chain    │
                       │  • Safety Verdict Banner         │
                       │  • Fail-closed UNVERIFIED        │
                       │  • SHA-256 Hash-Chained Audit Log│
                       └──────────────────────────────────┘
```

---

## 🛡️ Generic Medical AI vs. TriageRAG

| Safety Concern | Generic Medical LLM Chatbot | TriageRAG Decision Support |
|:---|:---|:---|
| **Drug Contraindications** | "I advise caution" (still outputs drug order) | 🛑 **Absolute BLOCK** (hard interlock, zero override code path) |
| **Dosing Calculations** | Binary float arithmetic (`84.7` becomes `84.7000000001`) | 📐 **Exact Decimal arithmetic** with 10x / 1000x tripwire guards |
| **Missing Patient Data** | Hallucinates or assumes "normal" defaults | ❓ **Fails Closed to `UNVERIFIED`** (flags missing vitals explicitly) |
| **Hallucinated Protocol Steps** | Invents ungrounded emergency procedures | 🔍 **Verbatim Chunk Citations** verified against guideline text |
| **Adversarial Prompt Injection** | Leaks instructions via patient chief complaint | 🛡️ **Quarantined narrative**; never touches decision rules |
| **Clinician Accountability** | Opaque black-box reasoning | ⛓️ **Cryptographic SHA-256 Hash-Chained Audit Log** on every run |

---

## 🖥️ The 2-Page Clinical Workflow

Designed like a clean medical workstation (**Linear meets Epic/Amboss**) with zero SaaS bloat, zero cyberpunk gimmicks, and pure clinical clarity.

### 1️⃣ Page 1: Patient Intake Station (`/intake`)
* **1-Click Reference Cases:** Instantly test live scenarios:
  * 🛑 **Case 1 (BLOCK):** Acute Coronary Syndrome + Sildenafil within 24h *(Fatal Vasodilation Hazard)*
  * ⚠️ **Case 2 (HIGH):** Pediatric Sepsis + Penicillin Allergy *(Cephalosporin Cross-Reactivity)*
  * ❓ **Case 3 (UNVERIFIED):** Missing Renal / Vitals Data *(Fail-Closed Safety Interlock)*
  * ✅ **Case 4 (CLEAR):** Acute Asthma Inhalation Protocol *(Salbutamol Inhalation)*
* **Demographics & Physical Profile:** Age, Sex, Weight (kg), and biological invariant locking (male pregnancy strictly locked to `No (N/A)`).
* **7 Measured Physiological Vitals:** Heart Rate, Blood Pressure (SBP/DBP), Respiratory Rate, SpO2 (%), Temperature (°C), **Capillary Blood Glucose (mg/dL)**, and AVPU+C Consciousness.
* **Home Medications & Allergies:** Formulary autocomplete with exact **Last Taken Time Windows** (`12h`, `24h`, `48h`, `72h ago`) mapped directly to lookback interlocks.

### 2️⃣ Page 2: Clinical Decision & Protocol Report (`/report`)
* **Patient Wristband Summary:** Compact bedside banner showing age, weight, presenting syndrome, home meds, and allergies.
* **Qualified Safety Verdict:** Prominent banner with full ruleset coverage notice (**never** bare `"CLEAR"`).
* **NEWS2 / PEWS Physiological Score Card:** Calculated total score, clinical risk band, and breakdown across all parameters.
* **Safety Alerts & Contraindications:** Detailed target agents, clinical consequences, and mandatory actions.
* **Recommended Protocol Orders:** Step-by-step verified clinical orders with requested dose, formulary ceiling bounds, and expandable verbatim guideline quotes.
* **Cryptographic SHA-256 Audit Seal:** Verifiable tamper-evident SHA-256 sequential hash chain recording each assessment, override, and decision step.

---

## 🔬 Safety Principles in Action

### 1. Fail Closed (Rule R2)
> *"No rule fired" means "no rule in this ruleset fired" — not "safe".*

If a patient's allergy reaction type, pregnancy status, or required vital sign is unknown or missing, the engine **refuses to clear the patient**. It emits an `UNVERIFIED` verdict and lists the exact missing fields so the clinical team knows what to measure before proceeding.

### 2. No Override of BLOCK (Rule R11)
Certain drug-drug combinations (such as PDE5-inhibitors and nitrates, which trigger refractory, fatal hypotension) carry an **inviolable `BLOCK` severity**.
* No code path exists in the entire engine or API to approve or override a `BLOCK` step.
* `HIGH` severity alerts (e.g. antibiotic cross-reactivity) require a clinician ID and minimum 15-character clinical rationale recorded directly into the audit chain.

### 3. Exact Decimal Math & Magnitude Tripwires (Rule R8)
* All pediatric and weight-based doses (mg/kg, mcg/kg) are calculated using pure `Decimal` arithmetic.
* Every dose is cross-checked against formulary minimums, per-dose maximums, and daily ceilings.
* A 10x magnitude tripwire flags ten-fold dosage errors as Severity.HIGH (DOSE_MAGNITUDE_WARNING), requiring mandatory clinician justification and audit logging before approval.

---

## 📊 Empirical Benchmarks

The entire system is continuously measured across seven automated verification and mutation suites:

```
======================================================================
  SUITE NAME               SCOPE & OBJECTIVE             RESULT
======================================================================
  Shipped Golden Cases     65/65 Ruleset Cases (isolated)100% PASSED
  Mechanics Suite          41/41 Edge-Case Patients      100% PASSED
  Metamorphic Invariance   3/3 Equivalence Transforms    100% PASSED
  Adversarial Injection    19/19 Hijacks & Laundering    100% BLOCKED
  Mutation Kill Score      52/52 Code & Rule Mutants     100% KILLED
  Differential Property    1,000 Hypothesis Permutations 100% GREEN (0 diff)
  Retrieval: Routed Track  41 Test Cases (Syndrome Given)100% Recall@5 (0.73 MRR)
  Retrieval: Unrouted Track15 Test Cases (Vitals Only)   0.0% Recall@1 (Fail-Closed HD-1)
  Retrieval: Overall Test  56 Test Positive Cases        73.21% R@5 [60.7, 83.9]
  Hard-Negative Abstention 14 Hard-Negative Cases        100% ABSTAINED (0 wrong proto)
  Pytest Test Suite        235 Collected Tests           234 PASSED, 1 XFAIL (HD-6)
======================================================================

> **Evaluation Honesty & Baseline Note:**
> - **Routed Retrieval Track:** 100% Recall@5 is observed on syndrome-provided cases (ranking protocol chunks within known syndrome). A paired candidate-pool random ranker achieves 95.44% Recall@5 and 26.44% Recall@1, demonstrating BM25's 2.0x ranking superiority on Top-1 (52.78% vs 26.44%, paired delta +26.33 pts [95% CI: 9.75, 42.56]) across the exact same query cases and candidate pools.
> - **Unrouted Retrieval Track:** Achieves 0.0% Recall on vitals-only cases because physiological flag thresholds are unverified (marked status: NEEDS_SOURCE under fail-closed governance HD-1), safely abstaining rather than hallucinating unvalidated protocol recommendations.
> - **Benchmark Labels:** Evaluated on synthetic regression fixtures marked `AGENT_AUTHORED_UNREVIEWED` pending external clinician panel review.
```

---

## 🚀 Quickstart

### Prerequisites
* Python 3.11+
* Node.js 18+ (for building the React frontend)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/AkkiSensei/TriageRAG.git
cd TriageRAG

# 2. Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
.venv\Scripts\activate          # On Windows

# 3. Install backend dependencies
pip install -e ".[dev]"

# 4. Install and build frontend
python tools/tasks.py web-install
python tools/tasks.py web-build
```

### Running Locally

```bash
# Start the full-stack server (FastAPI + React SPA)
python tools/tasks.py api
```

Visit [`http://127.0.0.1:8000`](http://127.0.0.1:8000) in your browser.

### Running Full Verification Gates

```bash
# Run all linters, typechecks, Pytest, and golden evaluation suites
python tools/tasks.py verify

# Run all 7 empirical evaluation suites (mutation, metamorphic, adversarial, RAG)
python tools/tasks.py eval all

# Run full frontend verification (ESLint, TypeScript, Vitest, Vite build)
python tools/tasks.py web-verify
```

---

## 📂 Project Architecture

```
TriageRAG/
├── data/
│   ├── formulary/              # Structured drug YAMLs (dosages, ceilings, classes)
│   ├── rules/                  # Clinical safety rules (DDIs, vitals interlocks, allergies)
│   ├── scoring/                # Early-warning scoring tables (NEWS2, PEWS)
│   └── protocols_synthetic/    # Synthetic, un-dosed emergency clinical protocols
├── src/triagerag/
│   ├── engine/                 # Pure deterministic safety engine
│   │   ├── rule_engine.py      # Two-pass clinical rule evaluator
│   │   ├── dose_engine.py      # Exact Decimal dose verification & ceilings
│   │   ├── scores.py           # NEWS2 / PEWS early-warning scoring
│   │   └── registry.py         # Immutable in-memory clinical knowledge store
│   ├── rag/                    # Protocol retrieval pipeline
│   │   ├── chunking.py         # Atomic IF/THEN decision node chunker
│   │   ├── index.py            # Partitioned BM25 with acronym expansion
│   │   └── retrieve.py         # Structured query builder & hard population filter
│   ├── llm/                    # Protocol plan drafting & repair
│   │   ├── fake.py             # Deterministic FakeLLM testing profiles
│   │   ├── gemini.py           # Google Gemini provider (JSON schema output)
│   │   └── repair.py           # Structured machine repair loop
│   ├── verify/                 # Pass 2 machine verification
│   │   ├── plan_verifier.py    # Order validation lattice & step status
│   │   ├── citations.py        # Verbatim chunk substring verification
│   │   └── drug_scan.py        # Prose drug leak scanner
│   ├── audit/                  # Cryptographic audit logging
│   │   └── chain.py            # SHA-256 append-only hash chain
│   └── api/                    # FastAPI presentation layer
├── web/                        # React 18 + Vite frontend
│   └── src/
│       ├── pages/
│       │   ├── IntakePage.tsx  # Page 1: Patient intake workstation
│       │   └── ReportPage.tsx  # Page 2: Clinical decision & protocol report
│       ├── features/intake/    # Patient form & 1-click showcase selector
│       └── features/results/   # SafetyBanner, ScoreCard, VerifiedPlanView
├── eval/                       # Evaluation & mutation benchmarks
└── tools/tasks.py              # Cross-platform project CLI
```

---

## 📜 Mandatory Regulatory Disclaimer

> **Research Prototype Only.** This software is an experimental research system designed to evaluate deterministic verification architectures for artificial intelligence. It contains synthetic protocol texts and synthetic patient cases. It is **not** a certified medical device, has **not** undergone clinical trials, and must **never** be used for actual clinical triage, medical diagnosis, or patient care.
