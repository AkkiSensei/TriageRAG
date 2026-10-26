# TriageRAG — Data Provenance & Verification Policy

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

## Provenance Model

Every rule, alias mapping, formulary threshold, and score table in TriageRAG is tracked using an immutable Pydantic `Provenance` contract:

```python
class Provenance(BaseModel):
    source_doc: str
    section_ref: str
    version_or_date: str
    source_status: SourceStatus = SourceStatus.PLACEHOLDER_UNRETRIEVED
    content_origin: ContentOrigin = ContentOrigin.AGENT_DRAFT_UNSOURCED
    verified: bool = False
    reviewer: str | None = None
```

### Invariants:
1. `verified: true` is strictly invalid unless `source_status == SourceStatus.REVIEWED` and `reviewer is not None`.
2. Any entity missing verified provenance is flagged as `UNSOURCED DRAFT` in user interfaces and CLI outputs.
3. Automated tools (`tools/provenance_report.py`) audit all YAML files in `data/` and fail CI if unverified content is falsely marked verified.

## Seed Corpus Provenance Status

All seed data in this repository is currently initialized to:
- `source_status: PLACEHOLDER_UNRETRIEVED`
- `content_origin: AGENT_DRAFT_UNSOURCED`
- `section_ref: "TO_BE_RESOLVED"`
- `verified: false`
- `reviewer: null`

No artificial section numbers or citations are fabricated. Where values are unknown, `status: NEEDS_SOURCE` is used to cause the engine to emit a safe `SkippedCheck`.
