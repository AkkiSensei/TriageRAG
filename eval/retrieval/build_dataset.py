"""Deterministic generator for the 160-case WP5 retrieval benchmark dataset.

Generates eval/retrieval/dataset.yaml with:
- 160 structured patient cases (96 dev [60%], 64 test [40%], stratified by family with seed 42).
- Natural patient vitals (systolic_bp_mmhg, heart_rate_bpm, respiratory_rate_bpm, spo2_percent,
  temperature_c, blood_glucose_mg_dl, consciousness) and chronological ages.
- Graded node-level relevance (2 = directly actionable node, 1 = supporting node in protocol).
- All 10 mandatory case families from Appendix B of POSTMORTEM.md.
"""

from __future__ import annotations

import random
from typing import Any

import yaml

from triagerag.config import get_repo_root


def _make_case(
    case_id: str,
    family: str,
    population: str,
    age_value: str,
    age_unit: str,
    suspected_syndrome: str | None,
    vitals: dict[str, Any],
    expected_syndrome: str | None,
    relevance_grades: dict[str, int],
    expect_abstain: bool,
    expected_abstain_code: str,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "family": family,
        "split": "dev",  # assigned by stratified splitter
        "age": {"value": age_value, "unit": age_unit},
        "population": population,
        "suspected_syndrome": suspected_syndrome,
        "vitals": vitals,
        "expected_syndrome": expected_syndrome,
        "relevance_grades": relevance_grades,
        "expect_abstain": expect_abstain,
        "expected_abstain_code": expected_abstain_code,
        "notes": notes,
    }


