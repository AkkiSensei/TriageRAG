"""Unit tests for WP8: Unified RetrievalService, full audit provenance, and ADR 0006.

Safety Properties (RAG-12, RAG-13, RAG-14, RAG-15, Rule R12):
1. All entrypoints (API, CLI, UI, eval) obtain retrieval via RetrievalService.create_default();
   no module-global _INDEX exists in api/routes/triage.py.
2. Concurrent RetrievalService.create_default() and reload() calls across 16 threads are race-free.
3. Orchestrator uses a dedicated _UNAVAILABLE_SCORE_PROVENANCE constant (works even with 0 rules).
4. AuditRecord records distinct formulary_version, retrieval_query, retrieval_filters,
   retrieval_stage_scores, corpus_hash, index_version, config_hash, and abstain_code.
5. ADR 0006 exists in docs/adr/.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from triagerag.audit.chain import verify_audit_chain
from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import AgeUnit, ScoreBand
from triagerag.contracts.schemas import Age, Measured, OrchestratorConfig, Patient, Vitals
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.service import RetrievalService


def test_single_retrieval_service_factory_across_surfaces() -> None:
    """RAG-12, RAG-13, RAG-15: API, CLI, UI use RetrievalService; UI syndrome dropdown is fixed."""
    repo_root = get_repo_root()
    triage_route = (repo_root / "src" / "triagerag" / "api" / "routes" / "triage.py").read_text(
        encoding="utf-8"
    )
    protocols_route = (
        repo_root / "src" / "triagerag" / "api" / "routes" / "protocols.py"
    ).read_text(encoding="utf-8")
    cli_code = (repo_root / "src" / "triagerag" / "cli.py").read_text(encoding="utf-8")
    ui_code = (repo_root / "src" / "triagerag" / "ui" / "app.py").read_text(encoding="utf-8")

    assert "_INDEX = None" not in triage_route
    assert "RetrievalService" in triage_route
    assert "RetrievalService" in protocols_route
    assert "RetrievalService" in cli_code
    assert "RetrievalService" in ui_code
    assert '"paediatric_sepsis_screen"' not in ui_code
    assert '"paediatric_sepsis"' in ui_code


def test_concurrent_retrieval_service_access_and_reload() -> None:
    """RAG-13: 16 concurrent threads calling create_default and reload are race-free."""
    data_dir = get_data_dir()

    def worker(idx: int) -> str:
        if idx % 5 == 0:
            svc = RetrievalService.reload(data_dir)
        else:
            svc = RetrievalService.create_default(data_dir)
        return svc.corpus_hash

    with ThreadPoolExecutor(max_workers=16) as pool:
        hashes = list(pool.map(worker, range(32)))

    assert len(set(hashes)) == 1
    assert len(hashes[0]) == 64


def test_orchestrator_zero_rules_unscored_and_full_audit_provenance(tmp_path: Path) -> None:
    """RAG-12, RAG-14: Empty-rules registry does not crash on assert; audit logs full RAG fields."""
    data_dir = get_data_dir()
    reg = ClinicalRegistry.load_from_directory(data_dir)
    assert reg.formulary_version != reg.version

    # 1. Empty rules registry + neonate (no score table) must not fail with AssertionError
    empty_rules_reg = reg.with_rules([])
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    neonate = Patient(
        assessed_at=now,
        age=Age(value=Decimal("10"), unit=AgeUnit.days),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("3.4"), source="measured"),
        vitals=Vitals(heart_rate_bpm=Measured[int](value=140, source="measured")),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="paediatric_sepsis",
    )
    svc = RetrievalService.create_default(data_dir)
    audit_file = tmp_path / "wp8_audit.jsonl"
    cfg = OrchestratorConfig(audit_log_path=str(audit_file))

    resp_neo = run_triage(
        neonate,
        registry=empty_rules_reg,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
        index=svc.index,
        config=cfg,
    )
    assert resp_neo.engine.score is not None
    assert resp_neo.engine.score.band == ScoreBand.UNSCORED

    # 2. Adult triage logs full retrieval metadata & distinct formulary_version in audit chain
    adult = Patient(
        assessed_at=now,
        age=Age(value=Decimal("55"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            heart_rate_bpm=Measured[int](value=115, source="measured"),
            systolic_bp_mmhg=Measured[int](value=85, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
    )
    run_triage(
        adult,
        registry=reg,
        llm=FakeLLM(FakeLLMProfile.COMPLIANT),
        index=svc.index,
        config=cfg,
    )

    valid, err = verify_audit_chain(audit_file)
    assert valid is True, f"Audit chain failed verification: {err}"

    lines = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    last_entry = lines[-1]
    assert last_entry["formulary_version"] == reg.formulary_version
    assert last_entry["formulary_version"] != last_entry["ruleset_version"]
    assert last_entry["corpus_hash"] == svc.corpus_hash
    assert last_entry["index_version"] == svc.index_version
    assert len(last_entry["config_hash"]) == 64
    assert "chest_pain" in last_entry["retrieval_query"]
    assert last_entry["retrieval_filters"]["population"] == "adult"
    assert last_entry["retrieval_filters"]["syndrome"] == "chest_pain"
    assert last_entry["abstain_code"] == "NONE"
    assert len(last_entry["retrieval_stage_scores"]) > 0

    # Tampering with corpus_hash or retrieval_query invalidates the cryptographic chain
    tampered = audit_file.read_text(encoding="utf-8").replace(svc.corpus_hash, "0" * 64)
    audit_file.write_text(tampered, encoding="utf-8")
    valid_after, _ = verify_audit_chain(audit_file)
    assert valid_after is False


def test_adr_0006_exists() -> None:
    """WP8: ADR 0006 documenting RAG hardening and support verification exists."""
    adr_path = get_repo_root() / "docs" / "adr" / "0006-rag-hardening-and-support-verification.md"
    assert adr_path.exists()
    content = adr_path.read_text(encoding="utf-8")
    assert "UNKNOWN_SYNDROME" in content
    assert "verify_step_support" in content
