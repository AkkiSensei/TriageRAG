# ADR 0002: Fail Closed on Incomplete or Unresolved Data

## Status
Accepted

## Context
In medical informatics, absence of evidence is frequently mistaken for evidence of absence. When medication history, allergy reactions, or physiological vitals are missing or ambiguous, clearing a patient as "safe" is dangerous.

## Decision
TriageRAG enforces a fail-closed policy across all evaluation paths:
1. Missing, incomplete, or unknown history yields `UNVERIFIED`, never a clean clearance.
2. Unresolved medication aliases or allergen substances produce `UNVERIFIED`.
3. "No rule fired" evaluates strictly to "no rule in this ruleset fired".
4. The overall safety verdict follows a lattice: `BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR`.

## Consequences
- No patient with incomplete data receives a misleading "CLEAR" badge.
- Clinicians are explicitly shown "What could not be checked" and known coverage gaps.
