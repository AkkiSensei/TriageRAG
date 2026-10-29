"""Fix Gate G2 unit & property tests: Clinical inputs fail closed (FG-02, FG-04, HD-1, HD-2).

AGENT_AUTHORED_UNREVIEWED: Tests authored by agent for Fix Gate G2 verification.

Safety Properties Tested:
1. FG-02: Any vitals flag rule with status=ACTIVE and provenance.verified=False is rejected
   at load time by VitalsFlagRule schema validation.
2. FG-02 / HD-1: All unverified vitals flag rules in data/retrieval/vitals_flags.yaml are
   status=NEEDS_SOURCE with threshold=None and emit zero flags.
3. FG-02: Paediatric patients resolve to age-specific bands (paediatric_1m_1y, paediatric_1_5y,
   paediatric_5_12y, paediatric_12_18y); unmatched bands fail closed; skipped rules are recorded
   in RetrievalReport.skipped_flags.
4. FG-04 / HD-2: Age normalizes to days using configured constants before population
   classification; 0.5 months (15 days) and <= 28 days are neonate; 0 months/years is rejected;
   population_category is monotone non-decreasing in chronological age across units.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from triagerag.config import get_data_dir
from triagerag.contracts.enums import (
    AbstainCode,
    AgeUnit,
    ContentOrigin,
    PopulationCategory,
    RuleStatus,
    SourceStatus,
)
from triagerag.contracts.schemas import Age, Measured, Patient, Provenance, Vitals
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import (
    VitalsFlagRule,
    VitalsFlagsConfig,
    derive_vitals_flags,
    derive_vitals_flags_with_trace,
    load_vitals_flags_config,
    resolve_vitals_population_band,
    retrieve_protocol_chunks,
)

_POP_RANK: dict[PopulationCategory, int] = {
    PopulationCategory.neonate: 0,
    PopulationCategory.paediatric: 1,
    PopulationCategory.adult: 2,
}


def _make_verified_provenance() -> Provenance:
    return Provenance(
        source_doc="TEST_VERIFIED_GUIDELINE_FIXTURE",
        section_ref="SECTION_1",
        version_or_date="2026-01",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="clinician_test_fixture",
    )


def _make_unverified_provenance() -> Provenance:
    return Provenance(
        source_doc="SYNTHETIC_UNSOURCED_DRAFT",
        section_ref="TO_BE_RESOLVED",
        version_or_date="2026-DRAFT",
        source_status=SourceStatus.PLACEHOLDER_UNRETRIEVED,
        content_origin=ContentOrigin.AGENT_DRAFT_UNSOURCED,
        verified=False,
        reviewer=None,
    )


def _make_patient(
    age_val: str,
    age_unit: AgeUnit,
    *,
    hr: int | None = None,
    sbp: int | None = None,
    rr: int | None = None,
    syndrome: str | None = None,
) -> Patient:
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal(age_val), unit=age_unit),
        sex="female",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("20.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=(
                Measured[int](value=hr, source="measured") if hr is not None else Measured[int]()
            ),
            systolic_bp_mmhg=(
                Measured[int](value=sbp, source="measured") if sbp is not None else Measured[int]()
            ),
            respiratory_rate_bpm=(
                Measured[int](value=rr, source="measured") if rr is not None else Measured[int]()
            ),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=syndrome,
    )


def test_unverified_provenance_rule_emits_nothing() -> None:
    """FG-02: Any rule with verified=False and status=ACTIVE is rejected at load time."""
    with pytest.raises(ValidationError, match="verified"):
        VitalsFlagRule(
            id="VF_TEST_UNVERIFIED_ACTIVE",
            flag="tachycardia",
            field="heart_rate_bpm",
            operator=">",
            threshold=Decimal("100"),
            status=RuleStatus.ACTIVE,
            provenance=_make_unverified_provenance(),
        )

    # Needs-source rule with unverified provenance loads cleanly and emits nothing
    needs_source_rule = VitalsFlagRule(
        id="VF_TEST_UNVERIFIED_NEEDS_SOURCE",
        flag="tachycardia",
        field="heart_rate_bpm",
        operator=">",
        threshold=None,
        status=RuleStatus.NEEDS_SOURCE,
        provenance=_make_unverified_provenance(),
    )
    base_cfg = load_vitals_flags_config(get_data_dir())
    custom_cfg = VitalsFlagsConfig(
        version="2.0.0",
        age_classification=base_cfg.age_classification,
        populations={"adult": [needs_source_rule]},
    )
    patient = _make_patient("45", AgeUnit.years, hr=150)
    flags, skipped, band = derive_vitals_flags_with_trace(patient, config=custom_cfg)
    assert flags == []
    assert band == "adult"
    assert any("VF_TEST_UNVERIFIED_NEEDS_SOURCE" in s and "NEEDS_SOURCE" in s for s in skipped)


def test_paediatric_age_band_required() -> None:
    """FG-02: 6-month-old, 4-year-old, and 16-year-old resolve to distinct bands; no band -> []"""
    cfg = load_vitals_flags_config(get_data_dir())

    age_6m = Age(value=Decimal("6"), unit=AgeUnit.months)
    age_4y = Age(value=Decimal("4"), unit=AgeUnit.years)
    age_7y = Age(value=Decimal("7"), unit=AgeUnit.years)
    age_16y = Age(value=Decimal("16"), unit=AgeUnit.years)

    band_6m = resolve_vitals_population_band(age_6m, cfg)
    band_4y = resolve_vitals_population_band(age_4y, cfg)
    band_7y = resolve_vitals_population_band(age_7y, cfg)
    band_16y = resolve_vitals_population_band(age_16y, cfg)

    assert band_6m == "paediatric_1m_1y"
    assert band_4y == "paediatric_1_5y"
    assert band_7y == "paediatric_5_12y"
    assert band_16y == "paediatric_12_18y"
    assert len({band_6m, band_4y, band_7y, band_16y}) == 4

    # With production config (all NEEDS_SOURCE), each band emits 0 flags and logs skipped_flags
    for age_str, unit, expected_band in [
        ("6", AgeUnit.months, "paediatric_1m_1y"),
        ("4", AgeUnit.years, "paediatric_1_5y"),
        ("16", AgeUnit.years, "paediatric_12_18y"),
    ]:
        p = _make_patient(age_str, unit, hr=165, sbp=70, rr=40)
        flags, skipped, resolved_band = derive_vitals_flags_with_trace(p, config=cfg)
        assert resolved_band == expected_band
        assert flags == []
        assert len(skipped) > 0

    # If a paediatric age band is missing from config, fail closed
    empty_bands_cfg = VitalsFlagsConfig(
        version="2.0.0",
        age_classification=cfg.age_classification.model_copy(update={"paediatric_bands": []}),
        populations={},
    )
    p_4y = _make_patient("4", AgeUnit.years, hr=165)
    flags_unmatched, skipped_unmatched, band_unmatched = derive_vitals_flags_with_trace(
        p_4y, config=empty_bands_cfg
    )
    assert band_unmatched is None
    assert flags_unmatched == []
    assert any("UNMATCHED_PAEDIATRIC_AGE_BAND" in s for s in skipped_unmatched)


def test_no_flag_from_other_band_or_population() -> None:
    """FG-02 metamorphic: changing age across a band/population boundary never reuses cut-offs."""
    base_cfg = load_vitals_flags_config(get_data_dir())
    verified_prov = _make_verified_provenance()

    # Configure distinct verified HR thresholds per band/population:
    # paediatric_1m_1y: > 180
    # paediatric_1_5y: > 150
    # paediatric_5_12y: > 130
    # paediatric_12_18y: > 110
    # adult: > 100
    # neonate: NEEDS_SOURCE
    test_cfg = VitalsFlagsConfig(
        version="2.0.0",
        age_classification=base_cfg.age_classification,
        populations={
            "neonate": [
                VitalsFlagRule(
                    id="VF_NEO_HR",
                    flag="tachycardia_neonate",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=None,
                    status=RuleStatus.NEEDS_SOURCE,
                    provenance=_make_unverified_provenance(),
                )
            ],
            "paediatric_1m_1y": [
                VitalsFlagRule(
                    id="VF_P1_HR",
                    flag="tachycardia_1m_1y",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("180"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                )
            ],
            "paediatric_1_5y": [
                VitalsFlagRule(
                    id="VF_P2_HR",
                    flag="tachycardia_1_5y",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("150"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                )
            ],
            "paediatric_5_12y": [
                VitalsFlagRule(
                    id="VF_P3_HR",
                    flag="tachycardia_5_12y",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("130"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                )
            ],
            "paediatric_12_18y": [
                VitalsFlagRule(
                    id="VF_P4_HR",
                    flag="tachycardia_12_18y",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("110"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                )
            ],
            "adult": [
                VitalsFlagRule(
                    id="VF_ADULT_HR",
                    flag="tachycardia_adult",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("100"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                )
            ],
        },
    )

    # At HR = 140:
    # - 10 days (neonate): []
    # - 6 months (1m_1y, cutoff 180): []
    # - 4 years (1_5y, cutoff 150): []
    # - 8 years (5_12y, cutoff 130): ["tachycardia_5_12y"]
    # - 16 years (12_18y, cutoff 110): ["tachycardia_12_18y"]
    # - 25 years (adult, cutoff 100): ["tachycardia_adult"]
    assert derive_vitals_flags(_make_patient("10", AgeUnit.days, hr=140), config=test_cfg) == []
    assert derive_vitals_flags(_make_patient("6", AgeUnit.months, hr=140), config=test_cfg) == []
    assert derive_vitals_flags(_make_patient("4", AgeUnit.years, hr=140), config=test_cfg) == []
    assert derive_vitals_flags(_make_patient("8", AgeUnit.years, hr=140), config=test_cfg) == [
        "tachycardia_5_12y"
    ]
    assert derive_vitals_flags(_make_patient("16", AgeUnit.years, hr=140), config=test_cfg) == [
        "tachycardia_12_18y"
    ]
    assert derive_vitals_flags(_make_patient("25", AgeUnit.years, hr=140), config=test_cfg) == [
        "tachycardia_adult"
    ]


def test_no_active_rule_without_verified_provenance() -> None:
    """FG-02: Scan all data/retrieval/*.yaml; zero ACTIVE rules without verified provenance."""
    retrieval_dir = get_data_dir() / "retrieval"
    yaml_files = sorted(retrieval_dir.glob("*.yaml"))
    assert len(yaml_files) >= 4

    violations: list[str] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            status = node.get("status")
            prov = node.get("provenance")
            if status == "ACTIVE":
                verified = isinstance(prov, dict) and prov.get("verified") is True
                if not verified:
                    rule_id = node.get("id", path)
                    violations.append(f"{path} ({rule_id}): status=ACTIVE with verified!=True")
            for k, v in node.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{path}[{idx}]")

    for yf in yaml_files:
        raw = yaml.safe_load(yf.read_text(encoding="utf-8"))
        _walk(raw, yf.name)

    assert violations == [], f"Unsourced ACTIVE rules found in data/retrieval/: {violations}"


def test_vitals_only_retrieval_degrades_to_abstain_when_flags_needs_source() -> None:
    """FG-02: With all flags NEEDS_SOURCE, a no-syndrome query abstains EMPTY_QUERY."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    patient = _make_patient("50", AgeUnit.years, hr=130, sbp=80, rr=28, syndrome=None)

    report = retrieve_protocol_chunks(patient, index)
    assert report.abstained is True
    assert report.abstain_code == AbstainCode.EMPTY_QUERY
    assert report.chunks == []
    assert len(report.skipped_flags) > 0
    assert any("NEEDS_SOURCE" in s for s in report.skipped_flags)


@pytest.mark.parametrize(
    ("val_str", "unit", "expected_pop"),
    [
        ("0", AgeUnit.days, PopulationCategory.neonate),
        ("15", AgeUnit.days, PopulationCategory.neonate),
        ("28", AgeUnit.days, PopulationCategory.neonate),
        ("0.5", AgeUnit.months, PopulationCategory.neonate),
        ("0.9", AgeUnit.months, PopulationCategory.neonate),
        ("28.01", AgeUnit.days, PopulationCategory.paediatric),
        ("28.5", AgeUnit.days, PopulationCategory.paediatric),
        ("29", AgeUnit.days, PopulationCategory.paediatric),
        ("1", AgeUnit.months, PopulationCategory.paediatric),
        ("17.99", AgeUnit.years, PopulationCategory.paediatric),
        ("18", AgeUnit.years, PopulationCategory.adult),
        ("65", AgeUnit.years, PopulationCategory.adult),
    ],
)
def test_age_boundary_matrix(
    val_str: str,
    unit: AgeUnit,
    expected_pop: PopulationCategory,
) -> None:
    """FG-04: Age boundary matrix across days, months, and years."""
    age = Age(value=Decimal(val_str), unit=unit)
    assert age.population_category == expected_pop


def test_months_below_neonate_cutoff_is_neonate() -> None:
    """FG-04: 0.5 months (~15 days) is classified as neonate, never paediatric."""
    half_month = Age(value=Decimal("0.5"), unit=AgeUnit.months)
    assert half_month.to_days() == Decimal("15.0")
    assert half_month.population_category == PopulationCategory.neonate

    quarter_month = Age(value=Decimal("0.25"), unit=AgeUnit.months)
    assert quarter_month.to_days() == Decimal("7.50")
    assert quarter_month.population_category == PopulationCategory.neonate

    # Ambiguous 0 months or 0 years must be flagged and classified into the more restrictive
    # neonate population (HD-2 fail-closed default)
    zero_months = Age(value=Decimal("0"), unit=AgeUnit.months)
    assert zero_months.is_ambiguous_boundary is True
    assert zero_months.population_category == PopulationCategory.neonate
    p_zero_m = _make_patient("0", AgeUnit.months, hr=160)
    flags_zm, skipped_zm, _ = derive_vitals_flags_with_trace(p_zero_m)
    assert flags_zm == []
    assert any("AMBIGUOUS_ZERO_AGE_UNIT" in s for s in skipped_zm)

    zero_years = Age(value=Decimal("0"), unit=AgeUnit.years)
    assert zero_years.is_ambiguous_boundary is True
    assert zero_years.population_category == PopulationCategory.neonate


@settings(max_examples=200, deadline=None)
@given(
    age1_spec=st.one_of(
        st.tuples(
            st.decimals(min_value=Decimal("0"), max_value=Decimal("365"), places=2),
            st.just(AgeUnit.days),
        ),
        st.tuples(
            st.decimals(min_value=Decimal("0.05"), max_value=Decimal("48"), places=2),
            st.just(AgeUnit.months),
        ),
        st.tuples(
            st.decimals(min_value=Decimal("0.05"), max_value=Decimal("120"), places=2),
            st.just(AgeUnit.years),
        ),
    ),
    age2_spec=st.one_of(
        st.tuples(
            st.decimals(min_value=Decimal("0"), max_value=Decimal("365"), places=2),
            st.just(AgeUnit.days),
        ),
        st.tuples(
            st.decimals(min_value=Decimal("0.05"), max_value=Decimal("48"), places=2),
            st.just(AgeUnit.months),
        ),
        st.tuples(
            st.decimals(min_value=Decimal("0.05"), max_value=Decimal("120"), places=2),
            st.just(AgeUnit.years),
        ),
    ),
)
def test_population_category_monotone_in_age(
    age1_spec: tuple[Decimal, AgeUnit],
    age2_spec: tuple[Decimal, AgeUnit],
) -> None:
    """FG-04 property: population_category is monotone non-decreasing in age across all units."""
    a1 = Age(value=age1_spec[0], unit=age1_spec[1])
    a2 = Age(value=age2_spec[0], unit=age2_spec[1])

    if a1.to_days() <= a2.to_days():
        assert _POP_RANK[a1.population_category] <= _POP_RANK[a2.population_category]
    else:
        assert _POP_RANK[a1.population_category] >= _POP_RANK[a2.population_category]
