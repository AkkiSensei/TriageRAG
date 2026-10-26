# ADR 0003: Synthetic Corpus First and Zero Doses in Guidelines

## Status
Accepted

## Context
Bundling real clinical clinical guidelines or proprietary formulary databases risks copyright infringement and clinical misuse of unvalidated research prototypes. Furthermore, hardcoding numeric doses in prose leads to discrepancies with formulary limits.

## Decision
All bundled emergency protocols are original synthetic markdown documents clearly badged `SYNTHETIC`. Protocols specify clinical indications and drug identifiers, but contain **no numeric doses**. All dosing limits reside exclusively in structured formulary YAML files.

## Consequences
- Prevents clinical reliance on prose numbers.
- Forces all dose calculations to pass through the deterministic `DoseEngine`.
- Eliminates copyright complications for research distribution.
