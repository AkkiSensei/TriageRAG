"""Unit tests for Licensing, Manifest Metadata, and HD-9 Provenance (T3.4 / HD-9).

Safety Properties (Rule R3, HD-9, AUB Task T3.4):
1. Every protocol document in the manifest carries a valid license_tag:
   ('synthetic', 'public_domain', 'cc_by_nc_sa', 'restricted').
2. ProtocolFrontmatter strictly enforces the LicenseTag enumeration.
3. Chunks preserve the document's license_tag during parsing and ingestion.
4. Non-synthetic restricted corpora, raw evidence, and local indexes are git-ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from triagerag.config import get_data_dir
from triagerag.rag.chunking import ProtocolFrontmatter, chunk_protocol_markdown
from triagerag.rag.ingest import load_corpus_manifest


def test_manifest_every_doc_carries_valid_license_tag() -> None:
    """T3.4: Every document in manifest.yaml declares a valid license_tag."""
    data_dir = get_data_dir()
    manifest = load_corpus_manifest(data_dir)
    assert len(manifest.documents) >= 60

    allowed_tags = {"synthetic", "public_domain", "cc_by_nc_sa", "restricted"}
    for doc in manifest.documents:
        assert doc.license_tag in allowed_tags, (
            f"Doc {doc.doc_id} has invalid license_tag: {doc.license_tag}"
        )


def test_frontmatter_enforces_license_tag_enum() -> None:
    """T3.4: ProtocolFrontmatter validates allowed license tags and rejects invalid tags."""
    base_dict: dict[str, Any] = {
        "doc_id": "TEST_DOC_LIC",
        "title": "Test Licensing Protocol",
        "section": "General",
        "population": "adult",
        "syndrome": "chest_pain",
        "chunk_id": "LIC_01",
        "synthetic": True,
        "version": "1.0.0",
        "license_tag": "synthetic",
    }

    # Allowed tags succeed
    for tag in ("synthetic", "public_domain", "cc_by_nc_sa", "restricted"):
        d = dict(base_dict, license_tag=tag)
        fm = ProtocolFrontmatter.model_validate(d)
        assert fm.license_tag == tag

    # Invalid tag fails validation
    invalid_dict = dict(base_dict, license_tag="invalid_custom_license")
    with pytest.raises(ValidationError):
        ProtocolFrontmatter.model_validate(invalid_dict)


def test_protocol_chunk_carries_license_tag() -> None:
    """T3.4: Chunks produced from markdown preserve the frontmatter license_tag."""
    md = """---
doc_id: EMERG_TEST_LIC_CHUNK
title: Test Chunk License Protocol
section: Test Section
population: adult
syndrome: chest_pain
chunk_id: LIC_CHUNK_01
synthetic: true
version: 1.0.0
license: synthetic
license_tag: synthetic
attribution: Test Corpus
source_url: null
retrieved_at: null
reviewed_by: null
status: PLACEHOLDER_UNRETRIEVED
---
1. IF test condition is met:
   THEN execute test intervention.
"""
    chunks = chunk_protocol_markdown(md)
    assert len(chunks) == 2
    assert chunks[0].license_tag == "synthetic"
    assert chunks[1].license_tag == "synthetic"


def test_gitignore_hd9_exclusions() -> None:
    """HD-9 Gate: Non-synthetic restricted corpora, raw evidence, and local indexes are git-ignored."""
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists(), ".gitignore file must exist at repo root"
    content = gitignore_path.read_text(encoding="utf-8")

    assert "data/protocols_restricted/*" in content
    assert "data/evidence_raw/*" in content
    assert "data/indexes_local/*" in content
