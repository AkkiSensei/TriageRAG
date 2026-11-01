"""Unit tests for Evidence-Grounded Rule Mining Pipeline (AUB Phase 6 Task T6.6).

Safety Properties (Rule R1, R2, R3, HD-7, T6.6):
1. Verifies the 5 deterministic validators (quote in chunk, numbers in quote, ids resolve,
   schema validity, no duplicate semantic keys).
2. Asserts 100% of auto-sourced rules pass all deterministic validators.
3. Asserts strict provenance on every auto-mined rule (verified: False, reviewer: None,
   source_status: RETRIEVED_UNREVIEWED, content_origin: SOURCE_EXTRACT).
4. Asserts generation of clinician review queue (docs/REVIEW_QUEUE.md).
"""

from __future__ import annotations

from tools.mine_rules import (
    DeterministicRuleValidator,
    evaluate_mining_pipeline,
)
from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import RuleStatus, Severity, SourceStatus
from triagerag.engine.registry import load_registry
from triagerag.rag.evidence import load_evidence_manifest


def test_validator_quote_must_be_verbatim_in_chunk() -> None:
    """Property 1: Verbatim quote must be an exact substring of the evidence chunk text."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    validator = DeterministicRuleValidator(registry)
    manifest = load_evidence_manifest(data_dir)

    chunk = manifest.chunks[0]
    # Pick a real sentence from chunk text
    real_quote = chunk.text[:50]
    fake_quote = "This is a fabricated clinical claim not present in the drug label."

    assert validator.validate_quote_in_chunk(real_quote, chunk) is True
    assert validator.validate_quote_in_chunk(fake_quote, chunk) is False
    assert validator.validate_quote_in_chunk("", chunk) is False


def test_validator_numbers_must_appear_in_quote() -> None:
    """Property 2: Any numbers/thresholds present in rule schema must appear in the verbatim quote."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    validator = DeterministicRuleValidator(registry)

    quote_with_numbers = (
        "Do not administer at an infusion rate exceeding 50 mg/min to avoid collapse."
    )
    quote_without_numbers = "Do not administer rapidly to avoid cardiovascular collapse."

    rule_with_rate = {
        "id": "TEST_RATE_01",
        "type": "rate_limit",
        "drug_id": "phenytoin",
        "max_rate_mg_per_min": 50.0,
    }

    assert validator.validate_numbers_in_quote(rule_with_rate, quote_with_numbers) is True
    assert validator.validate_numbers_in_quote(rule_with_rate, quote_without_numbers) is False


def test_validator_ids_must_resolve_in_registry() -> None:
    """Property 3: Drug and class IDs must resolve in formulary, aliases, or classes."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    validator = DeterministicRuleValidator(registry)

    valid_rule = {
        "id": "TEST_RESOLVE_01",
        "type": "pair",
        "drug_a": "sildenafil",
        "drug_b": "nitroglycerin",
    }
    invalid_rule = {
        "id": "TEST_RESOLVE_02",
        "type": "pair",
        "drug_a": "invented_miracle_drug",
        "drug_b": "nitroglycerin",
    }
    invalid_class_rule = {
        "id": "TEST_RESOLVE_03",
        "type": "class_interaction",
        "class_a": "INVENTED_PHARMA_CLASS",
        "class_b": "OPIOIDS",
    }

    assert validator.validate_ids_resolve(valid_rule) is True
    assert validator.validate_ids_resolve(invalid_rule) is False
    assert validator.validate_ids_resolve(invalid_class_rule) is False


def test_validator_schema_validation() -> None:
    """Property 4: Rule must validate against Schema V2 models."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    validator = DeterministicRuleValidator(registry)

    valid_rule = {
        "id": "TEST_SCHEMA_01",
        "type": "condition_contraindication",
        "drug_id": "morphine",
        "condition": "acute_respiratory_depression",
        "prohibited_status": "yes",
        "severity": Severity.BLOCK.value,
        "status": RuleStatus.ACTIVE.value,
        "consequence": "Severe consequence",
        "action": "Avoid morphine",
        "requires_fields": ["conditions"],
        "provenance": {
            "source_doc": "OPENFDA_SPL_TEST",
            "section_ref": "Contraindications",
            "version_or_date": "2026-DRAFT",
            "source_status": SourceStatus.RETRIEVED_UNREVIEWED.value,
            "content_origin": "SOURCE_EXTRACT",
            "verified": False,
            "reviewer": None,
        },
    }
    invalid_rule = dict(valid_rule, prohibited_status="invalid_status_enum")

    assert validator.validate_schema(valid_rule) is not None
    assert validator.validate_schema(invalid_rule) is None


def test_validator_no_duplicate_semantic_key() -> None:
    """Property 5: Prohibits duplicate semantic keys among active and candidate rules."""
    data_dir = get_data_dir()
    registry = load_registry(data_dir)
    validator = DeterministicRuleValidator(registry)

    # DDI_SILDENAFIL_NITROGLYCERIN_EXPLICIT is already active in registry
    duplicate_rule = {
        "id": "TEST_DUP_01",
        "type": "pair",
        "drug_a": "sildenafil",
        "drug_b": "nitroglycerin",
    }
    assert validator.validate_no_duplicate_key(duplicate_rule) is False

    new_rule = {
        "id": "TEST_NEW_01",
        "type": "pair",
        "drug_a": "amiodarone",
        "drug_b": "digoxin",
    }
    assert validator.validate_no_duplicate_key(new_rule) is True
    # Second check of same new rule must now fail
    assert validator.validate_no_duplicate_key(new_rule) is False


def test_mining_pipeline_execution_and_artifacts() -> None:
    """End-to-end evaluation of rule mining pipeline, gold set benchmarking, and artifacts."""
    results = evaluate_mining_pipeline()

    assert results["total_proposals"] > 0
    assert results["validated_rules_count"] == results["total_proposals"]
    assert results["validator_pass_rate"] == 100.0
    assert results["total_gold_rules"] == 30
    assert results["gold_recovered_count"] > 0

    repo_root = get_repo_root()
    data_dir = get_data_dir()

    auto_mined_path = data_dir / "rules_candidates" / "auto_mined.yaml"
    assert auto_mined_path.exists()
    assert auto_mined_path.stat().st_size > 0

    review_queue_path = repo_root / "docs" / "REVIEW_QUEUE.md"
    assert review_queue_path.exists()
    content = review_queue_path.read_text(encoding="utf-8")
    assert "CLINICIAN CANDIDATE RULE REVIEW QUEUE" in content
    assert "HD-7" in content
    assert "PENDING_CLINICIAN_REVIEW" in content

    # Assert strict provenance on every mined candidate
    for r in results["mined_rules"]:
        prov = r["provenance"]
        assert prov["verified"] is False
        assert prov["reviewer"] is None
        assert prov["source_status"] == SourceStatus.RETRIEVED_UNREVIEWED.value
        assert prov["content_origin"] == "SOURCE_EXTRACT"
