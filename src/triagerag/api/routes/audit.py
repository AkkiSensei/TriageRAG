"""Audit chain endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from triagerag.api.schemas import AuditEntryDto, AuditVerifyResponse
from triagerag.audit.chain import file_lock, verify_audit_chain
from triagerag.config import get_audit_path

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/entries", response_model=list[AuditEntryDto])
def get_audit_entries(
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AuditEntryDto]:
    audit_path = get_audit_path()
    if not audit_path.exists():
        return []

    entries: list[AuditEntryDto] = []
    with file_lock(audit_path):
        raw_lines = audit_path.read_text(encoding="utf-8").splitlines()
        lines = [line.strip() for line in raw_lines if line.strip()]

    # Take most recent entries up to limit, reversed or forward
    for line in lines[-limit:]:
        try:
            data = json.loads(line)
            entry = AuditEntryDto(
                sequence_number=data.get("sequence_number", 0),
                timestamp_iso=data.get("timestamp_utc", ""),
                patient_hash=data.get("patient_hash", ""),
                ruleset_version=data.get("ruleset_version", ""),
                formulary_version=data.get("formulary_version", ""),
                retrieved_chunk_ids=data.get("retrieved_chunk_ids", []),
                provider_name=data.get("provider_name", ""),
                model_name=data.get("model_name", ""),
                verdict=data.get("verdict", ""),
                alert_ids=data.get("alert_ids", []),
                skipped_rule_ids=data.get("skipped_rule_ids", []),
                previous_hash=data.get("prev_hash", ""),
                record_hash=data.get("hash", ""),
            )
            entries.append(entry)
        except Exception:
            continue

    return entries


@router.post("/verify", response_model=AuditVerifyResponse)
def verify_audit() -> AuditVerifyResponse:
    audit_path = get_audit_path()
    is_valid, bad_idx = verify_audit_chain(audit_path)
    return AuditVerifyResponse(
        valid=is_valid,
        first_bad_index=bad_idx,
    )
