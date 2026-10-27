"""Protocol library endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from triagerag.api.schemas import ProtocolChunkDto
from triagerag.config import get_data_dir
from triagerag.rag.ingest import ingest_protocols

router = APIRouter(prefix="/protocols", tags=["protocols"])


@router.get("", response_model=list[ProtocolChunkDto])
def list_protocols() -> list[ProtocolChunkDto]:
    chunks = ingest_protocols(get_data_dir())
    return [
        ProtocolChunkDto(
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            section=c.section,
            population=c.population,
            syndrome=c.syndrome,
            text=c.text,
            synthetic=True,
        )
        for c in chunks
    ]
