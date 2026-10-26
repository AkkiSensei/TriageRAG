"""Unit tests for TriageRAG contracts and domain schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    DoseUnit,
    PopulationCategory,
    SourceStatus,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    MedicationEntry,
    Patient,
    PlanStepDraft,
    Provenance,
    SpanCitation,
    Vitals,
)
from triagerag.normalize.units import (
    check_magnitude_tripwire,
    convert_dose,
    parse_dose_string,
)
from triagerag.normalize.yaml_loader import load_yaml_decimal


class TestProvenanceContract:
    def test_default_unverified_provenance(self) -> None:
        prov = Provenance(
            source_doc="TEST_DOC",
            section_ref="SEC_1",
            version_or_date="2026-TEST",
        )
        assert not prov.verified
        assert prov.source_status == SourceStatus.PLACEHOLDER_UNRETRIEVED
        assert prov.reviewer is None

    def test_verified_requires_reviewed_and_reviewer(self) -> None:
        with pytest.raises(ValidationError, match="requires source_status == REVIEWED"):
            Provenance(
                source_doc="TEST_DOC",
                section_ref="SEC_1",
                version_or_date="2026-TEST",
                source_status=SourceStatus.PLACEHOLDER_UNRETRIEVED,
                verified=True,
                reviewer="clinician_dr_smith",
            )

        with pytest.raises(ValidationError, match="requires non-empty reviewer"):
            Provenance(
                source_doc="TEST_DOC",
                section_ref="SEC_1",
                version_or_date="2026-TEST",
                source_status=SourceStatus.REVIEWED,
                verified=True,
                reviewer=None,
            )

        valid = Provenance(
            source_doc="TEST_DOC",
            section_ref="SEC_1",
            version_or_date="2026-TEST",
            source_status=SourceStatus.REVIEWED,
            verified=True,
            reviewer="dr_jane_doe",
        )
        assert valid.verified


class TestMeasuredContract:
    def test_measured_valid_states(self) -> None:
        m_unknown: Measured[int] = Measured[int]()
        assert m_unknown.source == "unknown"
        assert m_unknown.value is None

        m_measured: Measured[int] = Measured[int](value=80, source="measured")
        assert m_measured.value == 80

        m_estimated: Measured[Decimal] = Measured[Decimal](
            value=Decimal("70.5"), source="estimated"
        )
        assert m_estimated.value == Decimal("70.5")

    def test_measured_invariants(self) -> None:
        with pytest.raises(ValidationError, match="must have value=None"):
            Measured[int](value=10, source="unknown")

        with pytest.raises(ValidationError, match="must have a non-None value"):
            Measured[int](value=None, source="measured")


class TestAgeContract:
    def test_age_population_categories(self) -> None:
        neonate = Age(value=Decimal("20"), unit=AgeUnit.days)
        assert neonate.population_category == PopulationCategory.neonate

        paed_days = Age(value=Decimal("35"), unit=AgeUnit.days)
        assert paed_days.population_category == PopulationCategory.paediatric

        paed_years = Age(value=Decimal("12"), unit=AgeUnit.years)
        assert paed_years.population_category == PopulationCategory.paediatric

        adult = Age(value=Decimal("45"), unit=AgeUnit.years)
        assert adult.population_category == PopulationCategory.adult

    def test_negative_age_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must be non-negative"):
            Age(value=Decimal("-1"), unit=AgeUnit.years)


class TestPatientContract:
    def test_tz_aware_required(self) -> None:
        naive_now = datetime(2026, 10, 26, 12, 0, 0)
        with pytest.raises(ValidationError, match="timezone-aware"):
            Patient(
                assessed_at=naive_now,
                age=Age(value=Decimal("30"), unit=AgeUnit.years),
                sex="female",
                pregnancy="no",
                weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
                vitals=Vitals(),
                allergy_history_status="confirmed_none",
                medication_history_status="confirmed_none",
            )

    def test_medication_last_dose_time_bound(self) -> None:
        assessed_at = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
        future_dose = datetime(2026, 10, 26, 14, 0, 0, tzinfo=UTC)
        with pytest.raises(ValidationError, match="cannot be in the future"):
            Patient(
                assessed_at=assessed_at,
                age=Age(value=Decimal("30"), unit=AgeUnit.years),
                sex="female",
                pregnancy="no",
                weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
                vitals=Vitals(),
                allergy_history_status="confirmed_none",
                medication_history_status="confirmed_list",
                medications=[MedicationEntry(raw_text="metoprolol", last_dose_time=future_dose)],
            )


class TestPlanStepContract:
    def test_administer_requires_drug_id(self) -> None:
        citation = SpanCitation(
            doc_id="DOC1",
            section="SEC1",
            chunk_id="CHK1",
            quoted_span="administer sublingual nitroglycerin as formulary-directed",
        )
        with pytest.raises(ValidationError, match="requires a drug_id"):
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction="Give drug immediately",
                drug_id=None,
                citations=[citation],
            )

    def test_withhold_forbids_dose(self) -> None:
        citation = SpanCitation(
            doc_id="DOC1",
            section="SEC1",
            chunk_id="CHK1",
            quoted_span="withhold nitroglycerin completely to prevent refractory vasodilation",
        )
        with pytest.raises(ValidationError, match="forbids requested_dose"):
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.withhold,
                narrative_instruction="Withhold drug",
                drug_id="nitroglycerin",
                requested_dose=ExplicitDose(amount=Decimal("0.4"), unit=DoseUnit.mg),
                citations=[citation],
            )


class TestDecimalYamlLoader:
    def test_exact_84_7_decimal_parsed(self) -> None:
        yaml_text = "test_val: 84.7\nanother_val: 100.005\n"
        loaded = load_yaml_decimal(yaml_text)
        val = loaded["test_val"]
        assert isinstance(val, Decimal)
        assert val == Decimal("84.7")
        assert str(val) == "84.7"


class TestUnitsModule:
    def test_parse_dose_string_success(self) -> None:
        d1 = parse_dose_string("500 mg")
        assert d1.amount == Decimal("500")
        assert d1.unit == DoseUnit.mg

        d2 = parse_dose_string("0.4 mg")
        assert d2.amount == Decimal("0.4")
        assert d2.unit == DoseUnit.mg

    def test_dangerous_abbreviations_rejected(self) -> None:
        with pytest.raises(ValueError, match="Dangerous abbreviation 'u'"):
            parse_dose_string("10 u")
        with pytest.raises(ValueError, match="Dangerous abbreviation 'cc'"):
            parse_dose_string("5 cc")

    def test_exact_decimal_conversions(self) -> None:
        mg_dose = ExplicitDose(amount=Decimal("500"), unit=DoseUnit.mg)
        g_dose = convert_dose(mg_dose, DoseUnit.g)
        assert g_dose.amount == Decimal("0.5")

        mcg_dose = convert_dose(mg_dose, DoseUnit.mcg)
        assert mcg_dose.amount == Decimal("500000")

    def test_magnitude_tripwire(self) -> None:
        ref = Decimal("50")
        # 10x high
        assert check_magnitude_tripwire(Decimal("500"), ref)
        # 0.1x low
        assert check_magnitude_tripwire(Decimal("5"), ref)
        # Normal within range
        assert not check_magnitude_tripwire(Decimal("60"), ref)
