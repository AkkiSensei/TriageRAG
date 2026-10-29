"""Core Pydantic v2 schema definitions for TriageRAG.

Safety Property:
All models enforce extra="forbid" to reject unexpected payloads. Reports and
provenance records are frozen immutable. Units and numerical values are decimal-only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Generic, Literal, Protocol, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    ActionType,
    AgeUnit,
    Consciousness,
    ContentOrigin,
    DoseUnit,
    PopulationCategory,
    Route,
    ScoreBand,
    Severity,
    SourceStatus,
    StepStatus,
    Verdict,
)

T = TypeVar("T")


class Provenance(BaseModel):
    """Immutable audit trail of clinical evidence sources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_doc: str
    section_ref: str
    version_or_date: str
    source_status: SourceStatus = SourceStatus.PLACEHOLDER_UNRETRIEVED
    content_origin: ContentOrigin = ContentOrigin.AGENT_DRAFT_UNSOURCED
    verified: bool = False
    reviewer: str | None = None

    @model_validator(mode="after")
    def validate_verified_provenance(self) -> Provenance:
        if self.verified:
            if self.source_status != SourceStatus.REVIEWED:
                raise ValueError("verified=True requires source_status == REVIEWED")
            if not self.reviewer or not self.reviewer.strip():
                raise ValueError("verified=True requires non-empty reviewer identifier")
        return self


class Measured(BaseModel, Generic[T]):
    """First-class representation of clinical uncertainty: measured, estimated, or unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: T | None = None
    source: Literal["measured", "estimated", "unknown"] = "unknown"

    @model_validator(mode="after")
    def validate_measured_state(self) -> Measured[T]:
        if self.source == "unknown" and self.value is not None:
            raise ValueError("Measured with source='unknown' must have value=None")
        if self.source in ("measured", "estimated") and self.value is None:
            raise ValueError(f"Measured with source='{self.source}' must have a non-None value")
        return self


@lru_cache
def _load_age_classification_bounds(data_dir: Path | None = None) -> dict[str, Decimal]:
    """Load chronological age normalization bounds from data/retrieval/vitals_flags.yaml."""
    target_dir = data_dir or get_data_dir()
    flags_path = target_dir / "retrieval" / "vitals_flags.yaml"
    if not flags_path.exists():
        flags_path = get_data_dir() / "retrieval" / "vitals_flags.yaml"
    raw_data: Any = yaml.safe_load(flags_path.read_text(encoding="utf-8")) or {}
    age_cfg: dict[str, Any] = raw_data.get("age_classification") or {}
    return {
        "days_per_month": Decimal(str(age_cfg["days_per_month"])),
        "days_per_year": Decimal(str(age_cfg["days_per_year"])),
        "neonate_max_days": Decimal(str(age_cfg["neonate_max_days"])),
        "adult_min_years": Decimal(str(age_cfg["adult_min_years"])),
        "adult_min_days": Decimal(str(age_cfg["adult_min_days"])),
        "max_days_input": Decimal(str(age_cfg["max_days_input"])),
        "max_months_input": Decimal(str(age_cfg["max_months_input"])),
        "max_years_input": Decimal(str(age_cfg["max_years_input"])),
    }


class Age(BaseModel):
    """Patient chronological age with population classification (FG-04, HD-2)."""

    model_config = ConfigDict(extra="forbid")

    value: Decimal
    unit: AgeUnit = AgeUnit.years

    @model_validator(mode="after")
    def validate_age_bounds(self) -> Age:
        if self.value < Decimal("0"):
            raise ValueError("Age value must be non-negative")
        bounds = _load_age_classification_bounds()
        if self.unit == AgeUnit.days and self.value > bounds["max_days_input"]:
            raise ValueError("Age in days exceeds 365; use months or years")
        if self.unit == AgeUnit.months and self.value > bounds["max_months_input"]:
            raise ValueError("Age in months exceeds 48; use years")
        if self.unit == AgeUnit.years and self.value > bounds["max_years_input"]:
            raise ValueError("Age in years exceeds maximum bound of 130")
        return self

    @property
    def is_ambiguous_boundary(self) -> bool:
        """Flag ambiguous zero ages in coarse units (0 months, 0 years) (FG-04, HD-2)."""
        return self.unit in (AgeUnit.months, AgeUnit.years) and self.value == Decimal("0")

    def to_days(self) -> Decimal:
        """Normalize chronological age to days using configured conversion factors."""
        bounds = _load_age_classification_bounds()
        if self.unit == AgeUnit.days:
            return self.value
        if self.unit == AgeUnit.months:
            return self.value * bounds["days_per_month"]
        return self.value * bounds["days_per_year"]

    @property
    def population_category(self) -> PopulationCategory:
        bounds = _load_age_classification_bounds()
        age_days = self.to_days()
        if age_days <= bounds["neonate_max_days"]:
            return PopulationCategory.neonate
        if age_days < bounds["adult_min_days"]:
            return PopulationCategory.paediatric
        return PopulationCategory.adult


class ExplicitDose(BaseModel):
    """Explicit clinical dose amount and unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: Decimal
    unit: DoseUnit

    @model_validator(mode="after")
    def validate_positive_amount(self) -> ExplicitDose:
        if self.amount <= Decimal("0"):
            raise ValueError("Dose amount must be strictly positive")
        return self


