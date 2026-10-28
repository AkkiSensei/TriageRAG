"""Streamlit decision support and protocol verification UI for TriageRAG.

Safety Properties (Rules R1, R2, R3, R7, R11, R12):
1. Code decides; LLM explains: Fixed top banner & verdicts come solely from EngineReport.
2. Never display bare word 'CLEAR'.
3. 'UNSOURCED DRAFT' badges on alerts from unreviewed rules.
4. 'SYNTHETIC' badges on protocol text.
5. Untrusted chief complaint is NEVER rendered with unsafe_allow_html.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import streamlit as st

from triagerag.config import get_audit_path, get_data_dir
from triagerag.contracts.enums import (
    AgeUnit,
    Consciousness,
)
from triagerag.contracts.schemas import (
    Age,
    Measured,
    OverrideRecord,
    Patient,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import Retriever
from triagerag.rag.service import RetrievalService
from triagerag.ui.components import (
    get_preloaded_scenario,
    render_alerts_and_blocks,
    render_coverage_gaps,
    render_disclaimer_header,
    render_llm_narrative,
    render_top_banner,
    render_unverified_section,
    render_verified_plan,
)

st.set_page_config(
    page_title="TriageRAG Decision Support",
    page_icon="🏥",
    layout="wide",
)


@st.cache_resource
def load_triage_resources() -> tuple[ClinicalRegistry, Retriever]:
    """Load clinical registry and protocol index once via RetrievalService."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    service = RetrievalService.create_default(data_dir)
    return registry, service.index


