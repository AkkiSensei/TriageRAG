"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from triagerag.api.schemas import HealthResponse
from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.engine.registry import load_registry

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def get_health() -> HealthResponse:
    registry = load_registry(get_data_dir())
    unreviewed = sum(
        1 for r in registry.rules if r.provenance.source_status != SourceStatus.REVIEWED
    )
    return HealthResponse(
        version="0.1.0",
        ruleset_version="0.1.0",
        llm_available=True,
        retrieval_backend="bm25",
        unreviewed_rules_count=unreviewed,
        disclaimer=(
            "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
        ),
    )