class IngredientStrength(BaseModel):
    """Active pharmaceutical ingredient and strength for single or combination products."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ingredient_id: str
    strength_amount: Decimal | None = None
    strength_unit: DoseUnit | None = None


class MedicationEntry(BaseModel):
    """Medication in patient active or home regimen."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    ingredients: list[IngredientStrength] = Field(default_factory=list)
    suggestion: str | None = None
    dose_taken: ExplicitDose | None = None
    route: Route | None = None
    last_dose_time: datetime | None = None
    resolved: bool = False


class AllergyEntry(BaseModel):
    """Allergy or adverse substance reaction entry."""

    model_config = ConfigDict(extra="forbid")

    raw_substance: str
    normalized_allergen_id: str | None = None
    allergen_class: str | None = None
    suggestion: str | None = None
    reaction_type: Literal[
        "anaphylaxis_ige", "severe_cutaneous_scar", "mild_rash", "gi_upset", "unknown"
    ] = "unknown"
    resolved: bool = False


class Vitals(BaseModel):
    """Triage physiological vital signs with explicit uncertainty."""

    model_config = ConfigDict(extra="forbid")

    heart_rate_bpm: Measured[int] = Field(default_factory=lambda: Measured[int]())
    systolic_bp_mmhg: Measured[int] = Field(default_factory=lambda: Measured[int]())
    diastolic_bp_mmhg: Measured[int] = Field(default_factory=lambda: Measured[int]())
    respiratory_rate_bpm: Measured[int] = Field(default_factory=lambda: Measured[int]())
    spo2_percent: Measured[int] = Field(default_factory=lambda: Measured[int]())
    supplemental_o2: Measured[Literal["yes", "no", "unknown"]] = Field(
        default_factory=lambda: Measured[Literal["yes", "no", "unknown"]]()
    )
    temperature_c: Measured[Decimal] = Field(default_factory=lambda: Measured[Decimal]())
    blood_glucose_mg_dl: Measured[Decimal] = Field(default_factory=lambda: Measured[Decimal]())
    consciousness: Measured[Consciousness] = Field(
        default_factory=lambda: Measured[Consciousness]()
    )
    gcs_total: Measured[int] = Field(default_factory=lambda: Measured[int]())


