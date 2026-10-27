"""Concurrency and cryptographic tamper testing for the audit chain.

Safety Properties (Section 11):
1. Parallel multiprocessing writers: file locks guarantee atomic appends with zero torn lines or
   hash-chain breaks.
2. Tamper-evidence: any modification, reordering, deletion, or truncation is detected by
   verify_audit_chain.
"""

from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path

from triagerag.audit.chain import (
    append_audit_entry,
    verify_audit_chain,
)


def _writer_worker(audit_file: Path, worker_id: int, entries_per_worker: int) -> list[str]:
    """Worker function executed in separate process to append audit entries concurrently."""
    hashes: list[str] = []
    for i in range(entries_per_worker):
        h = append_audit_entry(
            audit_path=audit_file,
            patient_hash=f"patient_hash_{worker_id}_{i}",
            ruleset_version="0.1.0",
            formulary_version="0.1.0",
            retrieved_chunk_ids=[f"chunk_{worker_id}"],
            provider_name="test_worker",
            model_name="fake_model",
            verdict="CHECKED_CLEAR",
            alert_ids=[],
            skipped_rule_ids=[],
        )
        hashes.append(h)
    return hashes


def test_parallel_multiprocess_audit_logging(tmp_path: Path) -> None:
    """Multiprocess writers concurrently append records under file lock."""
    audit_file = tmp_path / "concurrent_audit.jsonl"

    num_workers = 4
    entries_per_worker = 10
    total_expected = num_workers * entries_per_worker

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=num_workers) as pool:
        results = [
            pool.apply_async(_writer_worker, (audit_file, wid, entries_per_worker))
            for wid in range(num_workers)
        ]
        worker_hashes = [r.get(timeout=30) for r in results]
        assert len(worker_hashes) == num_workers

    # Verify total records
    lines = [
        line.strip() for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == total_expected, f"Expected {total_expected} lines, got {len(lines)}"

    # Verify entire chain is cryptographically sound
    is_valid, bad_idx = verify_audit_chain(audit_file)
    assert is_valid is True, f"Audit chain verification failed at sequence {bad_idx}"

    # Verify sequence numbers are monotonic 1..total_expected
    records = [json.loads(line) for line in lines]
    seq_nums = [r["sequence_number"] for r in records]
    assert seq_nums == list(range(1, total_expected + 1)), "Sequence numbers broken or duplicated"


def test_tamper_modify_record_payload(tmp_path: Path) -> None:
    """Modifying any field in an audit record invalidates its hash."""
    audit_file = tmp_path / "tamper_modify.jsonl"

    for i in range(5):
        append_audit_entry(
            audit_path=audit_file,
            patient_hash=f"patient_{i}",
            ruleset_version="0.1.0",
            formulary_version="0.1.0",
            retrieved_chunk_ids=["C1"],
            provider_name="test",
            model_name="fake",
            verdict="CHECKED_CLEAR",
            alert_ids=[],
            skipped_rule_ids=[],
        )

    lines = audit_file.read_text(encoding="utf-8").splitlines()
    # Tamper with record 3: change verdict to BLOCKED without recomputing hash
    tampered_rec = json.loads(lines[2])
    tampered_rec["verdict"] = "BLOCKED"
    lines[2] = json.dumps(tampered_rec)
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, bad_idx = verify_audit_chain(audit_file)
    assert is_valid is False
    assert bad_idx is not None and "Line 3" in bad_idx


def test_tamper_delete_record_breaks_hash_chain(tmp_path: Path) -> None:
    """Deleting a record from the middle breaks the previous-hash link."""
    audit_file = tmp_path / "tamper_delete.jsonl"

    for i in range(5):
        append_audit_entry(
            audit_path=audit_file,
            patient_hash=f"patient_{i}",
            ruleset_version="0.1.0",
            formulary_version="0.1.0",
            retrieved_chunk_ids=["C1"],
            provider_name="test",
            model_name="fake",
            verdict="CHECKED_CLEAR",
            alert_ids=[],
            skipped_rule_ids=[],
        )

    lines = audit_file.read_text(encoding="utf-8").splitlines()
    # Delete record 3 (index 2)
    del lines[2]
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, bad_idx = verify_audit_chain(audit_file)
    assert is_valid is False
    assert bad_idx is not None and "Line 3" in bad_idx


def test_tamper_reorder_records_detected(tmp_path: Path) -> None:
    """Swapping adjacent records in the chain breaks sequence and hash verification."""
    audit_file = tmp_path / "tamper_reorder.jsonl"

    for i in range(4):
        append_audit_entry(
            audit_path=audit_file,
            patient_hash=f"patient_{i}",
            ruleset_version="0.1.0",
            formulary_version="0.1.0",
            retrieved_chunk_ids=["C1"],
            provider_name="test",
            model_name="fake",
            verdict="CHECKED_CLEAR",
            alert_ids=[],
            skipped_rule_ids=[],
        )

    lines = audit_file.read_text(encoding="utf-8").splitlines()
    # Swap record 2 and record 3
    lines[1], lines[2] = lines[2], lines[1]
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    is_valid, bad_idx = verify_audit_chain(audit_file)
    assert is_valid is False
    assert bad_idx is not None and ("Line 2" in bad_idx or "Line 3" in bad_idx)
