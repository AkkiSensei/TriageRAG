"""Chunking module for emergency clinical protocols.

Safety Properties (Section 8, RAG-04, RAG-05, RAG-06, Rules R3, R9):
1. Validates YAML frontmatter with a strict Pydantic schema (ProtocolFrontmatter).
   Never defaults 'synthetic' to True when omitted. Real protocols ('synthetic: false')
   must provide license, attribution, source_url, version, and retrieved_at.
2. Grammar-based line parser guarantees the round-trip invariant: every non-empty body
   line is either a structural header/divider, part of a valid IF/THEN child decision
   node, or explicitly recorded in parent.unparsed_lines (never silently dropped or
   bled across trailing sections).
3. Supports multi-branch decision nodes (IF / THEN / ELSE IF / ELSE and nested bullet
   sub-steps).
4. Populates contextual chunk headers in indexed_text ('{title} › {section} › {syndrome} › {id}')
   while preserving verbatim node text in 'text' for span citation verification.
5. Computes deterministic SHA-256 content_hash for every chunk.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError, model_validator

from triagerag.contracts.enums import SourceStatus

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)
_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_NUMBERED_IF_RE = re.compile(r"^(\d+)\.\s+IF\b", re.IGNORECASE)
_THEN_CLAUSE_RE = re.compile(r"(?:^\s*THEN\b|\bTHEN\s+)", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s*(.*)$")
_HR_RE = re.compile(r"^---\s*$")
_CONTINUATION_CLAUSE_RE = re.compile(
    r"^(?:THEN|ELSE\s+IF|ELSE|AND|OR)\b|^[-*]\s+|^[a-z]\)\s+",
    re.IGNORECASE,
)


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hex digest of normalized text."""
    normalized = "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_contextual_header(
    *,
    title: str,
    doc_id: str,
    section: str,
    syndrome: str,
    chunk_id: str,
    text: str,
) -> str:
    """Build contextualized text for indexing while keeping raw text separate for citations."""
    display_title = title.strip() if title and title.strip() else doc_id
    header = f"{display_title} › {section} › {syndrome} › {chunk_id}"
    return f"{header}\n{text}"


class ProtocolFrontmatter(BaseModel):
    """Strict schema for protocol markdown YAML frontmatter (RAG-04)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    title: str | None = None
    section: str
    population: Literal["adult", "paediatric", "neonate"]
    syndrome: str
    chunk_id: str
    synthetic: StrictBool
    version: str = "1.0.0"
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    reviewed_by: str | None = None
    status: SourceStatus = SourceStatus.PLACEHOLDER_UNRETRIEVED

    @model_validator(mode="after")
    def validate_provenance_requirements(self) -> ProtocolFrontmatter:
        if not self.doc_id.strip():
            raise ValueError("doc_id must be non-empty")
        if not self.section.strip():
            raise ValueError("section must be non-empty")
        if not self.syndrome.strip():
            raise ValueError("syndrome must be non-empty")
        if not self.chunk_id.strip():
            raise ValueError("chunk_id must be non-empty")

        if self.synthetic is False:
            missing: list[str] = []
            if not self.license or not self.license.strip():
                missing.append("license")
            if not self.attribution or not self.attribution.strip():
                missing.append("attribution")
            if not self.source_url or not self.source_url.strip():
                missing.append("source_url")
            if not self.version or not self.version.strip():
                missing.append("version")
            if not self.retrieved_at or not self.retrieved_at.strip():
                missing.append("retrieved_at")
            if missing:
                fields_str = ", ".join(missing)
                raise ValueError(
                    f"Real protocol (synthetic=False) missing required provenance metadata: "
                    f"{fields_str}"
                )

        if self.status == SourceStatus.REVIEWED and (
            not self.reviewed_by or not self.reviewed_by.strip()
        ):
            raise ValueError("Protocol with status=REVIEWED requires non-empty reviewed_by")

        return self


class ProtocolChunk(BaseModel):
    """Structured clinical protocol chunk with full provenance and parse diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    title: str = ""
    section: str
    chunk_id: str
    parent_id: str | None = None
    text: str
    indexed_text: str = ""
    population: str
    syndrome: str
    synthetic: bool = True
    version: str = "1.0.0"
    content_hash: str = ""
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    reviewed_by: str | None = None
    source_status: SourceStatus = SourceStatus.PLACEHOLDER_UNRETRIEVED
    unparsed_lines: tuple[str, ...] = ()
    parse_warnings: tuple[str, ...] = ()
    suspicious_patterns: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def populate_computed_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            text = str(data.get("text", ""))
            doc_id = str(data.get("doc_id", ""))
            title = str(data.get("title", "") or "")
            section = str(data.get("section", ""))
            syndrome = str(data.get("syndrome", ""))
            chunk_id = str(data.get("chunk_id", ""))

            if not data.get("content_hash"):
                data["content_hash"] = compute_content_hash(text)
            if not data.get("indexed_text"):
                data["indexed_text"] = build_contextual_header(
                    title=title,
                    doc_id=doc_id,
                    section=section,
                    syndrome=syndrome,
                    chunk_id=chunk_id,
                    text=text,
                )
        return data


