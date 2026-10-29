"""Fix Gate G3 unit tests: Abstention logic & context hygiene (FG-03, FG-05, FG-15, HD-4).

AGENT_AUTHORED_UNREVIEWED: Tests authored by agent for Fix Gate G3 verification.

Safety Properties Tested:
1. FG-03 / HD-4: When retrieval.abstain_code == AbstainCode.SYNDROME_INFERRED, no step in
   verify_plan / run_triage may reach StepStatus.APPROVED; maximum status is
   StepStatus.REQUIRES_CLINICIAN_CONFIRMATION.
2. FG-03: API response and UI/CLI payloads surface SYNDROME_INFERRED and
   REQUIRES_CLINICIAN_CONFIRMATION; AMBIGUOUS_MARGIN returns a plan-less response with reason;
   audit log records SYNDROME_INFERRED.
3. FG-05: Thresholds default to None all the way down; syndrome-inferred mode uses
   config.syndrome_inferred_threshold; known-syndrome mode uses config.calibrated_threshold;
   every key in data/retrieval/config.yaml is read; no import-time config load exists.
4. FG-15: Immutable RetrievalContext is built per data_dir; RetrievalService.reload() clears
   caches and picks up edited YAML on disk; custom data_dir is isolated from default;
   no get_data_dir() calls occur in the retrieval hot path.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import (
    AbstainCode,
    ActionType,
    AgeUnit,
    ContentOrigin,
    DoseUnit,
    Route,
    RuleStatus,
    SourceStatus,
    StepStatus,
)
from triagerag.contracts.schemas import (
    Age,
    ExplicitDose,
    Measured,
    OverrideRecord,
    Patient,
    PlanDraft,
    PlanStepDraft,
    Provenance,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.normalize.clause_parser import parse_clause_drug_actions
from triagerag.orchestrator import run_triage
from triagerag.rag.abstain import normalize_relevance_score
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import (
    RetrievalContext,
    VitalsFlagRule,
    VitalsFlagsConfig,
    build_retrieval_context,
    load_vitals_flags_config,
    retrieve_protocol_chunks,
)
from triagerag.rag.service import RetrievalService
from triagerag.verify.citations import load_action_cues
from triagerag.verify.plan_verifier import verify_plan


def _make_verified_vitals_cfg(data_dir: Path | None = None) -> VitalsFlagsConfig:
    base_cfg = load_vitals_flags_config(data_dir or get_data_dir())
    verified_prov = Provenance(
        source_doc="TEST_VERIFIED_GUIDELINE_FIXTURE",
        section_ref="SEC_1",
        version_or_date="2026-01",
        source_status=SourceStatus.REVIEWED,
        content_origin=ContentOrigin.SOURCE_EXTRACT,
        verified=True,
        reviewer="clinician_test_fixture",
    )
    return VitalsFlagsConfig(
        version="2.0.0",
        age_classification=base_cfg.age_classification,
        populations={
            "adult": [
                VitalsFlagRule(
                    id="VF_TEST_ADULT_HYPOTENSION",
                    flag="hypotension",
                    field="systolic_bp_mmhg",
                    operator="<",
                    threshold=Decimal("90"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                ),
                VitalsFlagRule(
                    id="VF_TEST_ADULT_TACHYPNEA",
                    flag="tachypnea",
                    field="respiratory_rate_bpm",
                    operator=">",
                    threshold=Decimal("22"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                ),
                VitalsFlagRule(
                    id="VF_TEST_ADULT_HYPOXIA",
                    flag="hypoxia",
                    field="spo2_percent",
                    operator="<",
                    threshold=Decimal("92"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                ),
            ],
            "paediatric_1_5y": [
                VitalsFlagRule(
                    id="VF_TEST_PAED_FEVER",
                    flag="fever",
                    field="temperature_c",
                    operator=">",
                    threshold=Decimal("38.0"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                ),
                VitalsFlagRule(
                    id="VF_TEST_PAED_TACHYCARDIA",
                    flag="tachycardia",
                    field="heart_rate_bpm",
                    operator=">",
                    threshold=Decimal("140"),
                    status=RuleStatus.ACTIVE,
                    provenance=verified_prov,
                ),
            ],
        },
    )


def _make_asthma_inferred_patient() -> Patient:
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal("30"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(
            respiratory_rate_bpm=Measured[int](value=30, source="measured"),
            spo2_percent=Measured[int](value=88, source="measured"),
            heart_rate_bpm=Measured[int](value=92, source="measured"),
            systolic_bp_mmhg=Measured[int](value=122, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=None,
    )


def test_inferred_syndrome_never_approves_any_step() -> None:
    """FG-03 / HD-4: When abstain_code == SYNDROME_INFERRED, no step may be APPROVED."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    patient = _make_asthma_inferred_patient()

    node_text = (
        "1. IF the adult patient presents with acute bronchospasm, tachypnea, or hypoxia:\n"
        "   THEN administer nebulized salbutamol immediately and provide supplemental oxygen."
    )
    chunk = RetrievedChunk(
        doc_id="EMERG_SEVERE_ASTHMA",
        section="Acute Bronchospasm Management",
        chunk_id="SEVERE_ASTHMA_01_NODE_1",
        parent_id="SEVERE_ASTHMA_01",
        text=node_text,
        population="adult",
        syndrome="severe_asthma",
        drug_actions=parse_clause_drug_actions(node_text),
    )

    draft = PlanDraft(
        matched_protocol_title="Acute Bronchospasm Management",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction=(
                    "Administer nebulized therapy immediately and provide supplemental oxygen"
                ),
                drug_id="salbutamol",
                requested_dose=ExplicitDose(amount=Decimal("2.5"), unit=DoseUnit.mg),
                route=Route.nebulized,
                citations=[
                    SpanCitation(
                        doc_id="EMERG_SEVERE_ASTHMA",
                        section="Acute Bronchospasm Management",
                        chunk_id="SEVERE_ASTHMA_01_NODE_1",
                        quoted_span=(
                            "administer nebulized salbutamol immediately and provide "
                            "supplemental oxygen"
                        ),
                    )
                ],
            )
        ],
    )

    # 1. With AbstainCode.NONE (known syndrome), the step is APPROVED
    steps_confirmed, _, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=registry,
        retrieval_abstain_code=AbstainCode.NONE,
    )
    assert steps_confirmed[0].status == StepStatus.APPROVED

    # 2. With AbstainCode.SYNDROME_INFERRED, the exact same step is capped at
    # StepStatus.REQUIRES_CLINICIAN_CONFIRMATION and never APPROVED
    steps_inferred, _, _, _ = verify_plan(
        patient=patient,
        draft=draft,
        baseline_alerts=[],
        retrieved_chunks=[chunk],
        registry=registry,
        retrieval_abstain_code=AbstainCode.SYNDROME_INFERRED,
    )
    assert steps_inferred[0].status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION
    assert steps_inferred[0].status != StepStatus.APPROVED
    assert any("SYNDROME_INFERRED" in r for r in steps_inferred[0].rejection_reasons)

    # 3. End-to-end via run_triage with an index that has verified vitals_flags_config
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    ctx = build_retrieval_context(data_dir).model_copy(
        update={"vitals_flags": _make_verified_vitals_cfg(data_dir)}
    )
    index.retrieval_context = ctx
    resp = run_triage(
        patient=patient,
        registry=registry,
        llm=FakeLLM(profile=FakeLLMProfile.COMPLIANT),
        index=index,
        overrides=[
            OverrideRecord(
                rule_id="SYNDROME_INFERRED",
                step_number=1,
                reason="Attempting to override inferred syndrome",
                clinician_id="dr_test",
            )
        ],
    )
    assert resp.retrieval is not None
    assert resp.retrieval.abstain_code == AbstainCode.SYNDROME_INFERRED
    assert len(resp.verified_steps) > 0
    assert all(s.status != StepStatus.APPROVED for s in resp.verified_steps)
    assert any(s.status == StepStatus.REQUIRES_CLINICIAN_CONFIRMATION for s in resp.verified_steps)


