"""Cryptographic append-only audit chain with file locking.

Safety Property (Section 11):
1. Tamper-evident SHA-256 hash chaining starting from a fixed genesis hash.
2. Canonical JSON serialization (sorted keys, compact separators, ISO UTC timestamps).
3. Stores one-way patient_hash (never raw patient PII or unhashed identifiers).
4. Verifiable offline via verify_audit_chain; any tamper immediately fails verification.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


@contextlib.contextmanager
def file_lock(filepath: Path) -> Iterator[None]:
    """Cross-platform advisory file lock using msvcrt on Windows and fcntl on POSIX."""
    lock_path = filepath.with_suffix(filepath.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        if sys.platform == "win32":
            import msvcrt

            # Seek to start and lock 1 byte
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def compute_canonical_hash(record_data: dict[str, Any]) -> str:
    """Compute SHA-256 hash over canonical JSON representation excluding 'hash'."""
    data_copy = {k: v for k, v in record_data.items() if k != "hash"}
    canonical_json = json.dumps(
        data_copy,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class AuditRecord(BaseModel):
    """Cryptographic audit chain record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence_number: int
    prev_hash: str
    timestamp_utc: str
    patient_hash: str
    ruleset_version: str
    formulary_version: str
    retrieved_chunk_ids: list[str]
    retrieval_query: str = ""
    retrieval_filters: dict[str, Any] = Field(default_factory=dict)
    retrieval_stage_scores: dict[str, Any] = Field(default_factory=dict)
    corpus_hash: str = ""
    index_version: str = ""
    config_hash: str = ""
    abstain_code: str = "NONE"
    provider_name: str
    model_name: str
    verdict: str
    alert_ids: list[str]
    skipped_rule_ids: list[str]
    override_records: list[dict[str, Any]] = Field(default_factory=list)
    hash: str = ""


def get_last_audit_hash(audit_path: Path) -> tuple[int, str]:
    """Return the last (sequence_number, hash) in the audit chain or (0, GENESIS_HASH)."""
    if not audit_path.exists():
        return 0, GENESIS_HASH

    last_seq = 0
    last_hash = GENESIS_HASH
    with open(audit_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                data = json.loads(stripped)
                last_seq = data.get("sequence_number", last_seq)
                last_hash = data.get("hash", last_hash)

    return last_seq, last_hash


def append_audit_entry(
    audit_path: Path,
    patient_hash: str,
    ruleset_version: str,
    formulary_version: str,
    retrieved_chunk_ids: list[str],
    provider_name: str,
    model_name: str,
    verdict: str,
    alert_ids: list[str],
    skipped_rule_ids: list[str],
    override_records: list[dict[str, Any]] | None = None,
    timestamp_iso: str | None = None,
    *,
    retrieval_query: str = "",
    retrieval_filters: dict[str, Any] | None = None,
    retrieval_stage_scores: dict[str, Any] | None = None,
    corpus_hash: str = "",
    index_version: str = "",
    config_hash: str = "",
    abstain_code: str = "NONE",
) -> str:
    """Append a cryptographically chained audit record under an exclusive file lock.

    Returns the new record's SHA-256 hash.
    """
    from datetime import UTC, datetime

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    ts = timestamp_iso or datetime.now(UTC).isoformat()

    with file_lock(audit_path):
        last_seq, prev_hash = get_last_audit_hash(audit_path)
        new_seq = last_seq + 1

        record_dict: dict[str, Any] = {
            "sequence_number": new_seq,
            "prev_hash": prev_hash,
            "timestamp_utc": ts,
            "patient_hash": patient_hash,
            "ruleset_version": ruleset_version,
            "formulary_version": formulary_version,
            "retrieved_chunk_ids": sorted(retrieved_chunk_ids),
            "retrieval_query": retrieval_query,
            "retrieval_filters": retrieval_filters or {},
            "retrieval_stage_scores": retrieval_stage_scores or {},
            "corpus_hash": corpus_hash,
            "index_version": index_version,
            "config_hash": config_hash,
            "abstain_code": abstain_code,
            "provider_name": provider_name,
            "model_name": model_name,
            "verdict": verdict,
            "alert_ids": sorted(alert_ids),
            "skipped_rule_ids": sorted(skipped_rule_ids),
            "override_records": override_records or [],
        }

        record_hash = compute_canonical_hash(record_dict)
        record_dict["hash"] = record_hash

        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_dict, sort_keys=True, separators=(",", ":")) + "\n")

    return record_hash


def verify_audit_chain(audit_path: Path) -> tuple[bool, str | None]:
    """Verify cryptographic integrity of an entire audit log file.

    Returns:
        (True, None) if completely valid.
        (False, error_details) on any tamper or hash mismatch.
    """
    if not audit_path.exists():
        return True, None

    expected_prev_hash = GENESIS_HASH
    expected_seq = 1

    with open(audit_path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except Exception as e:
                return False, f"Line {line_no}: Malformed JSON - {e}"

            seq = record.get("sequence_number")
            prev_h = record.get("prev_hash")
            rec_h = record.get("hash")

            if seq != expected_seq:
                return (
                    False,
                    f"Line {line_no}: Sequence number broken (expected {expected_seq}, got {seq})",
                )

            if prev_h != expected_prev_hash:
                return (
                    False,
                    f"Line {line_no}: Chaining broken (expected prev_hash "
                    f"{expected_prev_hash}, got {prev_h})",
                )

            computed_h = compute_canonical_hash(record)
            if computed_h != rec_h:
                return (
                    False,
                    f"Line {line_no}: Tamper detected (recorded hash "
                    f"{rec_h} != computed {computed_h})",
                )

            expected_prev_hash = rec_h
            expected_seq += 1

    return True, None
