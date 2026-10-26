# ADR 0001: Code Decides; The LLM Explains

## Status
Accepted

## Context
Large Language Models exhibit probabilistic behavior, hallucination, and susceptibility to adversarial prompting. In clinical triage and drug safety verification, ungrounded probabilistic calculations represent an unacceptable hazard.

## Decision
All clinical scoring, drug-drug interaction detection, allergy cross-reactivity mapping, dosage math, and final safety verdicts are computed strictly by deterministic Python code. The LLM is restricted to drafting narrative action steps (`PlanDraft`) citing retrieved protocol chunks, which are subsequently verified by deterministic machine validators.

## Consequences
- Engine logic is 100% reproducible and testable via unit and property tests.
- LLM cannot silently override clinical constraints or calculate medication doses.
- Strict isolation prevents the engine from importing any LLM or RAG libraries.
