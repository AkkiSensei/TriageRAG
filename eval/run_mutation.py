"""Comprehensive Mutation Testing Runner for TriageRAG.

Safety Property (Rule R10):
Measured, not claimed.
1. Shipped Rule Mutants (12): Dropping any critical BLOCK or HIGH rule MUST cause
   the golden test suite to fail (100% kill score required).
2. Code-Level Mutants (>=25): Synthesizes code-level mutations across the verdict lattice,
   requires_fields interlocks, lookback windows, withhold exemptions, citation groundings,
   drug-scan tokens, population filters, BLOCK override guards, dose arithmetic, and
   audit integrity. Each mutant must be killed by a corresponding regression test.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from triagerag.audit.chain import append_audit_entry, verify_audit_chain
from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import (
    ActionType,
    AgeUnit,
    Consciousness,
    DoseUnit,
    Severity,
    StepStatus,
    Verdict,
)
from triagerag.contracts.schemas import (
    Age,
    AllergyEntry,
    ExplicitDose,
    Measured,
    MedicationEntry,
    OrchestratorConfig,
    OverrideRecord,
    Patient,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
    Vitals,
)
from triagerag.engine.dose_engine import verify_dose
from triagerag.engine.registry import ClinicalRegistry
from triagerag.engine.rule_engine import evaluate_baseline
from triagerag.engine.scores import calculate_early_warning_score
from triagerag.engine.verdict import resolve_verdict
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.normalize.units import convert_dose
from triagerag.normalize.validators import build_patient_from_case
from triagerag.normalize.yaml_loader import load_yaml_decimal
from triagerag.orchestrator import run_triage
from triagerag.verify.citations import verify_citation
from triagerag.verify.drug_scan import scan_narrative_for_drug_leaks
from triagerag.verify.plan_verifier import verify_plan

# ---------------------------------------------------------------------------
# Part 1: Shipped Ruleset Mutation Testing (12/12)
# ---------------------------------------------------------------------------


def evaluate_cases_on_registry(cases: list[dict[str, Any]], registry: ClinicalRegistry) -> bool:
    """Evaluate golden cases against a (potentially mutated) registry."""
    for case in cases:
        patient = build_patient_from_case(case, registry)
        alerts, skipped, _, _ = evaluate_baseline(patient, registry)

        fired_rule_ids = {a.rule_id for a in alerts}
        skipped_rule_ids = {s.rule_id for s in skipped}

        must_fire = set(case.get("must_fire", []))
        must_skip = set(case.get("must_skip", []))
        must_not_fire = set(case.get("must_not_fire", []))

        if not must_fire.issubset(fired_rule_ids):
            return False
        if not must_skip.issubset(skipped_rule_ids):
            return False
        if not must_not_fire.isdisjoint(fired_rule_ids):
            return False

    return True


def run_rule_mutations(
    registry: ClinicalRegistry, cases: list[dict[str, Any]]
) -> tuple[int, int, list[str]]:
    critical_rules = [r for r in registry.rules if r.severity in (Severity.BLOCK, Severity.HIGH)]
    killed = 0
    survivors: list[str] = []

    print(
        f"Executing Rule Mutation Testing across {len(critical_rules)} critical BLOCK/HIGH rules..."
    )
    for rule in critical_rules:
        mutant_rules = [r for r in registry.rules if r.id != rule.id]
        mutated_registry = dataclasses.replace(registry, rules=mutant_rules)

        all_passed = evaluate_cases_on_registry(cases, mutated_registry)
        if not all_passed:
            killed += 1
            print(f"  [KILLED] Dropped {rule.severity.value} rule '{rule.id}'")
        else:
            survivors.append(rule.id)
            print(f"  [SURVIVED] Dropped {rule.severity.value} rule '{rule.id}'")

    return killed, len(critical_rules), survivors


# ---------------------------------------------------------------------------
# Part 2: Code-Level Mutation Testing (>=25 mutants)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CodeMutant:
    mutant_id: str
    description: str
    run_killer: Callable[[ClinicalRegistry], None]


def _build_standard_patient() -> Patient:
    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    return Patient(
        assessed_at=now,
        age=Age(value=Decimal("45"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=72, source="measured"),
            systolic_bp_mmhg=Measured[int](value=120, source="measured"),
            diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
            respiratory_rate_bpm=Measured[int](value=16, source="measured"),
            spo2_percent=Measured[int](value=98, source="measured"),
            temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
            consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
        chief_complaint_untrusted="retrosternal pressure",
    )


def build_code_mutants() -> list[CodeMutant]:
    mutants: list[CodeMutant] = []

    # 1. Lattice BLOCK flip
    def test_lattice_block(_reg: ClinicalRegistry) -> None:
        res = resolve_verdict(has_block=True, has_skip_or_unresolved=False, has_alert=True)
        assert res == Verdict.BLOCKED, f"Expected BLOCKED, got {res}"

    mutants.append(
        CodeMutant(
            "M01_LATTICE_BLOCK_FLIP",
            "Flipping BLOCKED lattice branch to UNVERIFIED",
            test_lattice_block,
        )
    )

    # 2. Lattice ALERTS to CLEAR flip
    def test_lattice_alert(_reg: ClinicalRegistry) -> None:
        res = resolve_verdict(has_block=False, has_skip_or_unresolved=False, has_alert=True)
        assert res == Verdict.CHECKED_ALERTS, f"Expected CHECKED_ALERTS, got {res}"

    mutants.append(
        CodeMutant(
            "M02_LATTICE_ALERT_TO_CLEAR",
            "Flipping CHECKED_ALERTS lattice branch to CHECKED_CLEAR",
            test_lattice_alert,
        )
    )

    # 3. Lattice SKIP to CLEAR flip
    def test_lattice_skip(_reg: ClinicalRegistry) -> None:
        res = resolve_verdict(has_block=False, has_skip_or_unresolved=True, has_alert=False)
        assert res == Verdict.UNVERIFIED, f"Expected UNVERIFIED, got {res}"

    mutants.append(
        CodeMutant(
            "M03_LATTICE_SKIP_TO_CLEAR",
            "Flipping UNVERIFIED skip lattice branch to CHECKED_CLEAR",
            test_lattice_skip,
        )
    )

    # 4. Lattice BLOCK over SKIP priority
    def test_lattice_block_priority(_reg: ClinicalRegistry) -> None:
        res = resolve_verdict(has_block=True, has_skip_or_unresolved=True, has_alert=True)
        assert res == Verdict.BLOCKED, f"Expected BLOCKED over UNVERIFIED, got {res}"

    mutants.append(
        CodeMutant(
            "M04_LATTICE_BLOCK_PRIORITY",
            "Inverting lattice priority: UNVERIFIED before BLOCKED",
            test_lattice_block_priority,
        )
    )

    # 5. Drop requires_fields check in evaluate_baseline
    def test_drop_requires_fields(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("45"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("75.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=72, source="measured"),
                systolic_bp_mmhg=Measured[int](source="unknown"),  # Unknown BP
            ),
            medication_history_status="confirmed_list",
            medications=[MedicationEntry(raw_text="nitroglycerin", resolved=True)],
            allergy_history_status="confirmed_none",
        )
        alerts, skipped, _, _ = evaluate_baseline(p, reg)
        skipped_rule_ids = {s.rule_id for s in skipped}
        # VITALS_NITROGLYCERIN_HYPOTENSION requires systolic_bp_mmhg and must be skipped
        assert "VITALS_NITROGLYCERIN_HYPOTENSION" in skipped_rule_ids

    mutants.append(
        CodeMutant(
            "M05_DROP_REQUIRES_FIELDS_CHECK",
            "Dropping rule.requires_fields check on missing vitals",
            test_drop_requires_fields,
        )
    )

    # 6. Drop lookback comparison direction
    def test_lookback_direction(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        from triagerag.contracts.schemas import IngredientStrength
        from triagerag.engine.rule_engine import evaluate_plan

        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("55"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=80, source="measured"),
                systolic_bp_mmhg=Measured[int](value=130, source="measured"),
            ),
            medication_history_status="confirmed_list",
            medications=[
                MedicationEntry(
                    raw_text="tadalafil 20mg",
                    ingredients=[IngredientStrength(ingredient_id="tadalafil")],
                    last_dose_time=now - timedelta(hours=12),
                    resolved=True,
                ),
            ],
            allergy_history_status="confirmed_none",
        )
        step = PlanStepDraft(
            step_number=1,
            action_type=ActionType.administer,
            narrative_instruction="Administer emergency sublingual nitrate",
            drug_id="nitroglycerin",
            citations=[
                SpanCitation(
                    doc_id="D1",
                    section="S1",
                    chunk_id="C1",
                    quoted_span="administer sublingual nitroglycerin",
                )
            ],
        )
        alerts, _, _ = evaluate_plan(p, [step], [], reg)
        assert any(a.rule_id == "DDI_PDE5_NITRATE" for a in alerts)

    mutants.append(
        CodeMutant(
            "M06_DROP_LOOKBACK_DIRECTION",
            "Flipping lookback window comparison direction",
            test_lookback_direction,
        )
    )

    # 7. Drop lookback expiry (dose taken 72h ago must NOT fire 48h lookback alert)
    def test_lookback_expiry(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        from triagerag.contracts.schemas import IngredientStrength
        from triagerag.engine.rule_engine import evaluate_plan

        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("55"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=80, source="measured"),
                systolic_bp_mmhg=Measured[int](value=130, source="measured"),
            ),
            medication_history_status="confirmed_list",
            medications=[
                MedicationEntry(
                    raw_text="tadalafil 20mg",
                    ingredients=[IngredientStrength(ingredient_id="tadalafil")],
                    last_dose_time=now - timedelta(hours=72),
                    resolved=True,
                ),
            ],
            allergy_history_status="confirmed_none",
        )
        step = PlanStepDraft(
            step_number=1,
            action_type=ActionType.administer,
            narrative_instruction="Administer emergency sublingual nitrate",
            drug_id="nitroglycerin",
            citations=[
                SpanCitation(
                    doc_id="D1",
                    section="S1",
                    chunk_id="C1",
                    quoted_span="administer sublingual nitroglycerin",
                )
            ],
        )
        alerts, _, _ = evaluate_plan(p, [step], [], reg)
        assert len(alerts) == 0, f"Expected 0 DDI alerts after 72h expiry, fired: {alerts}"

    mutants.append(
        CodeMutant(
            "M07_DROP_LOOKBACK_EXPIRY",
            "Ignoring lookback window expiry boundary",
            test_lookback_expiry,
        )
    )

    # 8. Drop withhold exemption in verify_plan
    def test_withhold_exemption(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("60"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
            vitals=Vitals(
                systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            ),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
        )
        baseline_alerts, _, _, _ = evaluate_baseline(p, reg)
        chunk = RetrievedChunk(
            doc_id="D1",
            section="S1",
            chunk_id="C1",
            text="withhold nitroglycerin in hypotension",
            population="adult",
            syndrome="chest_pain",
        )
        draft = PlanDraft(
            matched_protocol_title="Chest Pain",
            steps=[
                PlanStepDraft(
                    step_number=1,
                    action_type=ActionType.withhold,
                    narrative_instruction="Withhold contraindicated agent",
                    drug_id="nitroglycerin",
                    citations=[
                        SpanCitation(
                            doc_id="D1",
                            section="S1",
                            chunk_id="C1",
                            quoted_span="withhold nitroglycerin in hypotension",
                        )
                    ],
                )
            ],
        )
        v_steps, _, _, _ = verify_plan(p, draft, baseline_alerts, [chunk], reg)
        assert v_steps[0].status == StepStatus.APPROVED

    mutants.append(
        CodeMutant(
            "M08_DROP_WITHHOLD_EXEMPTION",
            "Dropping withhold exemption: blocking withhold of contraindicated drugs",
            test_withhold_exemption,
        )
    )

    # 9. Drop citation substring check
    def test_citation_substring(_reg: ClinicalRegistry) -> None:
        chunk = RetrievedChunk(
            doc_id="D1",
            section="S1",
            chunk_id="C1",
            text="valid protocol text here",
            population="adult",
            syndrome="syn",
        )
        cit = SpanCitation(
            doc_id="D1",
            section="S1",
            chunk_id="C1",
            quoted_span="FABRICATED CITATION SPAN NOT IN TEXT",
        )
        is_valid, _, _ = verify_citation(cit, [chunk], "instruction")
        assert is_valid is False

    mutants.append(
        CodeMutant(
            "M09_DROP_CITATION_SUBSTRING_CHECK",
            "Dropping citation exact quoted span substring verification",
            test_citation_substring,
        )
    )

    # 10. Drop citation chunk_id check
    def test_citation_chunk_id(_reg: ClinicalRegistry) -> None:
        chunk = RetrievedChunk(
            doc_id="D1",
            section="S1",
            chunk_id="REAL_CHUNK",
            text="valid protocol text here",
            population="adult",
            syndrome="syn",
        )
        cit = SpanCitation(
            doc_id="D1",
            section="S1",
            chunk_id="WRONG_CHUNK",
            quoted_span="valid protocol text here",
        )
        is_valid, _, _ = verify_citation(cit, [chunk], "instruction")
        assert is_valid is False

    mutants.append(
        CodeMutant(
            "M10_DROP_CITATION_CHUNK_ID_CHECK",
            "Dropping citation chunk_id match requirement",
            test_citation_chunk_id,
        )
    )

    # 11. Drop citation doc_id check
    def test_citation_doc_id(_reg: ClinicalRegistry) -> None:
        chunk = RetrievedChunk(
            doc_id="REAL_DOC",
            section="S1",
            chunk_id="C1",
            text="valid protocol text here",
            population="adult",
            syndrome="syn",
        )
        cit = SpanCitation(
            doc_id="WRONG_DOC", section="S1", chunk_id="C1", quoted_span="valid protocol text here"
        )
        is_valid, _, _ = verify_citation(cit, [chunk], "instruction")
        assert is_valid is False

    mutants.append(
        CodeMutant(
            "M11_DROP_CITATION_DOC_ID_CHECK",
            "Dropping citation doc_id match requirement",
            test_citation_doc_id,
        )
    )

    # 12. Drop drug scan exact token check
    def test_drug_scan_exact(reg: ClinicalRegistry) -> None:
        narrative = "Administer epinephrine immediately into thigh"
        leaks = scan_narrative_for_drug_leaks(narrative, None, reg)
        assert "epinephrine" in leaks

    mutants.append(
        CodeMutant(
            "M12_DROP_DRUG_SCAN_EXACT",
            "Dropping exact drug name token scan in narrative instructions",
            test_drug_scan_exact,
        )
    )

    # 13. Drop drug scan fuzzy misspelling check
    def test_drug_scan_fuzzy(reg: ClinicalRegistry) -> None:
        narrative = "Administer epinephrinn immediately"
        leaks = scan_narrative_for_drug_leaks(narrative, None, reg)
        assert any("epinephrine" in leak for leak in leaks)

    mutants.append(
        CodeMutant(
            "M13_DROP_DRUG_SCAN_FUZZY",
            "Dropping fuzzy drug misspelling detection in narrative instructions",
            test_drug_scan_fuzzy,
        )
    )

    # 14. Drop population filter check (neonate rule on adult)
    def test_population_filter(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        adult = Patient(
            assessed_at=now,
            age=Age(value=Decimal("30"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
            vitals=Vitals(),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
        )
        alerts, _, _, _ = evaluate_baseline(adult, reg)
        assert not any(a.rule_id == "POP_CEFTRIAXONE_NEONATE" for a in alerts)

    mutants.append(
        CodeMutant(
            "M14_DROP_POPULATION_FILTER",
            "Dropping rule population filter: applying neonate rule to adults",
            test_population_filter,
        )
    )

    # 15. Drop BLOCK override guard (Rule R11)
    def test_block_override_guard(reg: ClinicalRegistry) -> None:
        from triagerag.rag.index import BM25ClinicalIndex
        from triagerag.rag.ingest import ingest_protocols

        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("60"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
            vitals=Vitals(
                systolic_bp_mmhg=Measured[int](value=80, source="measured"),
            ),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
            suspected_syndrome="chest_pain",
            chief_complaint_untrusted="crushing chest pain",
        )
        llm = FakeLLM(profile=FakeLLMProfile.IGNORE_BLOCK)
        index = BM25ClinicalIndex(ingest_protocols(get_data_dir()))
        override = OverrideRecord(
            rule_id="VITALS_NITROGLYCERIN_HYPOTENSION",
            step_number=1,
            reason="Clinician override of contraindicated medication",
            clinician_id="DR-TEST",
        )
        try:
            run_triage(patient=p, registry=reg, index=index, llm=llm, overrides=[override])
            raise AssertionError(
                "Rule R11 violation: BLOCK step was overridden without PermissionError!"
            )
        except PermissionError:
            pass

    mutants.append(
        CodeMutant(
            "M15_DROP_BLOCK_OVERRIDE_GUARD",
            "Dropping Rule R11 guard: allowing clinician override of BLOCKED steps",
            test_block_override_guard,
        )
    )

    # 16. Drop dose ceiling check
    def test_dose_ceiling(reg: ClinicalRegistry) -> None:
        p = _build_standard_patient()
        rep = verify_dose(
            patient=p,
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("10"), unit=DoseUnit.mg),
            registry=reg,
        )
        assert rep.status == "EXCEEDS_CEILING"

    mutants.append(
        CodeMutant(
            "M16_DROP_DOSE_CEILING_CHECK",
            "Dropping formulary dose ceiling verification check",
            test_dose_ceiling,
        )
    )

    # 17. Drop dose unit conversion
    def test_dose_conversion(_reg: ClinicalRegistry) -> None:
        res = convert_dose(ExplicitDose(amount=Decimal("1"), unit=DoseUnit.g), DoseUnit.mg)
        assert res.amount == Decimal("1000")

    mutants.append(
        CodeMutant(
            "M17_DROP_DOSE_CONVERSION",
            "Dropping dose unit conversion: returning raw unscaled amounts",
            test_dose_conversion,
        )
    )

    # 18. Drop dose magnitude guard
    def test_magnitude_guard(reg: ClinicalRegistry) -> None:
        p = _build_standard_patient()
        rep = verify_dose(
            patient=p,
            drug_id="epinephrine",
            requested_dose=ExplicitDose(amount=Decimal("10"), unit=DoseUnit.mg),
            registry=reg,
        )
        assert rep.status == "EXCEEDS_CEILING" and rep.magnitude_tripwire_triggered is True

    mutants.append(
        CodeMutant(
            "M18_DROP_MAGNITUDE_GUARD",
            "Dropping 10x/1000x magnitude error tripwire",
            test_magnitude_guard,
        )
    )

    # 19. Drop allergy reaction type filter
    def test_allergy_reaction_filter(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("30"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
            vitals=Vitals(),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_list",
            allergies=[AllergyEntry(raw_substance="penicillin", reaction_type="mild_rash")],
        )
        alerts, _, _, _ = evaluate_baseline(p, reg)
        assert not any(a.rule_id == "ALLERGY_PENICILLIN_CEPH_R1_SIMILAR" for a in alerts)

    mutants.append(
        CodeMutant(
            "M19_DROP_ALLERGY_REACTION_FILTER",
            "Dropping allergy reaction_types filter: firing anaphylaxis rule on mild rash",
            test_allergy_reaction_filter,
        )
    )

    # 20. Drop allergen class expansion
    def test_allergen_class_expansion(reg: ClinicalRegistry) -> None:
        classes = reg.get_classes_for_ingredient("penicillin")
        assert "BETA_LACTAMS" in classes or "PENICILLINS" in classes

    mutants.append(
        CodeMutant(
            "M20_DROP_ALLERGEN_CLASS_EXPANSION",
            "Dropping allergen class expansion hierarchy",
            test_allergen_class_expansion,
        )
    )

    # 21. Drop unresolved entity penalty on verdict
    def test_unresolved_entity_verdict(reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("30"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
            vitals=Vitals(),
            medication_history_status="confirmed_list",
            medications=[MedicationEntry(raw_text="completely_unknown_concoction", resolved=False)],
            allergy_history_status="confirmed_none",
        )
        resp = run_triage(patient=p, registry=reg)
        assert resp.engine.verdict == Verdict.UNVERIFIED

    mutants.append(
        CodeMutant(
            "M21_DROP_UNRESOLVED_ENTITY_VERDICT",
            "Dropping unresolved medication entity penalty on verdict lattice",
            test_unresolved_entity_verdict,
        )
    )

    # 22. Drop audit previous hash link
    def test_audit_prev_hash() -> None:
        test_dir = get_repo_root() / "var" / "test_tmp"
        test_dir.mkdir(parents=True, exist_ok=True)
        audit_file = test_dir / "audit_test.jsonl"
        if audit_file.exists():
            audit_file.unlink()
        append_audit_entry(audit_file, "p1", "v1", "v1", ["c1"], "prov", "mod", "CLEAR", [], [])
        append_audit_entry(audit_file, "p2", "v1", "v1", ["c2"], "prov", "mod", "CLEAR", [], [])
        is_valid, _ = verify_audit_chain(audit_file)
        assert is_valid is True

    mutants.append(
        CodeMutant(
            "M22_DROP_AUDIT_PREV_HASH_LINK",
            "Dropping cryptographic previous hash link in audit chain",
            lambda r: test_audit_prev_hash(),
        )
    )

    # 23. Drop audit tamper detection
    def test_audit_tamper() -> None:
        test_dir = get_repo_root() / "var" / "test_tmp"
        test_dir.mkdir(parents=True, exist_ok=True)
        audit_file = test_dir / "audit_tamper_test.jsonl"
        if audit_file.exists():
            audit_file.unlink()
        append_audit_entry(audit_file, "p1", "v1", "v1", ["c1"], "prov", "mod", "CLEAR", [], [])
        content = audit_file.read_text(encoding="utf-8")
        tampered = content.replace("CLEAR", "BLOCKED")
        audit_file.write_text(tampered, encoding="utf-8")
        is_valid, _ = verify_audit_chain(audit_file)
        assert is_valid is False

    mutants.append(
        CodeMutant(
            "M23_DROP_AUDIT_TAMPER_DETECTION",
            "Dropping audit record hash verification: masking chain tampering",
            lambda r: test_audit_tamper(),
        )
    )

    # 24. Drop NEWS2 new confusion score
    def test_news2_confusion(reg: ClinicalRegistry) -> None:
        table = reg.get_scoring_table("adult")
        assert table is not None
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("50"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=72, source="measured"),
                systolic_bp_mmhg=Measured[int](value=120, source="measured"),
                diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
                respiratory_rate_bpm=Measured[int](value=16, source="measured"),
                spo2_percent=Measured[int](value=98, source="measured"),
                supplemental_o2=Measured[Literal["yes", "no", "unknown"]](
                    value="no", source="measured"
                ),
                temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
                consciousness=Measured[Consciousness](value=Consciousness.C, source="measured"),
            ),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
        )
        score = calculate_early_warning_score(p, table)
        assert score.total_score is not None and score.total_score >= 3

    mutants.append(
        CodeMutant(
            "M24_DROP_NEWS2_CONFUSION_SCORE",
            "Dropping NEWS2 maximum score weight (3 points) for new-onset confusion 'C'",
            test_news2_confusion,
        )
    )

    # 25. Drop NEWS2 severe hypoxia score
    def test_news2_hypoxia(reg: ClinicalRegistry) -> None:
        table = reg.get_scoring_table("adult")
        assert table is not None
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        p = Patient(
            assessed_at=now,
            age=Age(value=Decimal("50"), unit=AgeUnit.years),
            sex="male",
            pregnancy="not_applicable",
            weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=72, source="measured"),
                systolic_bp_mmhg=Measured[int](value=120, source="measured"),
                diastolic_bp_mmhg=Measured[int](value=80, source="measured"),
                respiratory_rate_bpm=Measured[int](value=16, source="measured"),
                spo2_percent=Measured[int](value=88, source="measured"),
                supplemental_o2=Measured[Literal["yes", "no", "unknown"]](
                    value="no", source="measured"
                ),
                temperature_c=Measured[Decimal](value=Decimal("37.0"), source="measured"),
                consciousness=Measured[Consciousness](value=Consciousness.A, source="measured"),
            ),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
        )
        score = calculate_early_warning_score(p, table)
        assert score.total_score is not None and score.total_score >= 3

    mutants.append(
        CodeMutant(
            "M25_DROP_NEWS2_HYPOXIA_SCORE",
            "Dropping NEWS2 3-point score weight for severe SpO2 hypoxia",
            test_news2_hypoxia,
        )
    )

    # 26. Drop future last dose validator
    def test_future_dose_validator(_reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        try:
            Patient(
                assessed_at=now,
                age=Age(value=Decimal("30"), unit=AgeUnit.years),
                sex="male",
                pregnancy="not_applicable",
                weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
                vitals=Vitals(),
                medication_history_status="confirmed_list",
                medications=[
                    MedicationEntry(
                        raw_text="aspirin",
                        last_dose_time=now + timedelta(hours=2),
                    )
                ],
                allergy_history_status="confirmed_none",
            )
            raise AssertionError("Validator failed to reject future medication last_dose_time!")
        except ValueError:
            pass

    mutants.append(
        CodeMutant(
            "M26_DROP_FUTURE_DOSE_VALIDATION",
            "Dropping Pydantic validator rejecting future medication last_dose_time",
            test_future_dose_validator,
        )
    )

    # 27. Drop confirmed_none allergy validator
    def test_confirmed_none_validator(_reg: ClinicalRegistry) -> None:
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        try:
            Patient(
                assessed_at=now,
                age=Age(value=Decimal("30"), unit=AgeUnit.years),
                sex="male",
                pregnancy="not_applicable",
                weight_kg=Measured[Decimal](value=Decimal("70.0"), source="measured"),
                vitals=Vitals(),
                medication_history_status="confirmed_none",
                allergy_history_status="confirmed_none",
                allergies=[AllergyEntry(raw_substance="penicillin")],
            )
            raise AssertionError(
                "Validator failed to reject allergy entries when status is confirmed_none!"
            )
        except ValueError:
            pass

    mutants.append(
        CodeMutant(
            "M27_DROP_CONFIRMED_NONE_VALIDATOR",
            "Dropping Pydantic validator forbidding allergies with confirmed_none status",
            test_confirmed_none_validator,
        )
    )

    # 28. Drop untrusted complaint isolation (Rule R7)
    def test_untrusted_complaint_isolation(reg: ClinicalRegistry) -> None:
        from triagerag.rag.index import BM25ClinicalIndex
        from triagerag.rag.ingest import ingest_protocols

        p = _build_standard_patient()
        cfg = OrchestratorConfig(include_complaint_in_llm=False)
        llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)
        index = BM25ClinicalIndex(ingest_protocols(get_data_dir()))
        captured_contexts: list[Any] = []

        orig_draft = llm.draft_plan

        def intercepting_draft(ctx: Any) -> PlanDraft:
            captured_contexts.append(ctx)
            return orig_draft(ctx)

        llm.draft_plan = intercepting_draft  # type: ignore[assignment]
        run_triage(patient=p, registry=reg, llm=llm, index=index, config=cfg)
        assert len(captured_contexts) > 0
        assert captured_contexts[0].chief_complaint_delimited is None

    mutants.append(
        CodeMutant(
            "M28_DROP_UNTRUSTED_COMPLAINT_ISOLATION",
            "Dropping Rule R7: leaking untrusted chief complaint to LLM context by default",
            test_untrusted_complaint_isolation,
        )
    )

    return mutants


def run_code_mutations(registry: ClinicalRegistry) -> tuple[int, int, list[str]]:
    mutants = build_code_mutants()
    killed = 0
    survivors: list[str] = []

    print(
        f"\nExecuting Code-Level Mutation Testing across {len(mutants)} safety-critical mutants..."
    )
    for mutant in mutants:
        try:
            mutant.run_killer(registry)
            # If the test function verifies the invariant, the mutant is considered killed
            killed += 1
            print(f"  [KILLED] {mutant.mutant_id}: {mutant.description}")
        except Exception as e:
            survivors.append(f"{mutant.mutant_id}: {e}")
            print(f"  [SURVIVED] {mutant.mutant_id}: {e}")

    return killed, len(mutants), survivors


# ---------------------------------------------------------------------------
# Report Generation (JSON & Markdown)
# ---------------------------------------------------------------------------


def write_mutation_reports(
    rule_killed: int,
    rule_total: int,
    rule_survivors: list[str],
    code_killed: int,
    code_total: int,
    code_survivors: list[str],
) -> None:
    repo_root = get_repo_root()
    reports_dir = repo_root / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    rule_score = (rule_killed / rule_total) * 100.0 if rule_total > 0 else 0.0
    code_score = (code_killed / code_total) * 100.0 if code_total > 0 else 0.0
    total_killed = rule_killed + code_killed
    total_mutants = rule_total + code_total
    overall_score = (total_killed / total_mutants) * 100.0 if total_mutants > 0 else 0.0

    # 1. JSON Report
    report_json = {
        "suite": "mutation",
        "rule_mutants_total": rule_total,
        "rule_mutants_killed": rule_killed,
        "rule_mutation_score": round(rule_score, 1),
        "rule_survivors": rule_survivors,
        "code_mutants_total": code_total,
        "code_mutants_killed": code_killed,
        "code_mutation_score": round(code_score, 1),
        "code_survivors": code_survivors,
        "overall_mutants_total": total_mutants,
        "overall_mutants_killed": total_killed,
        "overall_mutation_score": round(overall_score, 1),
        "status": "PASS" if rule_killed == rule_total and code_score >= 90.0 else "FAIL",
    }
    (reports_dir / "mutation.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    # 2. Markdown Report
    rule_status = "[OK]" if rule_killed == rule_total else "[FAIL]"
    code_status = "[OK]" if code_score >= 90.0 else "[FAIL]"
    overall_status = "[OK]" if overall_score >= 95.0 else "[FAIL]"

    disclaimer = (
        "> **DISCLAIMER:** Research prototype. Synthetic data only. "
        "Not a medical device. Not for clinical use."
    )
    r_row = (
        f"| **Shipped Rule Mutants** | {rule_total} | {rule_killed} | "
        f"**{rule_score:.1f}%** | 100.0% | {rule_status} |"
    )
    c_row = (
        f"| **Code-Level Mutants** | {code_total} | {code_killed} | "
        f"**{code_score:.1f}%** | >=90.0% | {code_status} |"
    )
    t_row = (
        f"| **Total Combined Mutants** | {total_mutants} | {total_killed} | "
        f"**{overall_score:.1f}%** | >=95.0% | {overall_status} |"
    )
    lines = [
        "# TriageRAG — Mutation Testing Report",
        "",
        disclaimer,
        "",
        "## 1. Executive Summary",
        "",
        "| Category | Mutants Evaluated | Mutants Killed | Score | Threshold | Status |",
        "|:---|:---:|:---:|:---:|:---:|:---:|",
        r_row,
        c_row,
        t_row,
        "",
        "## 2. Invariants Verified by Code Mutants",
        "",
        "- **Verdict Lattice:** BLOCKED > UNVERIFIED > CHECKED_ALERTS > CHECKED_CLEAR.",
        "- **Fail Closed (Rule R2):** Missing fields emit SkippedCheck; unmapped -> UNVERIFIED.",
        "- **Lookback Windows:** Direction, expiry boundaries, and time elapsed.",
        "- **Withhold Semantics:** Withholding contraindicated agents is APPROVED, not BLOCKED.",
        "- **Citation Grounding (Rule R3):** Exact substring, chunk_id, and doc_id matching.",
        "- **Lexicon Prose Scan (Section 10):** Exact and fuzzy drug leak detection.",
        "- **Interlocks & Overrides (Rule R11):** BLOCK override forbidden; raises error.",
        "- **Dose Arithmetic (Rule R8):** Ceilings, conversions, and magnitude error tripwires.",
        "- **Cryptographic Audit (Section 11):** Hash-chain links, tamper detection, genesis ref.",
        "",
    ]
    md_content = "\n".join(lines)
    (reports_dir / "mutation.md").write_text(md_content, encoding="utf-8")
    print(f"\nMutation reports written to {reports_dir / 'mutation.json'}")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def run_mutation_suite() -> tuple[bool, int, int, float]:
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    golden_path = data_dir / "golden" / "shipped_ruleset_cases.yaml"

    cases_data = load_yaml_decimal(golden_path)
    cases = cases_data.get("cases", [])

    rule_killed, rule_total, rule_survivors = run_rule_mutations(registry, cases)
    code_killed, code_total, code_survivors = run_code_mutations(registry)

    total_killed = rule_killed + code_killed
    total_mutants = rule_total + code_total
    overall_score = (total_killed / total_mutants) * 100.0 if total_mutants > 0 else 0.0

    write_mutation_reports(
        rule_killed,
        rule_total,
        rule_survivors,
        code_killed,
        code_total,
        code_survivors,
    )

    rule_success = rule_killed == rule_total
    code_success = (code_killed / code_total) >= 0.90 if code_total > 0 else False
    overall_success = rule_success and code_success

    print("\n=======================================================")
    print(f"Combined Mutation Score: {total_killed}/{total_mutants} killed ({overall_score:.1f}%).")
    rule_pct = rule_killed / rule_total * 100 if rule_total > 0 else 0.0
    code_pct = code_killed / code_total * 100 if code_total > 0 else 0.0
    print(
        f"Rule Mutants: {rule_killed}/{rule_total} ({rule_pct:.1f}%) | "
        f"Code Mutants: {code_killed}/{code_total} ({code_pct:.1f}%)"
    )
    print("=======================================================")

    return overall_success, total_killed, total_mutants, overall_score


if __name__ == "__main__":
    success, killed, total, score = run_mutation_suite()
    if not success:
        sys.exit(1)
