"""Chunking module for emergency clinical protocols.

Safety Property (Section 8):
Chunks by section and decision node with parent-child links.
Guarantees that an IF condition is NEVER split from its corresponding THEN action.
Maintains population and syndrome tags on every chunk for hard population filtering.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict


class ProtocolChunk(BaseModel):
    """Structured clinical protocol chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    section: str
    chunk_id: str
    parent_id: str | None = None
    text: str
    population: str
    syndrome: str
    synthetic: bool = True


def chunk_protocol_markdown(content: str, source_path: Path | None = None) -> list[ProtocolChunk]:
    """Parse protocol markdown file with YAML frontmatter into structured chunks.

    Extracts:
    1. Parent section chunk.
    2. Atomic child chunks for each numbered decision node (never splitting IF from THEN).
    """
    # 1. Parse frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not fm_match:
        raise ValueError(f"Missing YAML frontmatter in protocol file {source_path}")

    fm_raw, body_raw = fm_match.groups()
    metadata: dict[str, Any] = yaml.safe_load(fm_raw)

    doc_id = str(metadata["doc_id"])
    section = str(metadata["section"])
    population = str(metadata["population"]).strip().lower()
    syndrome = str(metadata["syndrome"]).strip().lower()
    parent_chunk_id = str(metadata["chunk_id"])
    synthetic = bool(metadata.get("synthetic", True))

    chunks: list[ProtocolChunk] = []

    # 2. Extract parent section text
    lines = body_raw.strip().splitlines()
    body_clean = "\n".join(lines).strip()

    # Add parent chunk
    chunks.append(
        ProtocolChunk(
            doc_id=doc_id,
            section=section,
            chunk_id=parent_chunk_id,
            parent_id=None,
            text=body_clean,
            population=population,
            syndrome=syndrome,
            synthetic=synthetic,
        )
    )

    # 3. Extract discrete IF/THEN decision nodes
    # Pattern matches numbered items like: "1. IF ... \n   THEN ..."
    node_pattern = re.compile(
        r"(^\d+\.\s+IF\s+.*?)(?=(?:^\d+\.\s+IF|\Z))",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )

    matches = list(node_pattern.finditer(body_raw))
    for i, m in enumerate(matches, start=1):
        node_text = m.group(1).strip()
        # Verify IF and THEN are both present in this atomic decision node
        has_if = "IF " in node_text.upper()
        has_then = "THEN " in node_text.upper()
        if not (has_if and has_then):
            continue

        child_chunk_id = f"{parent_chunk_id}_NODE_{i}"
        chunks.append(
            ProtocolChunk(
                doc_id=doc_id,
                section=section,
                chunk_id=child_chunk_id,
                parent_id=parent_chunk_id,
                text=node_text,
                population=population,
                syndrome=syndrome,
                synthetic=synthetic,
            )
        )

    return chunks
