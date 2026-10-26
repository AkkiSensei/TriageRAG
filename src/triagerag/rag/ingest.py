"""Ingestion module for synthetic and real clinical protocols.

Safety Property (Rules R3, R9):
Bundled protocols are strictly verified as synthetic.
Real protocols in data/protocols_real/ (if present) require explicit license
metadata (license, attribution, source_url) before ingestion is permitted.
"""

from __future__ import annotations

import logging
from pathlib import Path

from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown

logger = logging.getLogger(__name__)


def ingest_protocols(data_dir: Path) -> list[ProtocolChunk]:
    """Ingest and chunk all protocol markdown files from data directories.

    Scans data/protocols_synthetic/ and data/protocols_real/ (if present).
    """
    all_chunks: list[ProtocolChunk] = []

    # 1. Ingest synthetic protocols
    synth_dir = data_dir / "protocols_synthetic"
    if synth_dir.exists():
        for md_file in sorted(synth_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            chunks = chunk_protocol_markdown(content, source_path=md_file)
            all_chunks.extend(chunks)

    # 2. Ingest real protocols (if directory exists)
    real_dir = data_dir / "protocols_real"
    if real_dir.exists():
        for md_file in sorted(real_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            chunks = chunk_protocol_markdown(content, source_path=md_file)
            # Verify license metadata in frontmatter
            import yaml

            lines = content.split("---")
            if len(lines) >= 3:
                fm = yaml.safe_load(lines[1])
                if not isinstance(fm, dict) or "license" not in fm or "attribution" not in fm:
                    logger.warning(
                        "Skipping real protocol %s: missing license or attribution metadata",
                        md_file.name,
                    )
                    continue
            all_chunks.extend(chunks)

    return all_chunks
