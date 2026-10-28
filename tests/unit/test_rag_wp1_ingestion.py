"""Unit tests for WP1: Provenance, Frontmatter Schema, Manifest, Quarantine, and Corpus CLI.

Safety Properties (RAG-04, RAG-12, Rules R3, R9):
1. Frontmatter must explicitly declare 'synthetic' (boolean); never defaults to True.
2. Real documents ('synthetic: false') require license, attribution, source_url, version,
   and retrieved_at.
3. Chunks carry version, content_hash (SHA-256), license, attribution, source_url, source_status.
4. Malformed files are quarantined in IngestReport without aborting the ingestion run.
5. API ProtocolChunkDto reflects the chunk's true 'synthetic' flag and provenance fields.
6. CLI 'triagerag corpus validate' passes on valid corpus and fails on a seeded bad file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from triagerag.cli import app
from triagerag.config import get_data_dir
from triagerag.rag.chunking import chunk_protocol_markdown
from triagerag.rag.ingest import ingest_protocols_with_report

runner = CliRunner()

REAL_PROTOCOL_VALID_MD = """---
doc_id: "REAL_NICE_SEPSIS"
title: "Sepsis Recognition and Management"
section: "Acute Hospital Assessment"
population: "adult"
syndrome: "sepsis"
chunk_id: "REAL_SEPSIS_01"
synthetic: false
license: "Open Government Licence v3.0"
attribution: "National Institute for Health and Care Excellence"
source_url: "https://www.nice.org.uk/guidance/ng51"
version: "2024.1"
retrieved_at: "2026-10-01"
status: "RETRIEVED_UNREVIEWED"
---
# Sepsis Recognition

1. IF adult patient presents with suspected infection and physiological red flags:
   THEN perform immediate venous lactate and blood culture sampling.
---
2. IF septic shock persists despite initial fluid resuscitation:
   THEN escalate to critical care specialist immediately.
"""

REAL_PROTOCOL_MISSING_LICENSE_MD = """---
doc_id: "REAL_BAD_DOC"
section: "Section A"
population: "adult"
syndrome: "sepsis"
chunk_id: "REAL_BAD_01"
synthetic: false
version: "1.0"
---
1. IF condition a:
   THEN action b.
"""


def test_real_doc_not_labeled_synthetic() -> None:
    """RAG-04: Real protocol chunks must have synthetic=False and full provenance metadata."""
    chunks = chunk_protocol_markdown(REAL_PROTOCOL_VALID_MD)
    assert len(chunks) == 3  # 1 parent + 2 child nodes (horizontal rule '---' in body preserved)
    for chunk in chunks:
        assert chunk.synthetic is False
        assert chunk.license == "Open Government Licence v3.0"
        assert chunk.attribution == "National Institute for Health and Care Excellence"
        assert chunk.source_url == "https://www.nice.org.uk/guidance/ng51"
        assert chunk.version == "2024.1"
        assert len(chunk.content_hash) == 64


def test_license_required_for_real() -> None:
    """RAG-04: Real document ('synthetic: false') missing license/attribution/url is rejected."""
    with pytest.raises(ValueError, match="license"):
        chunk_protocol_markdown(REAL_PROTOCOL_MISSING_LICENSE_MD)


def test_bad_file_quarantined_not_fatal(tmp_path: Path) -> None:
    """RAG-04: Malformed protocol file is quarantined into IngestReport without aborting run."""
    synth_dir = tmp_path / "protocols_synthetic"
    synth_dir.mkdir(parents=True)
    real_dir = tmp_path / "protocols_real"
    real_dir.mkdir(parents=True)

    # 1 valid real doc (containing '---' horizontal rule in body)
    (real_dir / "valid_real.md").write_text(REAL_PROTOCOL_VALID_MD, encoding="utf-8")
    # 1 malformed real doc (missing license)
    (real_dir / "bad_real.md").write_text(REAL_PROTOCOL_MISSING_LICENSE_MD, encoding="utf-8")
    # 1 malformed synthetic doc (missing synthetic key)
    (synth_dir / "bad_synth.md").write_text(
        "---\ndoc_id: X\nsection: S\npopulation: adult\nsyndrome: s\nchunk_id: X1\n---\n"
        "1. IF a:\n   THEN b.\n",
        encoding="utf-8",
    )

    report = ingest_protocols_with_report(tmp_path)
    assert len(report.loaded_docs) == 1
    assert "REAL_NICE_SEPSIS" in report.loaded_docs
    assert len(report.quarantined) == 2
    quarantined_names = {Path(q.path).name for q in report.quarantined}
    assert quarantined_names == {"bad_real.md", "bad_synth.md"}
    assert len(report.chunks) == 3
    assert all(c.synthetic is False for c in report.chunks)
    assert len(report.corpus_hash) == 64


def test_corpus_validate_cli_passes_on_bundled_and_fails_on_bad(tmp_path: Path) -> None:
    """WP1 Gate: 'triagerag corpus validate' succeeds on bundled data and fails on bad file."""
    res_ok = runner.invoke(app, ["corpus", "validate", "--data-dir", str(get_data_dir())])
    assert res_ok.exit_code == 0, f"Expected exit 0 on bundled corpus, got: {res_ok.output}"

    bad_dir = tmp_path / "bad_data"
    synth_dir = bad_dir / "protocols_synthetic"
    synth_dir.mkdir(parents=True)
    (synth_dir / "broken.md").write_text(REAL_PROTOCOL_MISSING_LICENSE_MD, encoding="utf-8")

    res_bad = runner.invoke(app, ["corpus", "validate", "--data-dir", str(bad_dir)])
    assert res_bad.exit_code != 0
    assert "QUARANTINED" in res_bad.output.upper() or "FAILED" in res_bad.output.upper()