def _parse_frontmatter(
    content: str, source_path: Path | None = None
) -> tuple[ProtocolFrontmatter, str]:
    """Extract and validate YAML frontmatter at the start of a protocol file."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(f"Missing or malformed YAML frontmatter in protocol file {source_path}")

    fm_raw, body_raw = match.groups()
    try:
        loaded = yaml.safe_load(fm_raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML syntax in frontmatter of {source_path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"Frontmatter must be a YAML mapping in {source_path}")

    if "synthetic" not in loaded:
        raise ValueError(
            f"Missing required 'synthetic' boolean field in frontmatter of {source_path}"
        )

    if "population" in loaded and isinstance(loaded["population"], str):
        loaded["population"] = loaded["population"].strip().lower()
    if "syndrome" in loaded and isinstance(loaded["syndrome"], str):
        loaded["syndrome"] = loaded["syndrome"].strip().lower()

    try:
        fm = ProtocolFrontmatter.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Frontmatter validation failed in {source_path}: {exc}") from exc

    return fm, body_raw


def chunk_protocol_markdown(content: str, source_path: Path | None = None) -> list[ProtocolChunk]:
    """Parse protocol markdown file with YAML frontmatter into structured parent/child chunks.

    Enforces a grammar-based state machine over body lines:
    - Structural lines (# Title, > Disclaimer, ## Section, ---) are tracked as headers.
    - Numbered IF ... THEN ... (+ optional ELSE IF / ELSE / bullet sub-steps) become
      atomic child chunks ({chunk_id}_NODE_{i}).
    - Any numbered node missing THEN or any non-structural trailing/stray line is
      recorded in parent.unparsed_lines and never bled into child decision nodes.
    """
    fm, body_raw = _parse_frontmatter(content, source_path=source_path)

    raw_lines = body_raw.splitlines()
    inferred_title = fm.title or ""
    structural_lines: list[str] = []
    valid_nodes: list[str] = []
    unparsed_lines: list[str] = []
    parse_warnings: list[str] = []

    current_item_lines: list[str] = []
    current_item_is_if: bool = False

    def _flush_current_item() -> None:
        nonlocal current_item_lines, current_item_is_if
        if not current_item_lines:
            return
        node_text = "\n".join(current_item_lines).strip()
        has_then = bool(_THEN_CLAUSE_RE.search(node_text))
        if current_item_is_if and has_then:
            valid_nodes.append(node_text)
        else:
            for ln in current_item_lines:
                stripped = ln.strip()
                if stripped:
                    unparsed_lines.append(stripped)
            reason = (
                "Decision node starts with IF but lacks a THEN clause"
                if current_item_is_if
                else "Numbered item does not start with IF condition"
            )
            preview = current_item_lines[0].strip()
            msg = f"{reason}: '{preview}'"
            parse_warnings.append(msg)
            logger.warning("Protocol %s parse warning: %s", fm.doc_id, msg)
        current_item_lines = []
        current_item_is_if = False

    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped:
            continue

        # 1. Check horizontal rule
        if _HR_RE.match(stripped):
            _flush_current_item()
            structural_lines.append(stripped)
            continue

        # 2. Check markdown heading (#, ##, etc.)
        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            _flush_current_item()
            hashes, heading_text = heading_match.groups()
            if len(hashes) == 1 and not inferred_title:
                inferred_title = heading_text.strip()
            structural_lines.append(stripped)
            continue

        # 3. Check blockquote / disclaimer
        if _BLOCKQUOTE_RE.match(stripped):
            _flush_current_item()
            structural_lines.append(stripped)
            continue

        # 4. Check start of a numbered item (e.g. "1. IF ..." or "2. Something...")
        if _NUMBERED_ITEM_RE.match(stripped):
            _flush_current_item()
            current_item_lines = [stripped]
            current_item_is_if = bool(_NUMBERED_IF_RE.match(stripped))
            continue

        # 5. Inside an active numbered item: check if continuation line
        if current_item_lines:
            is_indented = raw_line.startswith((" ", "\t"))
            is_clause = bool(_CONTINUATION_CLAUSE_RE.match(stripped))
            if is_indented or is_clause:
                # Preserve clean 3-space indentation for continuation lines
                current_item_lines.append(f"   {stripped}")
                continue
            # Otherwise, unindented non-clause text terminates the current item
            _flush_current_item()

        # 6. Any other non-empty line outside a valid numbered item is unparsed
        unparsed_lines.append(stripped)
        msg = f"Unparsed body line outside decision node: '{stripped}'"
        parse_warnings.append(msg)

    _flush_current_item()

    doc_title = inferred_title or fm.doc_id
    body_clean = "\n".join(line.rstrip() for line in raw_lines).strip()

    parent_chunk = ProtocolChunk(
        doc_id=fm.doc_id,
        title=doc_title,
        section=fm.section,
        chunk_id=fm.chunk_id,
        parent_id=None,
        text=body_clean,
        population=fm.population,
        syndrome=fm.syndrome,
        synthetic=fm.synthetic,
        version=fm.version,
        license=fm.license,
        attribution=fm.attribution,
        source_url=fm.source_url,
        retrieved_at=fm.retrieved_at,
        reviewed_by=fm.reviewed_by,
        source_status=fm.status,
        unparsed_lines=tuple(unparsed_lines),
        parse_warnings=tuple(parse_warnings),
    )

    chunks: list[ProtocolChunk] = [parent_chunk]

    for idx, node_text in enumerate(valid_nodes, start=1):
        child_chunk_id = f"{fm.chunk_id}_NODE_{idx}"
        chunks.append(
            ProtocolChunk(
                doc_id=fm.doc_id,
                title=doc_title,
                section=fm.section,
                chunk_id=child_chunk_id,
                parent_id=fm.chunk_id,
                text=node_text,
                population=fm.population,
                syndrome=fm.syndrome,
                synthetic=fm.synthetic,
                version=fm.version,
                license=fm.license,
                attribution=fm.attribution,
                source_url=fm.source_url,
                retrieved_at=fm.retrieved_at,
                reviewed_by=fm.reviewed_by,
                source_status=fm.status,
            )
        )

    return chunks


def verify_round_trip_invariant(content: str, chunks: list[ProtocolChunk]) -> bool:
    """Verify that every non-empty body line is accounted for without silent loss or bleed.

    Every non-empty line in the markdown body must belong to either:
    - Structural headers/dividers (#, >, ---), OR
    - Exactly one child decision node chunk, OR
    - parent.unparsed_lines.
    And no line in parent.unparsed_lines may appear in any child decision node.
    """
    if not chunks:
        return False
    parent = chunks[0]
    children = [c for c in chunks[1:] if c.parent_id == parent.chunk_id]

    _, body_raw = _parse_frontmatter(content)
    body_lines = [ln.strip() for ln in body_raw.splitlines() if ln.strip()]

    child_lines: list[str] = []
    for child in children:
        for ln in child.text.splitlines():
            if ln.strip():
                child_lines.append(ln.strip())

    unparsed_set = set(parent.unparsed_lines)
    child_line_set = set(child_lines)

    # Disjointness between unparsed lines and child node lines
    if unparsed_set & child_line_set:
        return False

    for ln in body_lines:
        is_structural = bool(_HR_RE.match(ln) or _HEADING_RE.match(ln) or _BLOCKQUOTE_RE.match(ln))
        if is_structural:
            continue
        if ln not in child_line_set and ln not in unparsed_set:
            return False

    return True


def chunk_decision_graph_json(graph_data: dict[str, Any]) -> list[ProtocolChunk]:
    """Convert a structured JSON decision graph (flowchart adapter) into ProtocolChunks.

    Supports converting structured clinical flowcharts (nodes + edges) into
    atomic IF/THEN ProtocolChunks with full provenance validation.
    """
    fm = ProtocolFrontmatter.model_validate(graph_data.get("frontmatter", {}))
    nodes_raw = graph_data.get("nodes", [])
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise ValueError("Decision graph JSON must contain a non-empty 'nodes' list")

    doc_title = fm.title or fm.doc_id
    rendered_nodes: list[str] = []

    for idx, node in enumerate(nodes_raw, start=1):
        if not isinstance(node, dict):
            raise ValueError(f"Decision graph node {idx} must be a mapping")
        cond = str(node.get("if_condition", "")).strip()
        then_act = str(node.get("then_action", "")).strip()
        else_act = str(node.get("else_action", "")).strip()
        if not cond or not then_act:
            raise ValueError(f"Decision graph node {idx} requires 'if_condition' and 'then_action'")
        lines = [f"{idx}. IF {cond}:", f"   THEN {then_act}"]
        if else_act:
            lines.append(f"   ELSE {else_act}")
        rendered_nodes.append("\n".join(lines))

    parent_text = f"# {doc_title}\n\n## {fm.section}\n" + "\n".join(rendered_nodes)
    parent = ProtocolChunk(
        doc_id=fm.doc_id,
        title=doc_title,
        section=fm.section,
        chunk_id=fm.chunk_id,
        parent_id=None,
        text=parent_text,
        population=fm.population,
        syndrome=fm.syndrome,
        synthetic=fm.synthetic,
        version=fm.version,
        license=fm.license,
        attribution=fm.attribution,
        source_url=fm.source_url,
        retrieved_at=fm.retrieved_at,
        reviewed_by=fm.reviewed_by,
        source_status=fm.status,
    )
    result = [parent]
    for idx, node_text in enumerate(rendered_nodes, start=1):
        result.append(
            ProtocolChunk(
                doc_id=fm.doc_id,
                title=doc_title,
                section=fm.section,
                chunk_id=f"{fm.chunk_id}_NODE_{idx}",
                parent_id=fm.chunk_id,
                text=node_text,
                population=fm.population,
                syndrome=fm.syndrome,
                synthetic=fm.synthetic,
                version=fm.version,
                license=fm.license,
                attribution=fm.attribution,
                source_url=fm.source_url,
                retrieved_at=fm.retrieved_at,
                reviewed_by=fm.reviewed_by,
                source_status=fm.status,
            )
        )
    return result