def test_inferred_syndrome_banner_in_api_and_ui_payload() -> None:
    """FG-03: API/UI payload and Streamlit/React helpers surface SYNDROME_INFERRED."""
    from triagerag.ui.components import format_step_status_display

    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    patient = _make_asthma_inferred_patient()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    index.retrieval_context = build_retrieval_context(data_dir).model_copy(
        update={"vitals_flags": _make_verified_vitals_cfg(data_dir)}
    )

    resp = run_triage(
        patient=patient,
        registry=registry,
        llm=FakeLLM(profile=FakeLLMProfile.COMPLIANT),
        index=index,
    )
    payload = resp.model_dump(mode="json")
    assert payload["retrieval"]["abstain_code"] == "SYNDROME_INFERRED"
    assert payload["retrieval"]["abstained"] is False
    assert "inferred" in (payload["retrieval"]["reason"] or "").lower()
    assert any(s["status"] == "REQUIRES_CLINICIAN_CONFIRMATION" for s in payload["verified_steps"])
    assert "CONFIRMATION" in format_step_status_display(StepStatus.REQUIRES_CLINICIAN_CONFIRMATION)


def test_ambiguous_margin_returns_planless_with_reason() -> None:
    """FG-03: AMBIGUOUS_MARGIN abstains and yields plan-less response with reason."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    index.retrieval_context = build_retrieval_context(data_dir).model_copy(
        update={"vitals_flags": _make_verified_vitals_cfg(data_dir)}
    )

    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    ambiguous_patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("50"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome=None,
    )

    resp = run_triage(
        patient=ambiguous_patient,
        registry=registry,
        llm=FakeLLM(profile=FakeLLMProfile.COMPLIANT),
        index=index,
    )
    assert resp.retrieval is not None
    assert resp.retrieval.abstained is True
    assert resp.retrieval.abstain_code == AbstainCode.AMBIGUOUS_MARGIN
    assert resp.retrieval.reason is not None
    assert "margin" in resp.retrieval.reason.lower()
    assert resp.verified_steps == []
    assert resp.llm_fallback_mode is True


def test_audit_records_syndrome_inferred_code(tmp_path: Path) -> None:
    """FG-03: Cryptographic audit log records abstain_code == SYNDROME_INFERRED."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    index.retrieval_context = build_retrieval_context(data_dir).model_copy(
        update={"vitals_flags": _make_verified_vitals_cfg(data_dir)}
    )
    audit_path = tmp_path / "audit_fg3.jsonl"

    resp = run_triage(
        patient=_make_asthma_inferred_patient(),
        registry=registry,
        llm=FakeLLM(profile=FakeLLMProfile.COMPLIANT),
        index=index,
        config={"audit_log_path": str(audit_path)},
    )
    assert resp.audit_hash != "UNAUDITED"
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["abstain_code"] == "SYNDROME_INFERRED"


