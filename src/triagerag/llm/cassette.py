"""Cassette record/replay and local LLM provider interface.

Safety Properties (Rules R1, R3, R12, AUB T7.7, HD-14):
1. Code decides; LLM only drafts (Rule R1).
2. Deterministic cassette replay allows bit-for-bit reproducible plan drafting
   without stochastic variation or network access.
3. HD-14 Approval Boundary: Live external or local neural LLM execution requires
   explicit human approval (`approved_by`) and verified weights. Unapproved live
   inference raises `LLMProviderApprovalError` (fail-closed).
4. Cassette matching uses cryptographic SHA-256 hashes of canonical context and prompts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from triagerag.contracts.schemas import PlanContext, PlanDraft
from triagerag.llm.prompts import build_draft_prompt, build_repair_prompt
from triagerag.llm.provider import LLMProvider


class LLMProviderApprovalError(PermissionError):
    """Raised when an unapproved local or external LLM provider is invoked (AUB HD-14)."""

    pass


class CassetteNotFoundError(KeyError):
    """Raised when a required cassette entry is missing during replay."""

    pass


def canonical_hash_context(context: PlanContext) -> str:
    """Generate deterministic SHA-256 hash of canonical PlanContext fields."""
    normalized = {
        "population": str(context.population_category.value),
        "vitals_flags": sorted(context.vitals_derived_flags),
        "allowed_drug_ids": sorted(context.allowed_drug_ids),
        "pass1_alert_summaries": sorted(context.pass1_alert_summaries),
        "retrieved_chunk_ids": [c.chunk_id for c in context.retrieved_chunks],
        "chief_complaint": context.chief_complaint_delimited or "",
    }
    encoded = json.dumps(normalized, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_hash_text(text: str) -> str:
    """Generate SHA-256 hash of prompt or violation strings."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class CassetteEntry(BaseModel):
    """Deterministic recorded input/output interaction tape entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_hash: str
    prompt_hash: str
    stage: str  # "draft" | "repair"
    violations_hash: str = ""
    response_draft: dict[str, Any]
    recorded_at: str
    provider_name: str


class CassetteTape(BaseModel):
    """Collection of recorded cassette entries for deterministic replay."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0.0"
    tape_id: str
    entries: list[CassetteEntry] = Field(default_factory=list)

    def find_entry(
        self,
        context_hash: str,
        prompt_hash: str,
        stage: str,
        violations_hash: str = "",
    ) -> CassetteEntry | None:
        """Find matching cassette entry by key hashes."""
        for entry in self.entries:
            if (
                entry.context_hash == context_hash
                and entry.prompt_hash == prompt_hash
                and entry.stage == stage
                and entry.violations_hash == violations_hash
            ):
                return entry
        return None

    def add_entry(self, entry: CassetteEntry) -> None:
        """Add or replace an entry."""
        for i, existing in enumerate(self.entries):
            if (
                existing.context_hash == entry.context_hash
                and existing.prompt_hash == entry.prompt_hash
                and existing.stage == entry.stage
                and existing.violations_hash == entry.violations_hash
            ):
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def save(self, file_path: Path) -> None:
        """Save tape to disk as JSON."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path) -> CassetteTape:
        """Load tape from disk."""
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


class CassetteReplayProvider(LLMProvider):
    """Deterministic LLM Provider that replays recorded PlanDraft responses."""

    def __init__(
        self,
        tape: CassetteTape,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self.tape = tape
        self.fallback_provider = fallback_provider

    def draft_plan(self, context: PlanContext) -> PlanDraft:
        ctx_hash = canonical_hash_context(context)
        prompt = build_draft_prompt(context)
        p_hash = canonical_hash_text(prompt)

        entry = self.tape.find_entry(context_hash=ctx_hash, prompt_hash=p_hash, stage="draft")
        if entry is not None:
            return PlanDraft.model_validate(entry.response_draft)

        if self.fallback_provider is not None:
            return self.fallback_provider.draft_plan(context)

        raise CassetteNotFoundError(
            f"No cassette entry found for draft (context_hash={ctx_hash[:8]}, prompt_hash={p_hash[:8]})"
        )

    def repair_plan(
        self,
        context: PlanContext,
        draft: PlanDraft,
        violations: list[str],
    ) -> PlanDraft:
        ctx_hash = canonical_hash_context(context)
        prompt = build_repair_prompt(context, draft, violations)
        p_hash = canonical_hash_text(prompt)
        v_hash = canonical_hash_text(",".join(sorted(violations)))

        entry = self.tape.find_entry(
            context_hash=ctx_hash,
            prompt_hash=p_hash,
            stage="repair",
            violations_hash=v_hash,
        )
        if entry is not None:
            return PlanDraft.model_validate(entry.response_draft)

        if self.fallback_provider is not None:
            return self.fallback_provider.repair_plan(context, draft, violations)

        raise CassetteNotFoundError(
            f"No cassette entry found for repair (context_hash={ctx_hash[:8]}, prompt_hash={p_hash[:8]})"
        )


class LocalLLMConfig(BaseModel):
    """Configuration for local LLM provider (AUB HD-14)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_id: str
    weights_path: Path | None = None
    approved_by: str | None = None
    status: str = "BLOCKED_EXTERNAL"  # "APPROVED_LOCAL" | "BLOCKED_EXTERNAL"


class ApprovedLocalProvider(LLMProvider):
    """Interface for approved local neural LLM models under AUB HD-14 governance."""

    def __init__(self, config: LocalLLMConfig) -> None:
        self.config = config
        self._enforce_approval()

    def _enforce_approval(self) -> None:
        """Enforce HD-14: unapproved local models are blocked."""
        if not self.config.approved_by or self.config.status != "APPROVED_LOCAL":
            raise LLMProviderApprovalError(
                f"HD-14 Human Decision Gate: Local LLM provider '{self.config.model_id}' "
                f"has status '{self.config.status}' and approved_by={self.config.approved_by}. "
                "Executing live neural language models requires verified weights and documented clinician "
                "approval. Default offline FakeLLM or CassetteReplayProvider must be used."
            )

    def draft_plan(self, context: PlanContext) -> PlanDraft:
        self._enforce_approval()
        raise NotImplementedError("Live neural generation requires local inference backend")

    def repair_plan(
        self,
        context: PlanContext,
        draft: PlanDraft,
        violations: list[str],
    ) -> PlanDraft:
        self._enforce_approval()
        raise NotImplementedError("Live neural repair requires local inference backend")
