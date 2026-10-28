"""Protocol library endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from triagerag.api.schemas import ProtocolChunkDto
from triagerag.config import get_data_dir
from triagerag.rag.service import RetrievalService

router = APIRouter(prefix="/protocols", tags=["protocols"])


@router.get("", response_model=list[ProtocolChunkDto])
def list_protocols() -> list[ProtocolChunkDto]:
    service = RetrievalService.create_default(get_data_dir())
    chunks = service.list_chunks()
    return [
        ProtocolChunkDto(
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            parent_id=c.parent_id,
            title=c.title,
            section=c.section,
            population=c.population,
            syndrome=c.syndrome,
            text=c.text,
            synthetic=c.synthetic,
            version=c.version,
            content_hash=c.content_hash,
            license=c.license,
            attribution=c.attribution,
            source_url=c.source_url,
            source_status=c.source_status.value,
        )
        for c in chunks
    ]