def main() -> None:
    # Mandatory Disclaimer (top of every UI page per Section 1)
    render_disclaimer_header()

    st.title("TriageRAG Emergency Decision Support & Verification")

    registry, index = load_triage_resources()

    # Sidebar: Preloaded Scenarios & Config
    st.sidebar.header("Scenario & Controls")
    scenario_option = st.sidebar.selectbox(
        "Select Clinical Scenario",
        options=["BLOCK", "UNVERIFIED", "HIGH", "CLEAN", "Custom Patient"],
        index=0,
        help="Choose one of the 4 verified preloaded scenarios or enter custom data.",
    )

    include_complaint_in_llm = st.sidebar.checkbox(
        "Pass complaint to LLM (Rule R7 flag)",
        value=False,
        help="If enabled, passes untrusted complaint strictly inside a delimited prompt block.",
    )

    overrides: list[OverrideRecord] = []
    if scenario_option in ("HIGH", "Custom Patient"):
        with st.sidebar.expander("Clinician Overrides (HIGH Alert Only)", expanded=False):
            st.caption("Rule R11: BLOCK alerts cannot be overridden. Only HIGH alerts may be.")
            override_rule_id = st.text_input("Rule ID to Override", value="")
            override_step_no = st.number_input("Step Number", min_value=1, value=1)
            override_reason = st.text_area(
                "Clinical Rationale (min 15 chars)",
                value="",
                help="Logged to immutable audit chain.",
            )
            override_clinician = st.text_input("Clinician ID", value="")
            if override_rule_id and len(override_reason) >= 15 and override_clinician:
                overrides.append(
                    OverrideRecord(
                        rule_id=override_rule_id,
                        step_number=int(override_step_no),
                        reason=override_reason,
                        clinician_id=override_clinician,
                    )
                )

    # Patient Data Selection / Input
    patient: Patient
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    if scenario_option != "Custom Patient":
        patient, default_overrides = get_preloaded_scenario(scenario_option)
        if not overrides and default_overrides:
            overrides = default_overrides
        st.info(f"Loaded Scenario: **{scenario_option}**")
    else:
        st.subheader("Patient Clinical Assessment Form")
        with st.form("custom_patient_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                age_val = st.number_input("Age", min_value=0, max_value=120, value=35)
                age_unit_str = st.selectbox("Age Unit", ["years", "months", "days"], index=0)
                sex = st.selectbox("Sex", ["male", "female", "other", "unknown"], index=0)
                pregnancy = st.selectbox(
                    "Pregnancy", ["no", "yes", "not_applicable", "unknown"], index=0
                )
            with col2:
                weight_status = st.selectbox("Weight Status", ["measured", "unknown"], index=0)
                weight_val = (
                    Decimal(str(st.number_input("Weight (kg)", value=70.0, step=0.1)))
                    if weight_status == "measured"
                    else None
                )
                syndrome_choice = st.selectbox(
                    "Suspected Clinical Syndrome",
                    options=[
                        "None",
                        "anaphylaxis",
                        "chest_pain",
                        "severe_asthma",
                        "hypoglycemia",
                        "paediatric_sepsis",
                        "altered_mental_status",
                    ],
                    index=1,
                )
            with col3:
                hr_val = st.number_input("Heart Rate (BPM)", min_value=0, max_value=300, value=90)
                sbp_val = st.number_input(
                    "Systolic BP (mmHg)", min_value=0, max_value=300, value=120
                )
                rr_val = st.number_input("Resp Rate (BPM)", min_value=0, max_value=100, value=16)
                spo2_val = st.number_input("SpO2 (%)", min_value=0, max_value=100, value=98)
                o2_val = st.selectbox("Supplemental O2", ["no", "yes", "unknown"], index=0)
                consciousness_val = st.selectbox(
                    "Consciousness Level (AVPU+C)",
                    options=["A", "C", "V", "P", "U"],
                    index=0,
                    help="C = New Confusion (NEWS2/PEWS treat distinctly)",
                )

            st.write("---")
            complaint_text = st.text_input(
                "Chief Complaint (Untrusted Free-Text, Max 500 chars)",
                value="Chest tightness and dyspnea",
                max_chars=500,
            )

            st.form_submit_button("Run Clinical Evaluation")

        age_unit = (
            AgeUnit.years
            if age_unit_str == "years"
            else (AgeUnit.months if age_unit_str == "months" else AgeUnit.days)
        )
        patient = Patient(
            assessed_at=now,
            age=Age(value=Decimal(str(age_val)), unit=age_unit),
            sex=sex,  # type: ignore[arg-type]
            pregnancy=pregnancy,  # type: ignore[arg-type]
            weight_kg=(
                Measured[Decimal](value=weight_val, source="measured")
                if weight_val
                else Measured[Decimal]()
            ),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=int(hr_val), source="measured"),
                systolic_bp_mmhg=Measured[int](value=int(sbp_val), source="measured"),
                respiratory_rate_bpm=Measured[int](value=int(rr_val), source="measured"),
                spo2_percent=Measured[int](value=int(spo2_val), source="measured"),
                supplemental_o2=(
                    Measured[str](value=o2_val, source="measured")
                    if o2_val != "unknown"
                    else Measured[str]()
                ),
                consciousness=Measured[Consciousness](
                    value=Consciousness(consciousness_val), source="measured"
                ),
            ),
            medication_history_status="confirmed_none",
            medications=[],
            allergy_history_status="confirmed_nkda",
            allergies=[],
            renal_impairment="no",
            hepatic_impairment="no",
            suspected_syndrome=syndrome_choice if syndrome_choice != "None" else None,
            chief_complaint_untrusted=complaint_text,
        )

    # Display Untrusted Complaint Safely (Rule R7: never rendered with unsafe_allow_html)
    st.write("### Patient Presentation")
    st.text(f"Untrusted Chief Complaint: {patient.chief_complaint_untrusted}")

    # Execute Orchestrator
    llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)
    config = {
        "include_complaint_in_llm": include_complaint_in_llm,
        "audit_log_path": get_audit_path(),
    }

    response = run_triage(
        patient=patient,
        registry=registry,
        llm=llm,
        index=index,
        overrides=overrides,
        config=config,
    )

    engine = response.engine

    # Mandatory Layout Order (Section 12):
    # 1. Fixed Top Banner
    render_top_banner(engine)

    # 2. Alerts and blocked drugs (struck-through with rule ID and provenance)
    render_alerts_and_blocks(engine)

    # 3. What I couldn't check (Section 12)
    render_unverified_section(engine)

    # 4. Coverage Gaps (Section 12)
    render_coverage_gaps(engine)

    # 5. Verified Plan Steps with citation chips showing the source span (Section 12)
    render_verified_plan(response.verified_steps)

    # 6. LLM narrative last (Section 12)
    render_llm_narrative(response)


if __name__ == "__main__":
    main()
