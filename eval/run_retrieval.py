"""Retrieval evaluation suite for TriageRAG protocol retrieval.

Safety Property (Section 8, 13):
1. Evaluates recall@5 and MRR across ≥30 structured clinical query-to-chunk pairs.
2. Verifies hard population filter and abstain correctness (abstains when target is out of domain).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal

from triagerag.config import get_data_dir
from triagerag.contracts.enums import AgeUnit, Consciousness
from triagerag.contracts.schemas import Age, Measured, Patient, Vitals
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols
from triagerag.rag.retrieve import retrieve_protocol_chunks

# 32 Curated clinical query to expected chunk ID benchmarks
BENCHMARK_PAIRS: list[dict[str, str]] = [
    # Anaphylaxis (Adult)
    {
        "syndrome": "anaphylaxis",
        "pop": "adult",
        "flags": "hypotension tachycardia",
        "target": "ANAPHYLAXIS_01",
    },
    {
        "syndrome": "anaphylaxis",
        "pop": "adult",
        "flags": "hypotension hypoxia",
        "target": "ANAPHYLAXIS_01",
    },
    {
        "syndrome": "anaphylaxis",
        "pop": "adult",
        "flags": "tachycardia",
        "target": "ANAPHYLAXIS_01",
    },
    {
        "syndrome": "anaphylaxis",
        "pop": "adult",
        "flags": "hypotension",
        "target": "ANAPHYLAXIS_01",
    },
    {
        "syndrome": "anaphylaxis",
        "pop": "adult",
        "flags": "hypoxia",
        "target": "ANAPHYLAXIS_01",
    },
    # Chest Pain (Adult)
    {
        "syndrome": "chest_pain",
        "pop": "adult",
        "flags": "hypotension",
        "target": "CHEST_PAIN_01",
    },
    {
        "syndrome": "chest_pain",
        "pop": "adult",
        "flags": "tachycardia",
        "target": "CHEST_PAIN_01",
    },
    {
        "syndrome": "chest_pain",
        "pop": "adult",
        "flags": "bradycardia",
        "target": "CHEST_PAIN_01",
    },
    {
        "syndrome": "chest_pain",
        "pop": "adult",
        "flags": "severe_hypertension",
        "target": "CHEST_PAIN_01",
    },
    {
        "syndrome": "chest_pain",
        "pop": "adult",
        "flags": "hypotension bradycardia",
        "target": "CHEST_PAIN_01",
    },
    # Severe Asthma (Adult)
    {
        "syndrome": "severe_asthma",
        "pop": "adult",
        "flags": "tachypnea",
        "target": "SEVERE_ASTHMA_01",
    },
    {
        "syndrome": "severe_asthma",
        "pop": "adult",
        "flags": "hypoxia tachypnea",
        "target": "SEVERE_ASTHMA_01",
    },
    {
        "syndrome": "severe_asthma",
        "pop": "adult",
        "flags": "hypoxia",
        "target": "SEVERE_ASTHMA_01",
    },
    {
        "syndrome": "severe_asthma",
        "pop": "adult",
        "flags": "tachypnea tachycardia",
        "target": "SEVERE_ASTHMA_01",
    },
    {
        "syndrome": "severe_asthma",
        "pop": "adult",
        "flags": "hypoxia bradycardia",
        "target": "SEVERE_ASTHMA_01",
    },
    # Hypoglycemia (Adult)
    {
        "syndrome": "hypoglycemia",
        "pop": "adult",
        "flags": "hypoglycemia",
        "target": "HYPOGLYCEMIA_01",
    },
    {
        "syndrome": "hypoglycemia",
        "pop": "adult",
        "flags": "hypoglycemia confusion",
        "target": "HYPOGLYCEMIA_01",
    },
    {
        "syndrome": "hypoglycemia",
        "pop": "adult",
        "flags": "hypoglycemia tachycardia",
        "target": "HYPOGLYCEMIA_01",
    },
    {
        "syndrome": "hypoglycemia",
        "pop": "adult",
        "flags": "hypoglycemia diaphoresis",
        "target": "HYPOGLYCEMIA_01",
    },
    {
        "syndrome": "hypoglycemia",
        "pop": "adult",
        "flags": "confusion",
        "target": "HYPOGLYCEMIA_01",
    },
    # Paediatric Sepsis Screen (Paediatric)
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "fever",
        "target": "PAED_SEPSIS_01",
    },
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "tachycardia",
        "target": "PAED_SEPSIS_01",
    },
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "fever tachycardia",
        "target": "PAED_SEPSIS_01",
    },
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "hypotension",
        "target": "PAED_SEPSIS_01",
    },
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "fever hypotension",
        "target": "PAED_SEPSIS_01",
    },
    {
        "syndrome": "paediatric_sepsis_screen",
        "pop": "paediatric",
        "flags": "tachypnea fever",
        "target": "PAED_SEPSIS_01",
    },
    # Altered Mental Status (Adult)
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "hypoxia confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "bradycardia confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "hypoglycemia confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "hypotension confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
    {
        "syndrome": "altered_mental_status",
        "pop": "adult",
        "flags": "fever confusion",
        "target": "ALTERED_MENTAL_STATUS_01",
    },
]

# Abstain benchmark cases
ABSTAIN_CASES: list[dict[str, str]] = [
    {
        "syndrome": "chest_pain",
        "pop": "neonate",
        "flags": "cyanosis bradycardia",
        "reason": "No neonate chest pain protocol",
    },
    {
        "syndrome": "severe_asthma",
        "pop": "neonate",
        "flags": "apnea retraction",
        "reason": "No neonate asthma protocol",
    },
    {
        "syndrome": "unknown_fictional_condition_xyz",
        "pop": "adult",
        "flags": "normotensive euglycemic",
        "reason": "Unknown syndrome below threshold",
    },
]


def _build_retrieval_patient(syndrome: str, pop: str, flags: str) -> Patient:
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    age_val = (
        Decimal("30")
        if pop == "adult"
        else (Decimal("5") if pop == "paediatric" else Decimal("14"))
    )
    age_unit = AgeUnit.years if pop in ("adult", "paediatric") else AgeUnit.days

    hr = 130 if "tachycardia" in flags else (50 if "bradycardia" in flags else 80)
    sbp = 80 if "hypotension" in flags else (180 if "hypertension" in flags else 120)
    rr = 28 if "tachypnea" in flags else 16
    spo2 = 88 if "hypoxia" in flags else 98
    bg = Decimal("45") if "hypoglycemia" in flags else Decimal("100")
    conc = Consciousness.C if "confusion" in flags else Consciousness.A

    vitals = Vitals(
        heart_rate_bpm=Measured[int](value=hr, source="measured"),
        systolic_bp_mmhg=Measured[int](value=sbp, source="measured"),
        respiratory_rate_bpm=Measured[int](value=rr, source="measured"),
        spo2_percent=Measured[int](value=spo2, source="measured"),
        blood_glucose_mg_dl=Measured[Decimal](value=bg, source="measured"),
        consciousness=Measured[Consciousness](value=conc, source="measured"),
    )

    return Patient(
        assessed_at=now,
        age=Age(value=age_val, unit=age_unit),
        sex="female",
        pregnancy="no",
        weight_kg=Measured[Decimal](value=Decimal("60.0"), source="measured"),
        vitals=vitals,
        medication_history_status="confirmed_none",
        medications=[],
        allergy_history_status="confirmed_nkda",
        allergies=[],
        renal_impairment="no",
        hepatic_impairment="no",
        suspected_syndrome=syndrome if syndrome != "None" else None,
        chief_complaint_untrusted="",
    )


def run_retrieval_suite() -> tuple[bool, float, float, float]:
    """Execute retrieval benchmarks and measure Recall@5, MRR, and Abstain Accuracy."""
    data_dir = get_data_dir()
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)

    print(f"Executing Retrieval Evaluation Suite ({len(BENCHMARK_PAIRS)} benchmark pairs)...")

    reciprocal_ranks: list[float] = []
    hits_at_5 = 0

    for pair in BENCHMARK_PAIRS:
        syndrome = pair["syndrome"]
        pop = pair["pop"]
        flags = pair["flags"]
        target = pair["target"]

        patient = _build_retrieval_patient(syndrome, pop, flags)

        report = retrieve_protocol_chunks(
            patient=patient,
            index=index,
            top_k=5,
        )

        retrieved_ids = [c.chunk_id for c in report.chunks]

        if target in retrieved_ids:
            hits_at_5 += 1
            rank = retrieved_ids.index(target) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    recall_at_5 = (hits_at_5 / len(BENCHMARK_PAIRS)) * 100.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

    # Evaluate Abstain Correctness
    abstain_hits = 0
    print(f"\nExecuting Abstain Correctness Cases ({len(ABSTAIN_CASES)} cases)...")
    for c in ABSTAIN_CASES:
        syndrome = c["syndrome"]
        pop = c["pop"]
        flags = c["flags"]

        patient = _build_retrieval_patient(syndrome, pop, flags)

        report = retrieve_protocol_chunks(
            patient=patient,
            index=index,
            top_k=5,
        )

        if report.abstained:
            abstain_hits += 1
            print(f"  [PASS] Abstained correctly: {c['reason']} (Reason: {report.reason})")
        else:
            print(
                f"  [FAIL] Failed to abstain: {c['reason']} (Returned {len(report.chunks)} chunks)"
            )

    abstain_accuracy = (abstain_hits / len(ABSTAIN_CASES)) * 100.0

    print("\nRetrieval Evaluation Results:")
    print(f"  Benchmark Pairs: {len(BENCHMARK_PAIRS)}")
    print(f"  Recall@5: {recall_at_5:.1f}%")
    print(f"  MRR: {mrr:.3f}")
    print(f"  Abstain Accuracy: {abstain_accuracy:.1f}%")

    success = (recall_at_5 >= 90.0) and (mrr >= 0.70) and (abstain_accuracy == 100.0)
    reports_dir = data_dir.parent / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = {
        "suite": "retrieval",
        "benchmark_pairs": len(BENCHMARK_PAIRS),
        "recall_at_5": round(recall_at_5, 1),
        "mrr": round(mrr, 3),
        "abstain_accuracy": round(abstain_accuracy, 1),
        "status": "PASS" if success else "FAIL",
    }
    import json

    (reports_dir / "retrieval.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    return success, recall_at_5, mrr, abstain_accuracy


if __name__ == "__main__":
    success, r5, mrr, abstain_acc = run_retrieval_suite()
    if not success:
        sys.exit(1)
