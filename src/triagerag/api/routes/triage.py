"""Triage decision support endpoint."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter

from triagerag.api.schemas import TriageApiRequest
from triagerag.config import get_data_dir
from triagerag.contracts.schemas import OrchestratorConfig, TriageResponse
from triagerag.engine.registry import load_registry
from triagerag.llm.fake import FakeLLM
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triage", tags=["triage"])

# Cached registry and BM25 index for fast response times
_REGISTRY = None
_INDEX = None


def get_cached_registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = load_registry(get_data_dir())
    return _REGISTRY


def get_cached_index():
    global _INDEX
    if _INDEX is None:
        registry = get_cached_registry()
        chunks = ingest_protocols(get_data_dir())
        _INDEX = BM25ClinicalIndex(chunks, acronyms=registry.acronyms.acronyms)
    return _INDEX


@router.post("", response_model=TriageResponse)
def execute_triage(request: TriageApiRequest) -> TriageResponse:
    registry = get_cached_registry()
    index = get_cached_index()

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
        index=index,
        overrides=request.overrides or [],
        config=config,
    )
    return response
