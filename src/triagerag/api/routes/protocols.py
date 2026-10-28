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
