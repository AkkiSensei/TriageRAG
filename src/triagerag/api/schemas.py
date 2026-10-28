"""Data transfer schemas for the TriageRAG API layer.

Safety Property:
All clinical schemas are referenced from contracts; no client-side clinical math.
Decimals are serialized strictly as strings.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from triagerag.contracts.schemas import OverrideRecord, Patient
from triagerag.llm.fake import FakeLLMProfile


class HealthResponse(BaseModel):
    version: str = "0.1.0"
    ruleset_version: str = "0.1.0"
    llm_available: bool = True
    retrieval_backend: str = "bm25"
    unreviewed_rules_count: int = 0
    disclaimer: str = (
        "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
    )


class ScenarioSummary(BaseModel):
    id: str
    title: str
    description: str
    what_it_demonstrates: str
    expected_verdict: str


class ScenarioDetail(ScenarioSummary):
    patient: Patient
    overrides: list[OverrideRecord] = Field(default_factory=list)


class TriageApiRequest(BaseModel):
    patient: Patient
    overrides: list[OverrideRecord] | None = None
    llm_profile: FakeLLMProfile = FakeLLMProfile.COMPLIANT
    include_complaint_in_llm: bool = False

    @field_validator("llm_profile", mode="before")
    @classmethod
    def normalize_profile(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v


class RuleSummaryDto(BaseModel):
    id: str
    rule_type: str
    severity: str
    status: str
    source_status: str
    content_origin: str
    verified: bool
    requires_fields: list[str] = Field(default_factory=list)
    consequence: str = ""
    action: str = ""


class RegistrySummaryResponse(BaseModel):
    formulary_drugs_count: int
    rules_count: int
    rules_by_severity: dict[str, int]
    rules_by_source_status: dict[str, int]
    aliases_count: int
    acronyms_count: int
    coverage_gaps: list[str]
    unreviewed_count: int


class ProtocolChunkDto(BaseModel):
    chunk_id: str
    doc_id: str
    parent_id: str | None = None
    title: str = ""
    section: str
    population: str
    syndrome: str
    text: str
    synthetic: bool
    version: str = "1.0.0"
    content_hash: str = ""
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    source_status: str = "PLACEHOLDER_UNRETRIEVED"


class AuditEntryDto(BaseModel):
    sequence_number: int
    timestamp_iso: str
    patient_hash: str
    ruleset_version: str
    formulary_version: str
    retrieved_chunk_ids: list[str]
    provider_name: str
    model_name: str
    verdict: str
    alert_ids: list[str]
    skipped_rule_ids: list[str]
    previous_hash: str
    record_hash: str


class AuditVerifyResponse(BaseModel):
    valid: bool
    first_bad_index: str | None = None


class EvalSummaryResponse(BaseModel):
    golden: dict[str, Any] = Field(default_factory=dict)
    mechanics: dict[str, Any] = Field(default_factory=dict)
    metamorphic: dict[str, Any] = Field(default_factory=dict)
    adversarial: dict[str, Any] = Field(default_factory=dict)
    mutation: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    ablation: dict[str, Any] = Field(default_factory=dict)
