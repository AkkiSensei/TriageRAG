"""API endpoint for Ask-the-Corpus extractive guideline Q&A (T7.4 / AUB-QA-01)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from triagerag.rag.ask_corpus import CorpusAskResponse, ask_the_corpus

router = APIRouter(prefix="/corpus", tags=["corpus"])


class AskCorpusRequest(BaseModel):
    question: str
    population: str = "adult"
    syndrome: str | None = None
    top_k: int = 3


@router.post("/ask", response_model=CorpusAskResponse)
def ask_corpus_endpoint(request: AskCorpusRequest) -> CorpusAskResponse:
    """Answer questions strictly via verbatim evidence extraction from approved protocols."""
    return ask_the_corpus(
        question=request.question,
        population=request.population,
        syndrome=request.syndrome,
        top_k=request.top_k,
    )
