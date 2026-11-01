# TriageRAG Trust Policy Specification (T6.0 / AUB-ENG-04 / HD-7)

**Specification:** `AUB.md` Task T6.0  
**Status:** IMPLEMENTED  
**Governing ADR:** ADR-0015 (Schema V2 & Deterministic Rule Engine Expansion)  

---

## 1. Overview & Problem Statement (AUB-ENG-04)

TriageRAG's clinical safety architecture is governed by Rule R1 ("Code decides; the LLM explains"), Rule R2 ("Fail closed"), and Rule R3 ("No invented clinical facts"). Under Human Decision **HD-7**, candidate and seed rules carry:
```yaml
source_status: PLACEHOLDER_UNRETRIEVED # or RETRIEVED_UNREVIEWED
verified: false
reviewer: null
```
No clinical rule can be marked `verified: true` or `REVIEWED` programmatically without explicit sign-off by a licensed clinician/pharmacologist (and dual sign-off for BLOCK contraindications).

Prior to T6.0, an inconsistency existed (AUB-ENG-04): while vitals-based rules ran as active deterministic rules, their provenance explicitly remained unverified draft status.

---

## 2. Trust Policy Modes (`trust_mode`)

To resolve this inconsistency without creating false certainty or breaking prototype functionality, TriageRAG implements two first-class operational modes:

### `trust_mode = demo` (Default for Prototype)
- Intended for development, testing, research evaluation, and viva demonstration.
- Evaluates candidate and draft clinical rules to exercise deterministic rule logic and safety tripwires.
- Clearly badges all alerts with `[UNSOURCED DRAFT]` status.
- Every `EngineReport` transparently reports:
  - `trust_mode: "demo"`
  - `verified_rules_count: n`
  - `total_rules_count: N`
  - `verified_rules_summary: "verified n of N"` (e.g. `"verified 0 of 12"`)

### `trust_mode = strict` (Fail-Closed Mode)
- Intended for high-integrity clinical safety gates and production deployment readiness.
- Under Rule R2, if any unverified draft rules (`verified: false`) are evaluated during triage:
  - The system **refuses to issue `CHECKED_CLEAR`**.
  - The verdict fails closed to `UNVERIFIED` with explicit reason:
    `UNVERIFIED_RULESET: <n> rules evaluated without clinical verification in strict trust mode (HD-7)`
  - Crucially, protective `BLOCK` alerts triggered by safety rules are **still preserved** to ensure safety tripwires are never silenced.
  - Only when 100% of evaluated rules carry `provenance.verified: true` can a clean assessment achieve `CHECKED_CLEAR`.

---

## 3. Transparency & Surface Requirements

As required by T6.0:
1. **EngineReport**: Contains `trust_mode`, `verified_rules_count`, `total_rules_count`, and `verified_rules_summary`.
2. **CLI Output**: The triage report banner includes dedicated `Trust Mode` and `Verified Rules` columns showing e.g. `DEMO` and `verified 0 of 12`.
3. **Web Frontend**: The report header and summary wristband display badge: `Ruleset 0.1.0 • verified 0 of 12 (DEMO)`.
4. **Audit Log**: Audit event records log `trust_mode` and verification counts alongside patient hash and overall verdict.

