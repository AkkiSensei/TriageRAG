"""Tests for AUB Phase 3 Task 3.6: Tier-2 Evidence Ingestion Pipeline (AUB T3.6, AUB-COR-01).

Safety Properties (AUB T3.6, AUB-COR-01, Rules R1, R2, R3, HD-9):
1. Ingests and chunks openFDA SPL drug labels into structured Tier-2 evidence chunks
   (~600 chunks across Wave 1-2 generic drug catalog).
2. Every chunk carries strict Provenance (SPL ID, effective date, CC0 public domain license tag,
   content_origin='SOURCE_EXTRACT', verified=False).
3. Handles Indian-only products (Deriphyllin, etofylline) with explicit UnretrievedEvidenceNotice
   (no_evidence_chunk=True) to prevent inventing FDA facts (Rule R3).
4. Deterministic and idempotent execution: re-running yields bit-for-bit identical chunk outputs.
5. Operates 100% offline with zero network calls in automated testing and CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools.fetch_openfda_labels import (
    WAVE_1_2_GENERICS,
    build_evidence_corpus,
)
from triagerag.config import get_data_dir
from triagerag.contracts.enums import SourceStatus
from triagerag.rag.evidence import (
    INDIAN_ONLY_GENERICS,
    EvidenceChunk,
    EvidenceManifest,
    load_evidence_manifest,
    parse_spl_section_chunks,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "openfda"


def test_parse_spl_section_chunks_from_fixture() -> None:
    """Parses real openFDA SPL fixture into structured EvidenceChunk objects with Provenance."""
    epinephrine_path = FIXTURES_DIR / "epinephrine.json"
    assert epinephrine_path.exists(), f"Test fixture not found at {epinephrine_path}"

    record = json.loads(epinephrine_path.read_text(encoding="utf-8"))
    chunks = parse_spl_section_chunks(record, generic_name="epinephrine")

    assert len(chunks) >= 8  # At least 8 standard SPL sections extracted
    for chunk in chunks:
        assert isinstance(chunk, EvidenceChunk)
        assert chunk.generic_name == "epinephrine"
        assert chunk.drug_id == "epinephrine"
        assert chunk.chunk_id.startswith("EVID_EPINEPHRINE_")
        assert len(chunk.content_hash) == 64
        assert chunk.license_tag == "public_domain"
        assert chunk.provenance.source_status == SourceStatus.RETRIEVED_UNREVIEWED
        assert chunk.provenance.content_origin.value == "SOURCE_EXTRACT"
        assert chunk.provenance.verified is False
        assert chunk.provenance.reviewer is None
        assert chunk.text.strip() != ""


def test_indian_only_formulations_flagged_with_unretrieved_notice(tmp_path: Path) -> None:
    """Indian-only formulations (Deriphyllin, etofylline) must fail closed with unretrieved notices."""
    test_generics = ("deriphyllin", "etofylline", "aspirin")
    out_file = tmp_path / "test_evidence.json"
    cache_dir = tmp_path / "cache"

    manifest = build_evidence_corpus(
        generics=test_generics,
        cache_dir=cache_dir,
        output_file=out_file,
        force_network=False,
    )

    unretrieved_names = {u.generic_name for u in manifest.unretrieved_generics}
    assert "deriphyllin" in unretrieved_names
    assert "etofylline" in unretrieved_names

    for u in manifest.unretrieved_generics:
        assert u.no_evidence_chunk is True
        assert u.market_context == "Indian-only formulation"

    # Aspirin generates normal chunks, but deriphyllin and etofylline must generate 0 chunks
    chunk_drugs = {c.drug_id for c in manifest.chunks}
    assert "aspirin" in chunk_drugs
    assert "deriphyllin" not in chunk_drugs
    assert "etofylline" not in chunk_drugs


def test_build_evidence_corpus_generates_approx_600_chunks(tmp_path: Path) -> None:
    """Generates ~600 section chunks across Wave 1-2 generics (AUB T3.6 acceptance target)."""
    out_file = tmp_path / "evidence_chunks.json"
    cache_dir = tmp_path / "cache"

    manifest = build_evidence_corpus(
        generics=WAVE_1_2_GENERICS,
        cache_dir=cache_dir,
        output_file=out_file,
        force_network=False,
    )

    # Acceptance criterion: ~ 600 section chunks
    assert manifest.total_chunks >= 600, (
        f"Expected at least 600 Tier-2 evidence chunks, got {manifest.total_chunks}"
    )
    assert manifest.generics_count >= 50
    assert len(manifest.unretrieved_generics) >= len(INDIAN_ONLY_GENERICS)


def test_evidence_corpus_idempotence(tmp_path: Path) -> None:
    """Running evidence chunk generation twice produces bit-for-bit identical outputs."""
    out_1 = tmp_path / "evidence_run_1.json"
    out_2 = tmp_path / "evidence_run_2.json"
    cache_dir = tmp_path / "cache"

    manifest_1 = build_evidence_corpus(
        generics=("aspirin", "epinephrine", "morphine", "deriphyllin"),
        cache_dir=cache_dir,
        output_file=out_1,
        force_network=False,
    )

    manifest_2 = build_evidence_corpus(
        generics=("aspirin", "epinephrine", "morphine", "deriphyllin"),
        cache_dir=cache_dir,
        output_file=out_2,
        force_network=False,
    )

    assert manifest_1.total_chunks == manifest_2.total_chunks
    assert [c.chunk_id for c in manifest_1.chunks] == [c.chunk_id for c in manifest_2.chunks]
    assert [c.content_hash for c in manifest_1.chunks] == [
        c.content_hash for c in manifest_2.chunks
    ]
    assert out_1.read_text(encoding="utf-8") == out_2.read_text(encoding="utf-8")


def test_load_evidence_manifest_from_disk() -> None:
    """Loads default data/corpus/evidence_chunks.json manifest via helper."""
    data_dir = get_data_dir()
    manifest_file = data_dir / "corpus" / "evidence_chunks.json"
    assert manifest_file.exists()

    manifest = load_evidence_manifest(data_dir)
    assert isinstance(manifest, EvidenceManifest)
    assert manifest.total_chunks >= 600
    assert "public domain" in manifest.license_notice.lower()


def test_zero_network_calls_during_offline_ingest(tmp_path: Path) -> None:
    """Automated test execution must never attempt external HTTP requests."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        manifest = build_evidence_corpus(
            generics=("aspirin", "epinephrine"),
            cache_dir=tmp_path / "cache",
            output_file=tmp_path / "out.json",
            force_network=False,
        )
        mock_urlopen.assert_not_called()
        assert manifest.total_chunks > 0
