# ADR 0005: Clinical UX Safety Architecture — UI Shows, Never Decides

## Status
Accepted

## Context
When designing a modern web frontend with rich animations and micro-interactions (such as React Bits and Framer Motion), there is a significant risk that animations, transitions, or asynchronous UI rendering could delay, obscure, or alter safety-critical clinical information. Furthermore, performing any clinical math (such as dosage calculation or unit conversion) in client-side JavaScript risks IEEE 754 floating-point inaccuracies and client-side desynchronization with the deterministic Python engine.

## Decision
We enforce a strict Clinical UX Safety Architecture across the React frontend:
1. **Safety Information is Never Animated or Obscured (Principle S1):** SafetyBanner, contraindication alerts, blocked drugs, skipped checks, coverage gaps, and the mandatory clinical disclaimer render immediately, statically, and synchronously. No React Bits or Framer Motion transitions are permitted on safety output containers.
2. **Zero Client-Side Clinical Math (Principle S2):** The frontend performs zero medical mathematics. All physiological scores, weight-scaled doses, and lookbacks are computed on the backend and serialized as exact strings.
3. **No Bare "CLEAR" (Principle S3):** The bare word "CLEAR" is prohibited across all UI components and tests. Safe verdicts must always be qualified with ruleset coverage (e.g. `CHECKED CLEAR (ruleset coverage: N active rules)`).
4. **Motion Safety Guard (Principle S4):** The system respects `prefers-reduced-motion: reduce` and provides a global user toggle. Under reduced motion, all canvas particles, spring physics, and CSS shimmers are completely bypassed.
5. **No BLOCK Override Control (Principle S5):** For BLOCK contraindications, no override button or code path exists in the UI.

## Consequences
- Clinicians are guaranteed immediate, un-delayed access to critical contraindication alerts.
- Precision of Decimal math is preserved end-to-end without JavaScript float truncation.
- False confidence from unqualified "CLEAR" verdicts is eliminated.
