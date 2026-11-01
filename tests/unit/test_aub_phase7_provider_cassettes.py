"""Unit tests for Phase 7 cassette replay provider and HD-14 local model approval (AUB T7.7)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from triagerag.contracts.enums import ActionType, DoseUnit, PopulationCategory, Route
from triagerag.contracts.schemas import (
    ExplicitDose,
    PlanContext,
    PlanDraft,
    PlanStepDraft,
    RetrievedChunk,
    SpanCitation,
)
from triagerag.llm.cassette import (
    ApprovedLocalProvider,
    CassetteEntry,
    CassetteNotFoundError,
    CassetteReplayProvider,
    CassetteTape,
    LLMProviderApprovalError,
    LocalLLMConfig,
    canonical_hash_context,
    canonical_hash_text,
)
from triagerag.llm.fake import FakeLLM
from triagerag.llm.prompts import build_draft_prompt


def _make_dummy_context() -> PlanContext:
    chunk = RetrievedChunk(
        doc_id="PROTO-01",
        section="1.0",
        chunk_id="chk-01",
        text="Administer epinephrine 0.5mg IM for severe anaphylaxis.",
        population="adult",
        syndrome="anaphylaxis",
        score=Decimal("5.0"),
    )
    return PlanContext(
        population_category=PopulationCategory.adult,
        vitals_derived_flags=["HYPOTENSION"],
        allowed_drug_ids=["epinephrine"],
        pass1_alert_summaries=[],
        retrieved_chunks=[chunk],
    )


def test_canonical_hash_context_determinism():
    """Verify hash is bit-for-bit deterministic regardless of dictionary order."""
    ctx1 = _make_dummy_context()
    ctx2 = _make_dummy_context()

    assert canonical_hash_context(ctx1) == canonical_hash_context(ctx2)
    assert len(canonical_hash_context(ctx1)) == 64  # SHA-256


def test_cassette_record_save_load_replay(tmp_path):
    """Verify recording a PlanDraft to tape, saving, loading, and replaying."""
    ctx = _make_dummy_context()
    prompt = build_draft_prompt(ctx)
    ctx_hash = canonical_hash_context(ctx)
    p_hash = canonical_hash_text(prompt)

    draft = PlanDraft(
        matched_protocol_title="Anaphylaxis Adult Emergency",
        steps=[
            PlanStepDraft(
                step_number=1,
                action_type=ActionType.administer,
                narrative_instruction="Administer first-line agent via intramuscular injection",
                drug_id="epinephrine",
                requested_dose=ExplicitDose(amount=Decimal("0.5"), unit=DoseUnit.mg),
                route=Route.im,
                citations=[
                    SpanCitation(
                        doc_id="PROTO-01",
                        section="1.0",
                        chunk_id="chk-01",
                        quoted_span="epinephrine 0.5mg IM",
                    )
                ],
            )
        ],
    )

    entry = CassetteEntry(
        context_hash=ctx_hash,
        prompt_hash=p_hash,
        stage="draft",
        response_draft=draft.model_dump(),
        recorded_at=datetime.now(tz=UTC).isoformat(),
        provider_name="test_recorded_llama",
    )

    tape = CassetteTape(tape_id="tape-test-01", entries=[entry])
    tape_file = tmp_path / "tape.json"
    tape.save(tape_file)

    # Load from disk
    loaded_tape = CassetteTape.load(tape_file)
    assert len(loaded_tape.entries) == 1
    assert loaded_tape.tape_id == "tape-test-01"

    # Replay
    replay_provider = CassetteReplayProvider(tape=loaded_tape)
    replayed_draft = replay_provider.draft_plan(ctx)

    assert replayed_draft.matched_protocol_title == "Anaphylaxis Adult Emergency"
    assert len(replayed_draft.steps) == 1
    assert replayed_draft.steps[0].drug_id == "epinephrine"
    assert replayed_draft.steps[0].requested_dose.amount == Decimal("0.5")


def test_cassette_replay_missing_entry_raises_or_falls_back():
    """Verify CassetteNotFoundError when missing, or clean delegation to fallback."""
    tape = CassetteTape(tape_id="empty-tape")
    ctx = _make_dummy_context()

    provider_no_fallback = CassetteReplayProvider(tape=tape)
    with pytest.raises(CassetteNotFoundError, match="No cassette entry found for draft"):
        provider_no_fallback.draft_plan(ctx)

    # With FakeLLM as fallback
    fallback = FakeLLM()
    provider_with_fallback = CassetteReplayProvider(tape=tape, fallback_provider=fallback)
    draft = provider_with_fallback.draft_plan(ctx)
    assert draft is not None
    assert len(draft.steps) > 0


def test_hd14_local_provider_approval_gate():
    """Verify unapproved local LLM models raise LLMProviderApprovalError (HD-14)."""
    unapproved_cfg = LocalLLMConfig(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        approved_by=None,
        status="BLOCKED_EXTERNAL",
    )
    with pytest.raises(
        LLMProviderApprovalError, match="HD-14 Human Decision Gate.*Local LLM provider"
    ):
        ApprovedLocalProvider(config=unapproved_cfg)

    missing_status_cfg = LocalLLMConfig(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        approved_by="Dr. Clinician",
        status="BLOCKED_EXTERNAL",  # status still blocked
    )
    with pytest.raises(LLMProviderApprovalError, match="HD-14 Human Decision Gate"):
        ApprovedLocalProvider(config=missing_status_cfg)
