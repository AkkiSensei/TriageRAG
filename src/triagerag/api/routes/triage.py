"""Triage decision support endpoint."""

from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import APIRouter

from triagerag.api.schemas import ExplainApiRequest, TriageApiRequest
from triagerag.config import get_data_dir, get_retrieval_backend
from triagerag.contracts.schemas import OrchestratorConfig, ProviderMetadata, TriageResponse
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


def get_retrieval_service(backend: str | None = None) -> RetrievalService:
    """Return unified thread-safe RetrievalService instance."""
    eff_backend = backend or get_retrieval_backend()
    return RetrievalService.create_default(get_data_dir(), backend=eff_backend)


@router.post("", response_model=TriageResponse)
def execute_triage(request: TriageApiRequest) -> TriageResponse:
    registry = get_cached_registry()
    eff_backend = (request.retrieval_backend or get_retrieval_backend()).strip().lower()
    retrieval_service = get_retrieval_service(eff_backend)

    llm = FakeLLM(profile=request.llm_profile)
    req_profile = (
        request.llm_profile.value
        if hasattr(request.llm_profile, "value")
        else str(request.llm_profile)
    )
    prov_meta = ProviderMetadata(
        generation_mode="deterministic_mock",
        requested_profile=req_profile,
        retrieval_backend=eff_backend,
    )

    patient = request.patient
    # If suspected_syndrome is missing, infer from clinical narrative if available
    if not patient.suspected_syndrome and patient.chief_complaint_untrusted:
        complaint_lower = patient.chief_complaint_untrusted.lower()
        if any(w in complaint_lower for w in ["chest", "angina", "retrosternal", "substernal"]):
            patient = patient.model_copy(update={"suspected_syndrome": "chest_pain"})
        elif any(
            w in complaint_lower for w in ["anaphyl", "allergic", "urticaria", "hives", "stridor"]
        ):
            patient = patient.model_copy(update={"suspected_syndrome": "anaphylaxis"})
        elif any(w in complaint_lower for w in ["asthma", "wheez", "bronchospasm", "dyspnea"]):
            patient = patient.model_copy(update={"suspected_syndrome": "severe_asthma"})
        elif any(w in complaint_lower for w in ["sepsis", "septic", "fever", "rigor"]):
            patient = patient.model_copy(update={"suspected_syndrome": "paediatric_sepsis"})
        elif any(w in complaint_lower for w in ["hypoglyc", "blood sugar", "glucose"]):
            patient = patient.model_copy(update={"suspected_syndrome": "hypoglycemia"})

    include_complaint = request.include_complaint_in_llm or bool(
        patient.chief_complaint_untrusted and patient.chief_complaint_untrusted.strip()
    )
    config = OrchestratorConfig(
        include_complaint_in_llm=include_complaint,
    )

    response = run_triage(
        patient=patient,
        registry=registry,
        llm=llm,
        index=retrieval_service.index,
        overrides=request.overrides or [],
        config=config,
        provider_info=prov_meta,
    )
    return response


@router.post("/explain")
def explain_triage_retrieval(request: ExplainApiRequest) -> dict[str, Any]:
    """Return full Retrieval Inspector diagnostic trace for a patient presentation."""
    retrieval_service = get_retrieval_service()
    return retrieval_service.explain(request.to_patient())