class Patient(BaseModel):
    """Complete structured synthetic patient record."""

    model_config = ConfigDict(extra="forbid")

    assessed_at: datetime
    age: Age
    sex: Literal["male", "female", "other", "unknown"]
    pregnancy: Literal["yes", "no", "not_applicable", "unknown"]
    weight_kg: Measured[Decimal]
    vitals: Vitals
    allergy_history_status: Literal[
        "confirmed_none", "confirmed_nkda", "confirmed_list", "incomplete", "unknown_unobtainable"
    ]
    medication_history_status: Literal[
        "confirmed_none", "confirmed_nkda", "confirmed_list", "incomplete", "unknown_unobtainable"
    ]
    allergies: list[AllergyEntry] = Field(default_factory=list)
    medications: list[MedicationEntry] = Field(default_factory=list)
    renal_impairment: Literal["yes", "no", "unknown"] = "unknown"
    hepatic_impairment: Literal["yes", "no", "unknown"] = "unknown"
    suspected_syndrome: str | None = None
    chief_complaint_untrusted: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_patient_constraints(self) -> Patient:
        if self.assessed_at.tzinfo is None:
            raise ValueError("assessed_at must be a timezone-aware datetime")

        for med in self.medications:
            if med.last_dose_time is not None:
                if med.last_dose_time.tzinfo is None:
                    raise ValueError("Medication last_dose_time must be timezone-aware")
                if med.last_dose_time > self.assessed_at:
                    raise ValueError(
                        "Medication last_dose_time cannot be in the future relative to assessed_at"
                    )

        if (
            self.allergy_history_status in ("confirmed_none", "confirmed_nkda")
            and len(self.allergies) > 0
        ):
            raise ValueError(
                f"Allergy status '{self.allergy_history_status}' forbids non-empty allergies list"
            )
        if self.allergy_history_status == "confirmed_list" and len(self.allergies) == 0:
            raise ValueError("Allergy status 'confirmed_list' requires at least one allergy entry")

        if (
            self.medication_history_status in ("confirmed_none", "confirmed_nkda")
            and len(self.medications) > 0
        ):
            err = (
                f"Medication status '{self.medication_history_status}' "
                "forbids non-empty medications list"
            )
            raise ValueError(err)

        if self.medication_history_status == "confirmed_list" and len(self.medications) == 0:
            raise ValueError(
                "Medication status 'confirmed_list' requires at least one medication entry"
            )

        return self


class SpanCitation(BaseModel):
    """Verbatim citation pointing directly to a retrieved protocol chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    section: str
    chunk_id: str
    page: int | None = None
    quoted_span: str = Field(min_length=10)


class PlanStepDraft(BaseModel):
    """A single proposed clinical plan step drafted by the LLM."""

    model_config = ConfigDict(extra="forbid")

    step_number: int
    action_type: ActionType
    narrative_instruction: str
    drug_id: str | None = None
    requested_dose: ExplicitDose | None = None
    route: Route | None = None
    citations: list[SpanCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_step_consistency(self) -> PlanStepDraft:
        if self.action_type in (ActionType.administer, ActionType.withhold):
            if not self.drug_id or not self.drug_id.strip():
                raise ValueError(f"Action '{self.action_type}' requires a drug_id")
        else:
            if self.drug_id is not None:
                raise ValueError(f"Action '{self.action_type}' forbids drug_id")
            if self.requested_dose is not None:
                raise ValueError(f"Action '{self.action_type}' forbids requested_dose")
            if self.route is not None:
                raise ValueError(f"Action '{self.action_type}' forbids route")

        if self.action_type == ActionType.withhold and self.requested_dose is not None:
            raise ValueError("Action 'withhold' forbids requested_dose")

        if self.requested_dose is not None and self.route is None:
            raise ValueError("requested_dose requires an explicit route")

        return self


class PlanDraft(BaseModel):
    """The ONLY schema permitted for language model generation."""

    model_config = ConfigDict(extra="forbid")

    matched_protocol_title: str
    steps: list[PlanStepDraft] = Field(default_factory=list)


class DrugAction(BaseModel):
    """Clause-scoped binding between a clinical action polarity and a formulary drug (FG-01)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["administer", "withhold", "unparsed"]
    drug_id: str
    clause_text: str


class RetrievedChunk(BaseModel):
    """Retrieved document text chunk with metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    section: str
    chunk_id: str
    parent_id: str | None = None
    text: str
    population: str
    syndrome: str
    score: Decimal = Decimal("0.0")
    drug_actions: tuple[DrugAction, ...] = ()


class RetrievalReport(BaseModel):
    """Report on retrieval execution, backend used, provenance hashes, and abstain decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunks: list[RetrievedChunk] = Field(default_factory=list)
    backend: str = "bm25"
    abstained: bool = False
    abstain_code: AbstainCode = AbstainCode.NONE
    reason: str | None = None
    query: str = ""
    filters: dict[str, str] = Field(default_factory=dict)
    skipped_flags: list[str] = Field(default_factory=list)
    stage_scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    corpus_hash: str = ""
    index_version: str = "1.0.0"
    config_hash: str = ""


