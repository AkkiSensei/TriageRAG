"""Ingestion module for synthetic and real clinical protocols.

Safety Properties (Rules R3, R9, RAG-04, RAG-11, RAG-12):
1. Bundled protocols are strictly verified as synthetic or validated against full
   real-guideline license/attribution/source_url metadata before ingestion.
2. Malformed files or files with unparsed decision content are quarantined into
   IngestReport (with explicit reason) without aborting ingestion of valid files.
3. Detects and flags corpus-borne prompt-injection patterns on chunks at ingestion
   without silently deleting text.
4. Computes a deterministic SHA-256 corpus_hash over all ingested chunks and versions.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from triagerag.contracts.enums import SourceStatus
from triagerag.rag.chunking import ProtocolChunk, chunk_protocol_markdown

logger = logging.getLogger(__name__)

_SUSPICIOUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    ),
    ("ignore_safety", re.compile(r"ignore\s+(?:all\s+)?safety\s+rules", re.IGNORECASE)),
    ("system_override", re.compile(r"system\s+override", re.IGNORECASE)),
    (
        "disregard_rules",
        re.compile(r"disregard\s+(?:all\s+)?(?:previous|safety|clinical)", re.IGNORECASE),
    ),
    (
        "xml_tag_escape",
        re.compile(
            r"</?(?:instructions|system|prompt|untrusted_retrieved_protocol_data)>",
            re.IGNORECASE,
        ),
    ),
    ("role_hijack", re.compile(r"you\s+are\s+now\s+(?:an?\s+)?unrestricted", re.IGNORECASE)),
)


def detect_suspicious_patterns(text: str) -> tuple[str, ...]:
    """Scan chunk text for instruction-like prompt injection patterns (RAG-11)."""
    found: list[str] = []
    for name, pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            found.append(name)
    return tuple(found)


def sanitize_chunk_for_prompt(text: str) -> str:
    """Neutralize XML delimiter escapes and explicit override headers for LLM prompt framing."""
    sanitized = re.sub(
        r"</?(?:instructions|system|prompt|untrusted_retrieved_protocol_data)>",
        "[STRIPPED_TAG]",
        text,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(?:SYSTEM\s+OVERRIDE|IGNORE\s+(?:ALL\s+)?(?:PREVIOUS\s+INSTRUCTIONS|SAFETY\s+RULES))",
        "[FLAGGED_UNTRUSTED_DIRECTIVE]",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


class CorpusManifestEntry(BaseModel):
    """Manifest metadata entry for a single corpus protocol document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    title: str
    path: str
    population: Literal["adult", "paediatric", "neonate"]
    syndrome: str
    synthetic: bool
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    version: str = "1.0.0"
    retrieved_at: str | None = None
    content_hash: str
    reviewed_by: str | None = None
    status: SourceStatus = SourceStatus.PLACEHOLDER_UNRETRIEVED


class CorpusManifest(BaseModel):
    """Top-level corpus manifest and controlled syndrome vocabulary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: str = "1.0.0"
    controlled_syndromes: list[str] = Field(default_factory=list)
    syndrome_aliases: dict[str, str] = Field(default_factory=dict)
    documents: list[CorpusManifestEntry] = Field(default_factory=list)


class QuarantinedDocument(BaseModel):
    """Record of a protocol file rejected during ingestion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    reason: str


