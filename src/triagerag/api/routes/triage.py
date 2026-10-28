"""Triage decision support endpoint."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import APIRouter

from triagerag.api.schemas import TriageApiRequest
from triagerag.config import get_data_dir
from triagerag.contracts.schemas import OrchestratorConfig, TriageResponse
from triagerag.engine.registry import ClinicalRegistry, load_registry
from triagerag.llm.fake import FakeLLM
from triagerag.orchestrator import run_triage
from triagerag.rag.service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["triage"])

_REGISTRY_LOCK = threading.RLock()
_REGISTRY: ClinicalRegistry | None = None


def get_cached_registry() -> ClinicalRegistry:
    """Return thread-safe cached ClinicalRegistry."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            _REGISTRY = load_registry(get_data_dir())
        return _REGISTRY


def get_retrieval_service() -> RetrievalService:
    """Return unified thread-safe RetrievalService instance."""
    return RetrievalService.create_default(get_data_dir())


@router.post("", response_model=TriageResponse)
def execute_triage(request: TriageApiRequest) -> TriageResponse:
    registry = get_cached_registry()
    retrieval_service = get_retrieval_service()

    llm: Any
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key and request.llm_profile == "COMPLIANT":
        try:
            from triagerag.llm.gemini import GeminiProvider

            llm = GeminiProvider(api_key=gemini_key)
        except Exception as e:
            logger.warning("GeminiProvider initialization failed, falling back to FakeLLM: %s", e)
            llm = FakeLLM(profile=request.llm_profile)
    else:
        llm = FakeLLM(profile=request.llm_profile)

    config = OrchestratorConfig(
        include_complaint_in_llm=request.include_complaint_in_llm,
    )

    response = run_triage(
        patient=request.patient,
        registry=registry,
        llm=llm,
        index=retrieval_service.index,
        overrides=request.overrides or [],
        config=config,
    )
    return response


@router.post("/explain")
def explain_triage_retrieval(request: TriageApiRequest) -> dict[str, Any]:
    """Return full Retrieval Inspector diagnostic trace for a patient presentation."""
    retrieval_service = get_retrieval_service()
    return retrieval_service.explain(request.patient)
