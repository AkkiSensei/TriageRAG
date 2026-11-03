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
    write_head_anchor,
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


def test_audit_chain_unanchored_tail_truncation_vulnerability(tmp_path: Path) -> None:
    """Without an external head anchor, tail truncation leaves the remaining prefix valid."""
    audit_file = tmp_path / "truncation_audit.jsonl"

    append_audit_entry(
        audit_path=audit_file,
        patient_hash="p1",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["c1"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="CHECKED_CLEAR",
        alert_ids=[],
        skipped_rule_ids=[],
    )
    append_audit_entry(
        audit_path=audit_file,
        patient_hash="p2",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["c2"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="BLOCKED",
        alert_ids=["DDI_ALERT"],
        skipped_rule_ids=[],
    )

    # Initial chain is valid
    is_valid, _ = verify_audit_chain(audit_file)
    assert is_valid is True

    # Truncate second entry (tail truncation)
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    audit_file.write_text(lines[0] + "\n", encoding="utf-8")

    # Unanchored verification passes because remaining prefix is structurally valid from genesis
    is_valid_unanchored, _ = verify_audit_chain(audit_file)
    assert is_valid_unanchored is True


def test_audit_chain_head_anchor_detects_truncation(tmp_path: Path) -> None:
    """Head anchor detects truncation of the audit log tail (T0.10 / AUB-OPS-03)."""
    audit_file = tmp_path / "anchored_audit.jsonl"
    anchor_file = tmp_path / "audit.head"

    append_audit_entry(
        audit_path=audit_file,
        patient_hash="p1",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["c1"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="CHECKED_CLEAR",
        alert_ids=[],
        skipped_rule_ids=[],
    )
    append_audit_entry(
        audit_path=audit_file,
        patient_hash="p2",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["c2"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="BLOCKED",
        alert_ids=["DDI_ALERT"],
        skipped_rule_ids=[],
    )

    # Write head anchor
    head_hash = write_head_anchor(audit_file, anchor_file)
    assert len(head_hash) == 64

    # Verification with anchor succeeds on complete file
    is_valid, err = verify_audit_chain(audit_file, anchor_path=anchor_file)
    assert is_valid is True
    assert err is None

    # Truncate the file to drop the second entry
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    audit_file.write_text(lines[0] + "\n", encoding="utf-8")

    # Verification with anchor MUST fail with truncation detection
    is_valid_truncated, err_truncated = verify_audit_chain(audit_file, anchor_path=anchor_file)
    assert is_valid_truncated is False
    assert err_truncated is not None
    assert "Truncation detected" in err_truncated

    # Verification with expected_head_hash directly also fails
    is_valid_direct, err_direct = verify_audit_chain(audit_file, expected_head_hash=head_hash)
    assert is_valid_direct is False
    assert "Truncation detected" in (err_direct or "")


def test_audit_chain_hmac_key_verification(tmp_path: Path) -> None:
    """Audit chain can optionally use HMAC-SHA256 for keyed tamper-proofing."""
    audit_file = tmp_path / "hmac_audit.jsonl"
    secret_key = "audit-signing-secret"

    append_audit_entry(
        audit_path=audit_file,
        patient_hash="p1",
        ruleset_version="0.1.0",
        formulary_version="0.1.0",
        retrieved_chunk_ids=["c1"],
        provider_name="FakeLLM",
        model_name="COMPLIANT",
        verdict="CHECKED_CLEAR",
        alert_ids=[],
        skipped_rule_ids=[],
        hmac_key=secret_key,
    )

    # Verifying with matching key succeeds
    is_valid, err = verify_audit_chain(audit_file, hmac_key=secret_key)
    assert is_valid is True
    assert err is None

    # Verifying without key fails (unkeyed SHA-256 doesn't match HMAC)
    is_valid_no_key, err_no_key = verify_audit_chain(audit_file)
    assert is_valid_no_key is False
    assert err_no_key is not None
    assert "Tamper detected" in err_no_key

    # Verifying with wrong key fails
    is_valid_wrong_key, err_wrong_key = verify_audit_chain(audit_file, hmac_key="wrong-key")
    assert is_valid_wrong_key is False
    assert "Tamper detected" in (err_wrong_key or "")
