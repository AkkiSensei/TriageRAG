"""Data transfer schemas for the TriageRAG API layer.

Safety Property:
All clinical schemas are referenced from contracts; no client-side clinical math.
Decimals are serialized strictly as strings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from triagerag.contracts.enums import AgeUnit
from triagerag.contracts.schemas import Age, Measured, OverrideRecord, Patient, Vitals
from triagerag.llm.fake import FakeLLMProfile


class HealthResponse(BaseModel):
    version: str = "0.1.0"
    ruleset_version: str = "0.1.0"
    llm_available: bool = True
    generation_mode: str = "deterministic_mock"
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
    retrieval_backend: str | None = None

    @field_validator("llm_profile", mode="before")
    @classmethod
    def normalize_profile(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v


class ExplainApiRequest(BaseModel):
    """Request payload for the retrieval explain diagnostic endpoint.

    Accepts either a full Patient (wrapped under `patient` or inline), or minimal
    retrieval attributes (population, suspected_syndrome, vitals).
    """

    model_config = ConfigDict(extra="ignore")

    patient: Patient | None = None
    population: str = "adult"
    suspected_syndrome: str | None = None
    vitals: Vitals | dict[str, Any] = Field(default_factory=dict)
    assessed_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_root_patient(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "patient" in data and isinstance(data["patient"], dict):
                return data
            if "assessed_at" in data and "age" in data and "sex" in data:
                return {"patient": data}
        return data

    def to_patient(self) -> Patient:
        """Convert request into a fully-validated Patient instance."""
        if self.patient is not None:
            return self.patient

        pop_str = (self.population or "adult").lower().strip()
        if pop_str == "neonate":
            age = Age(value=Decimal("10"), unit=AgeUnit.days)
        elif pop_str in ("paediatric", "pediatric", "child"):
            age = Age(value=Decimal("8"), unit=AgeUnit.years)
        else:
            age = Age(value=Decimal("40"), unit=AgeUnit.years)

        if isinstance(self.vitals, Vitals):
            vitals_obj = self.vitals
        elif isinstance(self.vitals, dict):
            normalized_vitals: dict[str, Any] = {}
            for k, val in self.vitals.items():
                if isinstance(val, (int, float, str, Decimal)) and not isinstance(val, bool):
                    normalized_vitals[k] = {"value": val, "source": "measured"}
                else:
                    normalized_vitals[k] = val
            vitals_obj = Vitals(**normalized_vitals)
        else:
            vitals_obj = Vitals()

        return Patient(
            assessed_at=self.assessed_at or datetime.now(UTC),
            age=age,
            sex="unknown",
            pregnancy="unknown",
            weight_kg=Measured[Decimal](),
            vitals=vitals_obj,
            allergy_history_status="unknown_unobtainable",
            medication_history_status="unknown_unobtainable",
            allergies=[],
            medications=[],
            suspected_syndrome=self.suspected_syndrome,
        )


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
    retrieval_query: str = ""
    retrieval_filters: dict[str, Any] = Field(default_factory=dict)
    retrieval_stage_scores: dict[str, Any] = Field(default_factory=dict)
    corpus_hash: str = ""
    index_version: str = ""
    config_hash: str = ""
    abstain_code: str = "NONE"
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
