# ADR 0004: Strict Prohibition of BLOCK Alert Overrides

## Status
Accepted

## Context
In emergency decision support, hard contraindications (e.g. absolute drug-drug interactions like organic nitrates with PDE5 inhibitors, or life-threatening anaphylactic allergen exposures) must not be bypassed by clinical overrides or soft confirmations.

## Decision
No software code path exists in TriageRAG to approve, verify, or override any action step triggered by a `BLOCK` severity alert. An `administer` step triggering a `BLOCK` alert is permanently marked `BLOCKED_STRUCK_THROUGH`. Only `HIGH` severity alerts may be acknowledged via logged `OverrideRecord` with clinician credentials and rationale.

## Consequences
- Guaranteed mathematical invariant: zero approved steps with active BLOCK alerts.
- Enforced by automated regression tests in CI.