def test_inferred_mode_uses_inferred_threshold() -> None:
    """FG-05: Inferred mode uses syndrome_inferred_threshold, not calibrated_threshold."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    base_ctx = build_retrieval_context(data_dir)
    verified_vf = _make_verified_vitals_cfg(data_dir)

    patient = _make_asthma_inferred_patient()
    # First measure the normalized top score on this vitals-only patient
    probe_ctx = base_ctx.model_copy(
        update={
            "vitals_flags": verified_vf,
            "config": base_ctx.config.model_copy(
                update={"calibrated_threshold": 0.05, "syndrome_inferred_threshold": 0.05}
            ),
        }
    )
    probe_report = retrieve_protocol_chunks(patient, index, context=probe_ctx)
    assert probe_report.abstained is False
    assert probe_report.abstain_code == AbstainCode.SYNDROME_INFERRED
    raw_top = float(probe_report.chunks[0].score)
    norm_top = normalize_relevance_score(raw_top)
    assert 0.10 < norm_top < 0.95

    # Now set calibrated_threshold LOW (0.05) but syndrome_inferred_threshold HIGH (norm_top + 0.05)
    # Without explicit threshold parameter, inferred mode MUST use syndrome_inferred_threshold
    # and abstain with LOW_CONFIDENCE!
    high_inferred_ctx = base_ctx.model_copy(
        update={
            "vitals_flags": verified_vf,
            "config": base_ctx.config.model_copy(
                update={
                    "calibrated_threshold": 0.05,
                    "syndrome_inferred_threshold": round(min(0.99, norm_top + 0.05), 4),
                }
            ),
        }
    )
    report_abstain = retrieve_protocol_chunks(patient, index, context=high_inferred_ctx)
    assert report_abstain.abstained is True
    assert report_abstain.abstain_code == AbstainCode.LOW_CONFIDENCE

    # Also verify via RetrievalService.retrieve() with no threshold argument
    service = RetrievalService(
        data_dir=data_dir,
        ingest_report=RetrievalService.create_default(data_dir).ingest_report,
        manifest=high_inferred_ctx.manifest,
        config=high_inferred_ctx.config,
        index=index,
        context=high_inferred_ctx,
    )
    svc_report = service.retrieve(patient)
    assert svc_report.abstained is True
    assert svc_report.abstain_code == AbstainCode.LOW_CONFIDENCE


def test_known_syndrome_threshold_boundary() -> None:
    """FG-05: Known-syndrome retrieval succeeds just below and abstains just above norm_best."""
    data_dir = get_data_dir()
    index = BM25ClinicalIndex(ingest_protocols(data_dir))
    base_ctx = build_retrieval_context(data_dir)

    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("55"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )

    probe = retrieve_protocol_chunks(patient, index, context=base_ctx)
    assert probe.abstained is False
    raw_top = float(probe.chunks[0].score)
    norm_top = normalize_relevance_score(raw_top)
    assert 0.10 < norm_top < 0.95

    below_ctx = base_ctx.model_copy(
        update={
            "config": base_ctx.config.model_copy(
                update={"calibrated_threshold": round(norm_top - 0.02, 4)}
            )
        }
    )
    rep_below = retrieve_protocol_chunks(patient, index, context=below_ctx)
    assert rep_below.abstained is False
    assert rep_below.abstain_code == AbstainCode.NONE

    above_ctx = base_ctx.model_copy(
        update={
            "config": base_ctx.config.model_copy(
                update={"calibrated_threshold": round(min(0.99, norm_top + 0.02), 4)}
            )
        }
    )
    rep_above = retrieve_protocol_chunks(patient, index, context=above_ctx)
    assert rep_above.abstained is True
    assert rep_above.abstain_code == AbstainCode.LOW_CONFIDENCE


def test_every_config_key_is_read() -> None:
    """FG-05: Every key in data/retrieval/config.yaml has an AST attribute reader in src/."""
    cfg_path = get_data_dir() / "retrieval" / "config.yaml"
    raw_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert isinstance(raw_cfg, dict)
    config_keys = set(raw_cfg.keys())
    assert len(config_keys) >= 10

    src_dir = get_repo_root() / "src" / "triagerag"
    accessed_attrs: set[str] = set()
    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                accessed_attrs.add(node.attr)

    unread_keys = config_keys - accessed_attrs
    assert unread_keys == set(), f"Config keys in config.yaml never read in src/: {unread_keys}"


def test_no_import_time_config_load() -> None:
    """FG-05: Importing triagerag.rag.abstain and triagerag.rag.retrieve does not load YAML."""
    code = (
        "import triagerag.rag.abstain as a, triagerag.rag.retrieve as r, "
        "triagerag.verify.citations as c; "
        "assert a.load_retrieval_config.cache_info().currsize == 0, "
        "'abstain loaded at import: ' + str(a.load_retrieval_config.cache_info()); "
        "assert r.load_vitals_flags_config.cache_info().currsize == 0, "
        "'retrieve loaded at import: ' + str(r.load_vitals_flags_config.cache_info()); "
        "assert c.load_action_cues.cache_info().currsize == 0, "
        "'citations loaded at import: ' + str(c.load_action_cues.cache_info()); "
        "assert not hasattr(a, 'DEFAULT_MIN_RETRIEVAL_THRESHOLD')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Import-time config load detected: {proc.stderr or proc.stdout}"


def test_reload_picks_up_edited_config(tmp_path: Path) -> None:
    """FG-15: RetrievalService.reload() clears caches and picks up edited YAML on disk."""
    custom_dir = tmp_path / "data_copy"
    shutil.copytree(get_data_dir(), custom_dir)

    svc1 = RetrievalService.create_default(custom_dir)
    assert svc1.config.top_k == 5
    old_hash = svc1.config_hash

    # Edit retrieval/config.yaml and retrieval/action_cues.yaml on disk
    cfg_path = custom_dir / "retrieval" / "config.yaml"
    cfg_data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg_data["top_k"] = 3
    cfg_data["calibrated_threshold"] = 0.22
    cfg_path.write_text(yaml.safe_dump(cfg_data, sort_keys=False), encoding="utf-8")

    cues_path = custom_dir / "retrieval" / "action_cues.yaml"
    cues_data = yaml.safe_load(cues_path.read_text(encoding="utf-8"))
    cues_data["min_overlap_threshold"] = 0.18
    cues_path.write_text(yaml.safe_dump(cues_data, sort_keys=False), encoding="utf-8")

    svc2 = RetrievalService.reload(custom_dir)
    assert svc2.config.top_k == 3
    assert svc2.config.calibrated_threshold == 0.22
    assert svc2.config_hash != old_hash
    assert svc2.context.action_cues.min_overlap_threshold == 0.18
    assert load_action_cues(custom_dir).min_overlap_threshold == 0.18


def test_custom_data_dir_isolated_from_default(tmp_path: Path) -> None:
    """FG-15: Custom data_dir RetrievalService is strictly isolated from default get_data_dir()."""
    custom_dir = tmp_path / "custom_data"
    shutil.copytree(get_data_dir(), custom_dir)

    # Modify custom_dir manifest to remove 'anaphylaxis' from controlled_syndromes and remove file
    manifest_path = custom_dir / "corpus" / "manifest.yaml"
    manifest_raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_raw["controlled_syndromes"] = [
        s for s in manifest_raw["controlled_syndromes"] if s != "anaphylaxis"
    ]
    manifest_raw["documents"] = [
        d for d in manifest_raw["documents"] if d["syndrome"] != "anaphylaxis"
    ]
    manifest_raw["syndrome_aliases"] = {
        k: v for k, v in manifest_raw["syndrome_aliases"].items() if v != "anaphylaxis"
    }
    manifest_path.write_text(yaml.safe_dump(manifest_raw, sort_keys=False), encoding="utf-8")
    (custom_dir / "protocols_synthetic" / "anaphylaxis.md").unlink()

    custom_svc = RetrievalService.reload(custom_dir)
    default_svc = RetrievalService.create_default(get_data_dir())

    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    patient = Patient(
        assessed_at=now,
        age=Age(value=Decimal("35"), unit=AgeUnit.years),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("65.0"), source="measured"),
        vitals=Vitals(),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="anaphylaxis",
    )

    rep_custom = custom_svc.retrieve(patient)
    rep_default = default_svc.retrieve(patient)

    # Custom data_dir has no anaphylaxis in its manifest/corpus -> UNKNOWN_SYNDROME
    assert rep_custom.abstained is True
    assert rep_custom.abstain_code == AbstainCode.UNKNOWN_SYNDROME

    # Default data_dir still has anaphylaxis -> succeeds
    assert rep_default.abstained is False
    assert rep_default.abstain_code == AbstainCode.NONE
    assert isinstance(custom_svc.context, RetrievalContext)


def test_no_get_data_dir_calls_in_retrieval_hot_path() -> None:
    """FG-15: AST check that retrieval hot-path functions do not call get_data_dir()."""
    hot_path_targets: list[tuple[Path, set[str]]] = [
        (
            get_repo_root() / "src" / "triagerag" / "rag" / "retrieve.py",
            {
                "retrieve_protocol_chunks",
                "build_retrieval_query",
                "derive_vitals_flags",
                "derive_vitals_flags_with_trace",
                "normalize_syndrome",
                "resolve_vitals_population_band",
            },
        ),
        (
            get_repo_root() / "src" / "triagerag" / "rag" / "abstain.py",
            {
                "evaluate_abstention_with_code",
                "evaluate_abstention",
                "normalize_relevance_score",
            },
        ),
        (
            get_repo_root() / "src" / "triagerag" / "rag" / "service.py",
            {
                "retrieve",
                "explain",
            },
        ),
    ]

    violations: list[str] = []
    for py_path, fn_names in hot_path_targets:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in fn_names:
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Name)
                        and sub.func.id == "get_data_dir"
                    ):
                        violations.append(f"{py_path.name}::{node.name} calls get_data_dir()")

    assert violations == [], f"Found get_data_dir() calls in retrieval hot path: {violations}"