def generate_all_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    idx = 1

    def next_id(prefix: str) -> str:
        nonlocal idx
        cid = f"RET_{idx:03d}_{prefix}"
        idx += 1
        return cid

    # -------------------------------------------------------------------------
    # Family 1: Per-syndrome positives with realistic vitals (36 cases: 6 per syndrome)
    # -------------------------------------------------------------------------
    for sbp, hr in [(82, 95), (85, 52), (130, 118), (125, 124), (140, 88), (78, 55)]:
        grades = (
            {"CHEST_PAIN_01_NODE_5": 2, "CHEST_PAIN_01_NODE_1": 1, "CHEST_PAIN_01_NODE_2": 1}
            if sbp < 90
            else (
                {"CHEST_PAIN_01_NODE_4": 2, "CHEST_PAIN_01_NODE_1": 1, "CHEST_PAIN_01_NODE_2": 1}
                if hr > 100
                else {
                    "CHEST_PAIN_01_NODE_1": 2,
                    "CHEST_PAIN_01_NODE_2": 2,
                    "CHEST_PAIN_01_NODE_3": 1,
                }
            )
        )
        cases.append(
            _make_case(
                next_id("POS_CP"),
                "syndrome_positives",
                "adult",
                "58",
                "years",
                "chest_pain",
                {"systolic_bp_mmhg": sbp, "heart_rate_bpm": hr, "spo2_percent": 96},
                "chest_pain",
                grades,
                False,
                "NONE",
            )
        )

    for sbp, spo2 in [(76, 94), (84, 89), (88, 95), (110, 90), (80, 91), (115, 96)]:
        grades = (
            {"ANAPHYLAXIS_01_NODE_4": 2, "ANAPHYLAXIS_01_NODE_1": 2, "ANAPHYLAXIS_01_NODE_3": 1}
            if sbp < 90
            else {
                "ANAPHYLAXIS_01_NODE_1": 2,
                "ANAPHYLAXIS_01_NODE_2": 2,
                "ANAPHYLAXIS_01_NODE_3": 1,
            }
        )
        cases.append(
            _make_case(
                next_id("POS_ANA"),
                "syndrome_positives",
                "adult",
                "34",
                "years",
                "anaphylaxis",
                {"systolic_bp_mmhg": sbp, "spo2_percent": spo2, "heart_rate_bpm": 112},
                "anaphylaxis",
                grades,
                False,
                "NONE",
            )
        )

    for rr, spo2 in [(28, 88), (32, 86), (26, 90), (30, 89), (24, 91), (34, 85)]:
        cases.append(
            _make_case(
                next_id("POS_ASTHMA"),
                "syndrome_positives",
                "adult",
                "29",
                "years",
                "severe_asthma",
                {"respiratory_rate_bpm": rr, "spo2_percent": spo2, "heart_rate_bpm": 110},
                "severe_asthma",
                {
                    "SEVERE_ASTHMA_01_NODE_1": 2,
                    "SEVERE_ASTHMA_01_NODE_2": 1,
                    "SEVERE_ASTHMA_01_NODE_3": 1,
                },
                False,
                "NONE",
            )
        )

    for glu, consc in [
        ("42", "C"),
        ("55", "A"),
        ("38", "V"),
        ("48", "C"),
        ("62", "A"),
        ("50", "P"),
    ]:
        cases.append(
            _make_case(
                next_id("POS_HYPO"),
                "syndrome_positives",
                "adult",
                "64",
                "years",
                "hypoglycemia",
                {"blood_glucose_mg_dl": glu, "consciousness": consc, "heart_rate_bpm": 96},
                "hypoglycemia",
                {
                    "HYPOGLYCEMIA_01_NODE_1": 2,
                    "HYPOGLYCEMIA_01_NODE_3": 2,
                    "HYPOGLYCEMIA_01_NODE_2": 1,
                },
                False,
                "NONE",
            )
        )

    for consc, glu in [
        ("C", "85"),
        ("V", "52"),
        ("P", "90"),
        ("U", "45"),
        ("C", "58"),
        ("V", "95"),
    ]:
        cases.append(
            _make_case(
                next_id("POS_AMS"),
                "syndrome_positives",
                "adult",
                "71",
                "years",
                "altered_mental_status",
                {"consciousness": consc, "blood_glucose_mg_dl": glu},
                "altered_mental_status",
                {
                    "ALTERED_MENTAL_STATUS_01_NODE_1": 2,
                    "ALTERED_MENTAL_STATUS_01_NODE_2": 2,
                    "ALTERED_MENTAL_STATUS_01_NODE_3": 1,
                },
                False,
                "NONE",
            )
        )

    for temp, hr, rr in [
        ("39.2", 155, 36),
        ("38.8", 148, 34),
        ("39.5", 162, 40),
        ("38.5", 145, 32),
        ("39.0", 150, 35),
        ("39.8", 168, 42),
    ]:
        cases.append(
            _make_case(
                next_id("POS_PAED"),
                "syndrome_positives",
                "paediatric",
                "5",
                "years",
                "paediatric_sepsis",
                {"temperature_c": temp, "heart_rate_bpm": hr, "respiratory_rate_bpm": rr},
                "paediatric_sepsis",
                {
                    "PAED_SEPSIS_01_NODE_1": 2,
                    "PAED_SEPSIS_01_NODE_2": 1,
                    "PAED_SEPSIS_01_NODE_3": 1,
                },
                False,
                "NONE",
            )
        )

    # -------------------------------------------------------------------------
    # Family 2: Hard negatives — unknown syndromes with abnormal vitals (28 cases)
    # -------------------------------------------------------------------------
    unknown_syndromes = [
        "kidney_stone",
        "appendicitis",
        "migraine",
        "gi_bleed",
        "pulmonary_embolism",
        "acute_stroke",
        "cellulitis",
        "femur_fracture",
        "urinary_tract_infection",
        "lobar_pneumonia",
        "acute_pancreatitis",
        "status_epilepticus",
        "vasovagal_syncope",
        "heat_stroke",
    ]
    for syn in unknown_syndromes:
        # Adult with hypotension + tachycardia (the exact postmortem probe pattern)
        cases.append(
            _make_case(
                next_id("HN_ADULT"),
                "hard_negatives",
                "adult",
                "45",
                "years",
                syn,
                {"systolic_bp_mmhg": 80, "heart_rate_bpm": 130, "spo2_percent": 89},
                None,
                {},
                True,
                "UNKNOWN_SYNDROME",
                f"Unknown syndrome '{syn}' with hypotension/tachycardia/hypoxia must abstain",
            )
        )
        # Paediatric with fever + severe tachycardia + unknown syndrome
        cases.append(
            _make_case(
                next_id("HN_PAED"),
                "hard_negatives",
                "paediatric",
                "6",
                "years",
                syn,
                {"temperature_c": "39.4", "heart_rate_bpm": 158, "respiratory_rate_bpm": 38},
                None,
                {},
                True,
                "UNKNOWN_SYNDROME",
                f"Paediatric unknown syndrome '{syn}' with fever/tachycardia must abstain",
            )
        )

    # -------------------------------------------------------------------------
    # Family 3: Conflicting syndrome vs vitals (16 cases)
    # -------------------------------------------------------------------------
    conflicting_specs: list[tuple[str, dict[str, Any], str]] = [
        ("hypoglycemia", {"systolic_bp_mmhg": 78, "heart_rate_bpm": 128}, "HYPOGLYCEMIA_01_NODE_1"),
        (
            "hypoglycemia",
            {"respiratory_rate_bpm": 28, "spo2_percent": 88},
            "HYPOGLYCEMIA_01_NODE_1",
        ),
        (
            "anaphylaxis",
            {"blood_glucose_mg_dl": "55", "consciousness": "C"},
            "ANAPHYLAXIS_01_NODE_1",
        ),
        ("anaphylaxis", {"temperature_c": "38.9", "heart_rate_bpm": 52}, "ANAPHYLAXIS_01_NODE_1"),
        (
            "severe_asthma",
            {"systolic_bp_mmhg": 82, "heart_rate_bpm": 54},
            "SEVERE_ASTHMA_01_NODE_1",
        ),
        (
            "severe_asthma",
            {"blood_glucose_mg_dl": "58", "temperature_c": "38.6"},
            "SEVERE_ASTHMA_01_NODE_1",
        ),
        ("chest_pain", {"blood_glucose_mg_dl": "50", "spo2_percent": 88}, "CHEST_PAIN_01_NODE_1"),
        (
            "chest_pain",
            {"temperature_c": "39.0", "respiratory_rate_bpm": 26},
            "CHEST_PAIN_01_NODE_1",
        ),
        (
            "altered_mental_status",
            {"systolic_bp_mmhg": 80, "heart_rate_bpm": 125},
            "ALTERED_MENTAL_STATUS_01_NODE_1",
        ),
        (
            "altered_mental_status",
            {"respiratory_rate_bpm": 28, "spo2_percent": 89},
            "ALTERED_MENTAL_STATUS_01_NODE_1",
        ),
        ("anaphylaxis", {"systolic_bp_mmhg": 80, "heart_rate_bpm": 50}, "ANAPHYLAXIS_01_NODE_4"),
        ("chest_pain", {"systolic_bp_mmhg": 82, "consciousness": "C"}, "CHEST_PAIN_01_NODE_5"),
        (
            "severe_asthma",
            {"systolic_bp_mmhg": 84, "consciousness": "V"},
            "SEVERE_ASTHMA_01_NODE_1",
        ),
        (
            "hypoglycemia",
            {"systolic_bp_mmhg": 81, "temperature_c": "38.7"},
            "HYPOGLYCEMIA_01_NODE_1",
        ),
        (
            "altered_mental_status",
            {"temperature_c": "38.8", "heart_rate_bpm": 55},
            "ALTERED_MENTAL_STATUS_01_NODE_1",
        ),
        ("paediatric_sepsis", {"spo2_percent": 88, "consciousness": "V"}, "PAED_SEPSIS_01_NODE_1"),
    ]
    for syn, v_dict, primary_node in conflicting_specs:
        pop = "paediatric" if syn == "paediatric_sepsis" else "adult"
        age_v = "7" if pop == "paediatric" else "52"
        prefix = primary_node.rsplit("_NODE_", 1)[0]
        grades = {
            f"{prefix}_NODE_1": 2 if primary_node.endswith("_1") else 1,
            f"{prefix}_NODE_2": 1,
            f"{prefix}_NODE_3": 1,
        }
        grades[primary_node] = 2
        cases.append(
            _make_case(
                next_id("CONF"),
                "conflicting_syndrome_vitals",
                pop,
                age_v,
                "years",
                syn,
                v_dict,
                syn,
                grades,
                False,
                "NONE",
                "Hard syndrome filter prevents cross-syndrome leakage despite conflicting vitals",
            )
        )

    # -------------------------------------------------------------------------
    # Family 4: Vitals-only (suspected_syndrome=None) — margin & inference (20 cases)
    # -------------------------------------------------------------------------
    # 4a: Ambiguous single adult flags that match multiple protocols closely -> AMBIGUOUS_MARGIN
    for sbp in [75, 78, 80, 82, 85, 88]:
        cases.append(
            _make_case(
                next_id("VO_AMBIG_SBP"),
                "vitals_only",
                "adult",
                "50",
                "years",
                None,
                {"systolic_bp_mmhg": sbp},
                None,
                {},
                True,
                "AMBIGUOUS_MARGIN",
                "Adult hypotension alone matches both chest_pain and anaphylaxis within margin",
            )
        )
    # 4b: Normal vitals with no syndrome -> EMPTY_QUERY
    for hr, sbp in [(72, 120), (80, 118), (68, 124), (76, 115), (84, 122), (70, 116)]:
        cases.append(
            _make_case(
                next_id("VO_EMPTY"),
                "vitals_only",
                "adult",
                "40",
                "years",
                None,
                {"heart_rate_bpm": hr, "systolic_bp_mmhg": sbp, "spo2_percent": 98},
                None,
                {},
                True,
                "EMPTY_QUERY",
                "Normal vitals and no suspected syndrome emits empty query and abstains",
            )
        )
    # 4c: Paediatric fever + severe tachycardia with no syndrome -> infers paediatric_sepsis
    for temp, hr in [("39.2", 155), ("38.9", 148), ("39.5", 160), ("39.1", 152)]:
        cases.append(
            _make_case(
                next_id("VO_INF_PAED"),
                "vitals_only",
                "paediatric",
                "4",
                "years",
                None,
                {"temperature_c": temp, "heart_rate_bpm": hr},
                "paediatric_sepsis",
                {"PAED_SEPSIS_01_NODE_1": 2, "PAED_SEPSIS_01_NODE_2": 1},
                False,
                "SYNDROME_INFERRED",
                "Paediatric fever + severe tachycardia infers paediatric_sepsis",
            )
        )
    # 4d: Adult tachypnea + hypoxia (severe_asthma NODE_1 has both tachypnea and oxygen)
    for rr, spo2 in [(30, 88), (32, 86), (28, 89), (34, 85)]:
        cases.append(
            _make_case(
                next_id("VO_INF_ASTHMA"),
                "vitals_only",
                "adult",
                "30",
                "years",
                None,
                {"respiratory_rate_bpm": rr, "spo2_percent": spo2},
                "severe_asthma",
                {"SEVERE_ASTHMA_01_NODE_1": 2, "SEVERE_ASTHMA_01_NODE_2": 1},
                False,
                "SYNDROME_INFERRED",
                "Adult tachypnea + hypoxia infers severe_asthma with SYNDROME_INFERRED",
            )
        )

    # -------------------------------------------------------------------------
    # Family 5: Population boundaries — neonate, paediatric, adult (16 cases)
    # -------------------------------------------------------------------------
    for days in ["1", "7", "14", "21", "28"]:
        cases.append(
            _make_case(
                next_id("POP_NEO"),
                "population_boundaries",
                "neonate",
                days,
                "days",
                "paediatric_sepsis",
                {"heart_rate_bpm": 160, "temperature_c": "38.5"},
                None,
                {},
                True,
                "NO_POPULATION_COVERAGE",
                f"Neonate ({days} days <= 28d) has 0 neonate protocols and must abstain",
            )
        )
    for age_val, age_unit in [("29", "days"), ("6", "months"), ("2", "years"), ("17", "years")]:
        cases.append(
            _make_case(
                next_id("POP_PAED_OK"),
                "population_boundaries",
                "paediatric",
                age_val,
                age_unit,
                "paediatric_sepsis",
                {"temperature_c": "39.0", "heart_rate_bpm": 150},
                "paediatric_sepsis",
                {
                    "PAED_SEPSIS_01_NODE_1": 2,
                    "PAED_SEPSIS_01_NODE_2": 1,
                    "PAED_SEPSIS_01_NODE_3": 1,
                },
                False,
                "NONE",
            )
        )
    # Paediatric patient requesting adult-only syndrome -> NO_POPULATION_COVERAGE
    for adult_syn in ["chest_pain", "anaphylaxis", "severe_asthma"]:
        cases.append(
            _make_case(
                next_id("POP_PAED_MISMATCH"),
                "population_boundaries",
                "paediatric",
                "8",
                "years",
                adult_syn,
                {"heart_rate_bpm": 150},
                None,
                {},
                True,
                "NO_POPULATION_COVERAGE",
                f"Paediatric patient with adult-only syndrome '{adult_syn}' must abstain",
            )
        )
    # Adult boundary (18y, 90y) + adult requesting paediatric_sepsis -> NO_POPULATION_COVERAGE
    for age_val in ["18", "90"]:
        cases.append(
            _make_case(
                next_id("POP_ADULT_OK"),
                "population_boundaries",
                "adult",
                age_val,
                "years",
                "chest_pain",
                {"systolic_bp_mmhg": 84, "heart_rate_bpm": 115},
                "chest_pain",
                {"CHEST_PAIN_01_NODE_5": 2, "CHEST_PAIN_01_NODE_4": 2, "CHEST_PAIN_01_NODE_1": 1},
                False,
                "NONE",
            )
        )
    for age_val in ["18", "45"]:
        cases.append(
            _make_case(
                next_id("POP_ADULT_PAEDSYN"),
                "population_boundaries",
                "adult",
                age_val,
                "years",
                "paediatric_sepsis",
                {"temperature_c": "39.1", "heart_rate_bpm": 125},
                None,
                {},
                True,
                "NO_POPULATION_COVERAGE",
                "Adult patient with paediatric-only syndrome 'paediatric_sepsis' must abstain",
            )
        )

    # -------------------------------------------------------------------------
    # Family 6: Unknown / missing vitals (14 cases)
    # -------------------------------------------------------------------------
    for syn, prefix in [
        ("chest_pain", "CHEST_PAIN_01"),
        ("anaphylaxis", "ANAPHYLAXIS_01"),
        ("severe_asthma", "SEVERE_ASTHMA_01"),
        ("hypoglycemia", "HYPOGLYCEMIA_01"),
        ("altered_mental_status", "ALTERED_MENTAL_STATUS_01"),
        ("paediatric_sepsis", "PAED_SEPSIS_01"),
    ]:
        pop = "paediatric" if syn == "paediatric_sepsis" else "adult"
        age_v = "6" if pop == "paediatric" else "48"
        cases.append(
            _make_case(
                next_id("UNK_SYN_ONLY"),
                "unknown_missing_vitals",
                pop,
                age_v,
                "years",
                syn,
                {},
                syn,
                {f"{prefix}_NODE_1": 2, f"{prefix}_NODE_2": 1, f"{prefix}_NODE_3": 1},
                False,
                "NONE",
                "All vitals unknown/missing but known syndrome still retrieves protocol nodes",
            )
        )
    for i in range(8):
        cases.append(
            _make_case(
                next_id("UNK_ALL"),
                "unknown_missing_vitals",
                "adult",
                str(30 + i * 5),
                "years",
                None,
                {},
                None,
                {},
                True,
                "EMPTY_QUERY",
                "All vitals unknown and no syndrome abstains with EMPTY_QUERY",
            )
        )

    # -------------------------------------------------------------------------
    # Family 7: Acronym, alias, punctuation & case variants (12 cases)
    # -------------------------------------------------------------------------
    variant_specs: list[tuple[str, str, str, str, dict[str, Any], str]] = [
        ("ACS", "adult", "55", "chest_pain", {"systolic_bp_mmhg": 84}, "CHEST_PAIN_01"),
        (
            "acute_coronary_syndrome",
            "adult",
            "61",
            "chest_pain",
            {"heart_rate_bpm": 118},
            "CHEST_PAIN_01",
        ),
        (
            "  CHEST-PAIN!!! ",
            "adult",
            "52",
            "chest_pain",
            {"systolic_bp_mmhg": 82},
            "CHEST_PAIN_01",
        ),
        ("ANAPHYLAXIS??", "adult", "28", "anaphylaxis", {"systolic_bp_mmhg": 78}, "ANAPHYLAXIS_01"),
        (
            "asthma",
            "adult",
            "24",
            "severe_asthma",
            {"respiratory_rate_bpm": 30, "spo2_percent": 88},
            "SEVERE_ASTHMA_01",
        ),
        (
            "SEVERE-ASTHMA",
            "adult",
            "33",
            "severe_asthma",
            {"respiratory_rate_bpm": 28},
            "SEVERE_ASTHMA_01",
        ),
        (
            "encephalopathy",
            "adult",
            "68",
            "altered_mental_status",
            {"consciousness": "C"},
            "ALTERED_MENTAL_STATUS_01",
        ),
        (
            "ALTERED MENTAL STATUS",
            "adult",
            "72",
            "altered_mental_status",
            {"consciousness": "V"},
            "ALTERED_MENTAL_STATUS_01",
        ),
        (
            "paediatric_sepsis_screen",
            "paediatric",
            "5",
            "paediatric_sepsis",
            {"temperature_c": "39.2", "heart_rate_bpm": 152},
            "PAED_SEPSIS_01",
        ),
        (
            "PAEDIATRIC-SEPSIS",
            "paediatric",
            "4",
            "paediatric_sepsis",
            {"temperature_c": "38.9", "heart_rate_bpm": 148},
            "PAED_SEPSIS_01",
        ),
        (
            "Hypoglycemia...",
            "adult",
            "59",
            "hypoglycemia",
            {"blood_glucose_mg_dl": "45"},
            "HYPOGLYCEMIA_01",
        ),
        (
            "  anaphylaxis  ",
            "adult",
            "41",
            "anaphylaxis",
            {"systolic_bp_mmhg": 85},
            "ANAPHYLAXIS_01",
        ),
    ]
    for raw_syn, pop, age_v, canon_syn, v_dict, prefix in variant_specs:
        cases.append(
            _make_case(
                next_id("VAR"),
                "acronym_morphology_variants",
                pop,
                age_v,
                "years",
                raw_syn,
                v_dict,
                canon_syn,
                {f"{prefix}_NODE_1": 2, f"{prefix}_NODE_2": 1, f"{prefix}_NODE_3": 1},
                False,
                "NONE",
            )
        )

    # -------------------------------------------------------------------------
    # Family 8: Corpus-poisoned chunk resilience (6 cases)
    # -------------------------------------------------------------------------
    for syn, prefix in [
        ("chest_pain", "CHEST_PAIN_01"),
        ("anaphylaxis", "ANAPHYLAXIS_01"),
        ("severe_asthma", "SEVERE_ASTHMA_01"),
        ("hypoglycemia", "HYPOGLYCEMIA_01"),
        ("altered_mental_status", "ALTERED_MENTAL_STATUS_01"),
        ("paediatric_sepsis", "PAED_SEPSIS_01"),
    ]:
        pop = "paediatric" if syn == "paediatric_sepsis" else "adult"
        age_v = "5" if pop == "paediatric" else "50"
        cases.append(
            _make_case(
                next_id("POISON"),
                "corpus_poisoned_chunk",
                pop,
                age_v,
                "years",
                syn,
                {"heart_rate_bpm": 150 if pop == "paediatric" else 115},
                syn,
                {f"{prefix}_NODE_1": 2, f"{prefix}_NODE_2": 1, f"{prefix}_NODE_3": 1},
                False,
                "NONE",
                "Retrieval ignores cross-syndrome poisoned chunks and flags suspicious patterns",
            )
        )

    # -------------------------------------------------------------------------
    # Family 9: Near-duplicate protocol versions / tie-breaking stability (6 cases)
    # -------------------------------------------------------------------------
    for i in range(6):
        cases.append(
            _make_case(
                next_id("DUP"),
                "near_duplicate_versions",
                "adult",
                str(45 + i),
                "years",
                "chest_pain",
                {"systolic_bp_mmhg": 80 + i, "heart_rate_bpm": 52},
                "chest_pain",
                {"CHEST_PAIN_01_NODE_5": 2, "CHEST_PAIN_01_NODE_1": 1},
                False,
                "NONE",
                "Deterministic tie-breaking by (-score, chunk_id) across runs",
            )
        )

    # -------------------------------------------------------------------------
    # Family 10: High-flag density scale & latency cases (6 cases)
    # -------------------------------------------------------------------------
    for i in range(6):
        cases.append(
            _make_case(
                next_id("SCALE"),
                "scale_latency",
                "adult",
                str(55 + i),
                "years",
                "chest_pain",
                {
                    "systolic_bp_mmhg": 82,
                    "heart_rate_bpm": 128,
                    "respiratory_rate_bpm": 26,
                    "spo2_percent": 89,
                    "temperature_c": "38.6",
                    "blood_glucose_mg_dl": "58",
                    "consciousness": "C",
                },
                "chest_pain",
                {
                    "CHEST_PAIN_01_NODE_5": 2,
                    "CHEST_PAIN_01_NODE_4": 2,
                    "CHEST_PAIN_01_NODE_1": 1,
                },
                False,
                "NONE",
            )
        )

    # Stratified 60% dev / 40% test split with fixed seed 42
    rng = random.Random(42)
    by_family: dict[str, list[dict[str, Any]]] = {}
    for c in cases:
        by_family.setdefault(str(c["family"]), []).append(c)

    for _fam, fam_cases in sorted(by_family.items()):
        indices = list(range(len(fam_cases)))
        rng.shuffle(indices)
        dev_cutoff = round(len(fam_cases) * 0.6)
        dev_idx_set = set(indices[:dev_cutoff])
        for pos, case_obj in enumerate(fam_cases):
            case_obj["split"] = "dev" if pos in dev_idx_set else "test"

    return cases


def main() -> None:
    cases = generate_all_cases()
    dev_n = sum(1 for c in cases if c["split"] == "dev")
    test_n = sum(1 for c in cases if c["split"] == "test")
    payload = {
        "dataset_version": "2.0.0",
        "seed": 42,
        "total_cases": len(cases),
        "dev_cases": dev_n,
        "test_cases": test_n,
        "cases": cases,
    }
    out_path = get_repo_root() / "eval" / "retrieval" / "dataset.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    print(f"Generated {len(cases)} cases ({dev_n} dev, {test_n} test) -> {out_path}")


if __name__ == "__main__":
    main()