class IngestReport(BaseModel):
    """Structured report from protocol ingestion, quarantine, and provenance audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunks: list[ProtocolChunk] = Field(default_factory=list)
    loaded_docs: list[str] = Field(default_factory=list)
    quarantined: list[QuarantinedDocument] = Field(default_factory=list)
    unparsed_by_doc: dict[str, list[str]] = Field(default_factory=dict)
    flagged_chunks: dict[str, list[str]] = Field(default_factory=dict)
    corpus_hash: str = ""


def compute_corpus_hash(chunks: list[ProtocolChunk]) -> str:
    """Compute a deterministic SHA-256 hash over sorted chunk IDs, versions, and content hashes."""
    hasher = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: (c.doc_id, c.chunk_id)):
        record = (
            f"{chunk.doc_id}:{chunk.chunk_id}:{chunk.version}:"
            f"{chunk.content_hash}:{chunk.synthetic}\n"
        )
        hasher.update(record.encode("utf-8"))
    return hasher.hexdigest()


def load_corpus_manifest(data_dir: Path) -> CorpusManifest:
    """Load data/corpus/manifest.yaml if present, or derive from ingested chunks."""
    manifest_path = data_dir / "corpus" / "manifest.yaml"
    if manifest_path.exists():
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return CorpusManifest.model_validate(raw)

    # Fallback derivation when operating on a temporary test data_dir without manifest.yaml
    report = ingest_protocols_with_report(data_dir, strict_unparsed=False)
    syndromes = sorted({c.syndrome for c in report.chunks if c.syndrome})
    return CorpusManifest(
        manifest_version="1.0.0",
        controlled_syndromes=syndromes,
        syndrome_aliases={"paediatric_sepsis_screen": "paediatric_sepsis"},
        documents=[],
    )


def ingest_protocols_with_report(
    data_dir: Path,
    *,
    strict_unparsed: bool = True,
) -> IngestReport:
    """Ingest and validate all protocol markdown files from data directories.

    Scans data/protocols_synthetic/, data/protocols_real/, and data/corpus/ (excluding manifest).
    Quarantines malformed files per-file rather than aborting the entire ingestion run.
    """
    all_chunks: list[ProtocolChunk] = []
    loaded_docs: list[str] = []
    quarantined: list[QuarantinedDocument] = []
    unparsed_by_doc: dict[str, list[str]] = {}
    flagged_chunks: dict[str, list[str]] = {}

    candidate_dirs = [
        data_dir / "protocols_synthetic",
        data_dir / "protocols_real",
        data_dir / "corpus",
    ]

    seen_paths: set[Path] = set()
    md_files: list[Path] = []
    for d in candidate_dirs:
        if d.exists() and d.is_dir():
            for md_file in sorted(d.glob("*.md")):
                resolved = md_file.resolve()
                if resolved not in seen_paths:
                    seen_paths.add(resolved)
                    md_files.append(md_file)

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            doc_chunks = chunk_protocol_markdown(content, source_path=md_file)
        except Exception as exc:
            reason = str(exc)
            logger.warning("Quarantining protocol %s: %s", md_file.name, reason)
            quarantined.append(QuarantinedDocument(path=str(md_file), reason=reason))
            continue

        if not doc_chunks:
            quarantined.append(
                QuarantinedDocument(path=str(md_file), reason="No chunks produced from file")
            )
            continue

        parent = doc_chunks[0]
        if parent.unparsed_lines:
            unparsed_by_doc[parent.doc_id] = list(parent.unparsed_lines)
            if strict_unparsed:
                reason = (
                    f"Document {parent.doc_id} contains {len(parent.unparsed_lines)} "
                    f"unparsed line(s): {parent.unparsed_lines[0]}"
                )
                logger.warning("Quarantining protocol %s: %s", md_file.name, reason)
                quarantined.append(QuarantinedDocument(path=str(md_file), reason=reason))
                continue

        # Check for corpus-borne prompt injection patterns (RAG-11)
        checked_chunks: list[ProtocolChunk] = []
        for chunk in doc_chunks:
            suspicious = detect_suspicious_patterns(chunk.text)
            if suspicious:
                flagged_chunks[chunk.chunk_id] = list(suspicious)
                chunk = chunk.model_copy(update={"suspicious_patterns": suspicious})
            checked_chunks.append(chunk)

        loaded_docs.append(parent.doc_id)
        all_chunks.extend(checked_chunks)

    corpus_hash = compute_corpus_hash(all_chunks)
    return IngestReport(
        chunks=all_chunks,
        loaded_docs=loaded_docs,
        quarantined=quarantined,
        unparsed_by_doc=unparsed_by_doc,
        flagged_chunks=flagged_chunks,
        corpus_hash=corpus_hash,
    )


def ingest_protocols(data_dir: Path) -> list[ProtocolChunk]:
    """Ingest and chunk all valid protocol markdown files from data directories."""
    report = ingest_protocols_with_report(data_dir, strict_unparsed=True)
    return report.chunks
