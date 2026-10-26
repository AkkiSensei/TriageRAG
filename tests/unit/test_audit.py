"""Unit tests for cryptographic audit chain integrity and tamper detection.

Safety Property (Section 11):
Verifies that audit records are hashed canonically and chained via SHA-256.
Asserts that any file modification, line alteration, or tampering immediately
fails cryptographic verification.
"""

from __future__ import annotations

import json
from pathlib import Path

from triagerag.audit.chain import (
    GENESIS_HASH,
    append_audit_entry,
    verify_audit_chain,
)


def test_audit_chain_creation_and_verification(tmp_path: Path) -> None:
    """Appending multiple records creates a valid, verifiable audit chain."""
    audit_file = tmp_path / "audit.jsonl"

    # Append first record
    hash_1 = append_audit_entry(
        audit_path=audit_file,
        patient_hash="patient_hash_001",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["chunk_1"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="CHECKED_ALERTS",
        alert_ids=["DDI_PDE5_NITRATE"],
        skipped_rule_ids=[],
    )

    # Append second record
    hash_2 = append_audit_entry(
        audit_path=audit_file,
        patient_hash="patient_hash_002",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["chunk_2"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="CHECKED_CLEAR",
        alert_ids=[],
        skipped_rule_ids=[],
    )

    assert hash_1 != hash_2
    assert hash_1 != GENESIS_HASH

    # Verify clean chain
    is_valid, err = verify_audit_chain(audit_file)
    assert is_valid is True
    assert err is None


def test_audit_chain_tamper_detection(tmp_path: Path) -> None:
    """Modifying even one character in an audit record causes verification to fail."""
    audit_file = tmp_path / "tamper_audit.jsonl"

    append_audit_entry(
        audit_path=audit_file,
        patient_hash="patient_hash_001",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["chunk_1"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="BLOCKED",
        alert_ids=["ALLERGY_PENICILLIN_ANAPHYLAXIS"],
        skipped_rule_ids=[],
    )

    append_audit_entry(
        audit_path=audit_file,
        patient_hash="patient_hash_002",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["chunk_2"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="UNVERIFIED",
        alert_ids=[],
        skipped_rule_ids=["ALLERGY_REACTION_UNKNOWN"],
    )

    # Chain is initially valid
    is_valid, _ = verify_audit_chain(audit_file)
    assert is_valid is True

    # Tamper with the first record: alter verdict from BLOCKED to CHECKED_CLEAR
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    record_0 = json.loads(lines[0])
    record_0["verdict"] = "CHECKED_CLEAR"
    lines[0] = json.dumps(record_0, sort_keys=True, separators=(",", ":"))
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Verification MUST fail
    is_valid_after_tamper, err_msg = verify_audit_chain(audit_file)
    assert is_valid_after_tamper is False
    assert err_msg is not None
    assert "Tamper detected" in err_msg
