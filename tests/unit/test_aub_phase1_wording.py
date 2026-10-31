"""Unit & drift tests for AUB Phase 1 Task T1.3: Authoritative Verdict Wording (AUB-UX-02).

Safety Property (T1.3 / AUB-UX-02):
1. data/wording/verdicts.json is the single source of truth for verdict copy across API and web.
2. web/src/lib/wording.json matches data/wording/verdicts.json byte-for-byte.
3. Clear-state action list NEVER includes 'order administration'.
4. Evidence summary appends ellipsis if and only if chunk text exceeds 140 characters.
5. All verdict headlines and displays strictly forbid bare 'CLEAR'.
"""

from __future__ import annotations

import json

from triagerag.config import get_data_dir, get_repo_root
from triagerag.contracts.enums import Verdict
from triagerag.contracts.schemas import (
    EngineReport,
    ProviderMetadata,
    RetrievalReport,
    RetrievedChunk,
)
from triagerag.contracts.wording import get_verdict_entry, load_verdict_wording
from triagerag.orchestrator import build_triage_explanation


def test_verdict_json_and_frontend_wording_json_identical() -> None:
    """data/wording/verdicts.json and web/src/lib/wording.json must be identical (no drift)."""
    repo_root = get_repo_root()
    canonical_path = repo_root / "data" / "wording" / "verdicts.json"
    frontend_path = repo_root / "web" / "src" / "lib" / "wording.json"

    assert canonical_path.exists(), f"Missing canonical wording file: {canonical_path}"
    assert frontend_path.exists(), f"Missing frontend wording copy: {frontend_path}"

    canonical_data = json.loads(canonical_path.read_text(encoding="utf-8"))
    frontend_data = json.loads(frontend_path.read_text(encoding="utf-8"))

    assert canonical_data == frontend_data, (
        "Wording drift detected between data/wording/verdicts.json and web/src/lib/wording.json"
    )


def test_clear_state_action_list_removes_order_administration() -> None:
    """Action list for CHECKED_CLEAR must NOT contain 'order administration' (AUB-UX-02)."""
    data = load_verdict_wording(get_data_dir())
    clear_entry = data["verdicts"]["CHECKED_CLEAR"]
    actions = clear_entry["actions"]

    assert len(actions) > 0
    for action in actions:
        assert "order administration" not in action.lower(), (
            f"Found forbidden 'order administration' in action: {action}"
        )


def test_verdict_wording_snapshot_coverage() -> None:
    """Verify all four verdicts exist and forbid bare 'CLEAR'."""
    expected_verdicts = ["BLOCKED", "UNVERIFIED", "CHECKED_ALERTS", "CHECKED_CLEAR"]
    for v_name in expected_verdicts:
        entry = get_verdict_entry(v_name)
        assert entry["label"] == v_name
        assert len(entry["badge"]) > 0
        assert len(entry["headline"]) > 0
        assert len(entry["summary"]) > 0
        assert len(entry["actions"]) > 0

        # Never display bare "CLEAR"
        display = entry["display"]
        if "CLEAR" in display:
            assert "CHECKED CLEAR" in display, f"Bare CLEAR found in display: {display}"


def test_evidence_summary_ellipsis_conditional_on_length() -> None:
    """Evidence summary appends ellipsis if and only if excerpt is truncated (> 140 chars)."""
    short_text = "Epinephrine IM 0.3mg immediately."  # 34 chars < 140
    long_text = "A" * 150  # 150 chars > 140

    def make_chunk(text: str) -> RetrievedChunk:
        return RetrievedChunk(
            doc_id="DOC_1",
            section="Section 1",
            chunk_id="C1",
            parent_id="DOC_1",
            text=text,
            population="adult",
            syndrome="anaphylaxis",
        )

    engine_report = EngineReport(
        verdict=Verdict.UNVERIFIED,
        checks_run=1,
        checks_skipped=[],
        unresolved_entities=[],
        ruleset_coverage=[],
        coverage_gaps=[],
        unverified_rules_evaluated=0,
    )

    # 1. Short text: should NOT end with ellipsis (...)
    retrieval_short = RetrievalReport(
        chunks=[make_chunk(short_text)],
        query="test",
        filters={},
        stage_scores={},
        abstained=False,
    )
    explanation_short = build_triage_explanation(
        engine=engine_report,
        retrieval=retrieval_short,
        verified_steps=[],
        patient=None,
        provider_info=ProviderMetadata(),
        llm_fallback_mode=False,
    )
    assert not explanation_short.evidence_summary.endswith('..."')
    assert f'Excerpt: "{short_text}"' in explanation_short.evidence_summary

    # 2. Long text: MUST end with ellipsis (...)
    retrieval_long = RetrievalReport(
        chunks=[make_chunk(long_text)],
        query="test",
        filters={},
        stage_scores={},
        abstained=False,
    )
    explanation_long = build_triage_explanation(
        engine=engine_report,
        retrieval=retrieval_long,
        verified_steps=[],
        patient=None,
        provider_info=ProviderMetadata(),
        llm_fallback_mode=False,
    )
    assert explanation_long.evidence_summary.endswith('..."')
    assert f'Excerpt: "{"A" * 140}..."' in explanation_long.evidence_summary