class PlanContext(BaseModel):
    """Controlled contextual payload passed to the plan drafting module."""

    model_config = ConfigDict(extra="forbid")

    population_category: PopulationCategory
    vitals_derived_flags: list[str] = Field(default_factory=list)
    allowed_drug_ids: list[str] = Field(default_factory=list)
    pass1_alert_summaries: list[str] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    chief_complaint_delimited: str | None = None


class Alert(BaseModel):
    """Deterministic clinical rule alert."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    severity: Severity
    rule_type: str
    drug_ids: list[str] = Field(default_factory=list)
    consequence: str
    action: str
    provenance: Provenance
    unverified: bool = False


class SkippedCheck(BaseModel):
    """Explicit record of an unperformed check due to missing or unresolved data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    rule_type: str
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
    provenance: Provenance | None = None


class CalculatedDoseReport(BaseModel):
    """Dose mathematics and formulary limit verification report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    drug_id: str
    requested_dose: ExplicitDose
    calculated_ceiling: ExplicitDose | None = None
    calculated_recommended: ExplicitDose | None = None
    magnitude_tripwire_triggered: bool = False
    status: Literal[
        "OK", "EXCEEDS_CEILING", "BELOW_MINIMUM", "UNVERIFIED_MISSING_CAP", "MAGNITUDE_WARNING"
    ]
    notes: str = ""


class ScoreResult(BaseModel):
    """Physiological score calculation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score_name: str
    total_score: int | None = None
    band: ScoreBand = ScoreBand.UNSCORED
    subscores: dict[str, int] = Field(default_factory=dict)
    missing_vitals: list[str] = Field(default_factory=list)
    provenance: Provenance


class EngineReport(BaseModel):
    """Deterministic, pure output from the clinical decision engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Verdict
    score: ScoreResult | None = None
    baseline_alerts: list[Alert] = Field(default_factory=list)
    plan_alerts: list[Alert] = Field(default_factory=list)
    dose_reports: list[CalculatedDoseReport] = Field(default_factory=list)
    checks_run: int = 0
    checks_skipped: list[SkippedCheck] = Field(default_factory=list)
    unresolved_entities: list[str] = Field(default_factory=list)
    ruleset_coverage: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    unverified_rules_evaluated: int = 0
    ruleset_review_state: Literal["UNREVIEWED_DRAFT", "PARTIALLY_REVIEWED", "FULLY_REVIEWED"] = (
        "UNREVIEWED_DRAFT"
    )
    ruleset_version: str = "0.1.0"


class OverrideRecord(BaseModel):
    """Clinician override acknowledgment for a HIGH alert step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    step_number: int
    reason: str = Field(min_length=15)
    clinician_id: str


class VerifiedStep(BaseModel):
    """Machine-verified plan step."""

    model_config = ConfigDict(extra="forbid")

    draft: PlanStepDraft
    status: StepStatus
    triggered_rule_ids: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    citation_verified: bool = False
    citation_overlap_score: Decimal = Decimal("0.0")
    support_reason: str | None = None


class TriageResponse(BaseModel):
    """Full triage response returned to UI and CLI."""

    model_config = ConfigDict(extra="forbid")

    engine: EngineReport
    verified_steps: list[VerifiedStep] = Field(default_factory=list)
    retrieved_protocol_title: str | None = None
    retrieval: RetrievalReport | None = None
    overrides: list[OverrideRecord] = Field(default_factory=list)
    llm_fallback_mode: bool = False
    audit_hash: str = ""


class Clock(Protocol):
    """Abstract clock protocol for deterministic time injection (Rule R12)."""

    def now(self) -> datetime: ...


class SystemClock:
    """Real system clock emitting timezone-aware UTC datetime."""

    def now(self) -> datetime:
        from datetime import UTC, datetime

        return datetime.now(UTC)


class FixedClock:
    """Deterministic fixed clock for testing and repeatable evaluation."""

    def __init__(self, fixed_time: datetime) -> None:
        if fixed_time.tzinfo is None:
            raise ValueError("FixedClock requires timezone-aware datetime")
        self._time = fixed_time

    def now(self) -> datetime:
        return self._time


class OrchestratorConfig(BaseModel):
    """Immutable runtime configuration for the clinical orchestrator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    include_complaint_in_llm: bool = False
    retrieval_threshold: float = 0.30
    top_k_chunks: int = 5
    max_repair_cycles: int = 2
    audit_log_path: Path | None = None
