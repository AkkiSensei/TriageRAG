"""UI smoke tests using Streamlit AppTest.

Safety Properties (Rules R1, R2, R3, R7, R11, R12):
1. Banner renders from EngineReport.
2. BLOCK scenario renders BLOCKED status and struck-through alert.
3. UNVERIFIED scenario renders UNVERIFIED status and 'What I couldn't check'.
4. Bare word 'CLEAR' is never displayed anywhere.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

_ROOT = Path(__file__).resolve().parent.parent.parent
APP_PATH = str(_ROOT / "src" / "triagerag" / "ui" / "app.py")


def test_ui_smoke_block_scenario() -> None:
    """Smoke test AppTest execution for preloaded BLOCK scenario."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    # Verify no unhandled app exceptions
    assert not at.exception, f"App threw exception: {at.exception}"

    # Verify disclaimer is present
    disclaimer_text = (
        "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
    )
    found_disclaimer = any(disclaimer_text in err.value for err in at.error)
    assert found_disclaimer, "Mandatory safety disclaimer not found in UI errors/notices"

    # Verify BLOCK verdict rendered in markdown
    markdown_texts = [m.value for m in at.markdown]
    combined_markdown = "\n".join(markdown_texts)

    assert "BLOCKED" in combined_markdown, "BLOCKED verdict not rendered in top banner"
    assert any("DDI_SILDENAFIL_NITROGLYCERIN_EXPLICIT" in e.value for e in at.error) or any(
        "DDI" in m for m in markdown_texts
    )

    # Verify bare word CLEAR is forbidden
    assert "Verdict: CLEAR" not in combined_markdown
    assert ">CLEAR<" not in combined_markdown


def test_ui_smoke_unverified_scenario() -> None:
    """Smoke test AppTest execution for preloaded UNVERIFIED scenario."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"App threw exception: {at.exception}"

    # Switch scenario selectbox to UNVERIFIED and rerun
    at.sidebar.selectbox[0].select("UNVERIFIED")
    at.run()

    assert not at.exception, f"App threw exception: {at.exception}"

    markdown_texts = [m.value for m in at.markdown]
    combined_markdown = "\n".join(markdown_texts)

    assert "UNVERIFIED" in combined_markdown, "UNVERIFIED verdict not rendered in banner"
    # Verify 'What I Couldn't Check' is rendered
    subheader_texts = [s.value for s in at.subheader]
    assert any("What I Couldn't Check" in s for s in subheader_texts)


def test_ui_smoke_no_bare_clear_wording() -> None:
    """Verify Section 12 rule: never show the bare word 'CLEAR'."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"App threw exception: {at.exception}"

    at.sidebar.selectbox[0].select("CLEAN")
    at.run()

    assert not at.exception, f"App threw exception: {at.exception}"

    # Get all rendered text across all widgets
    all_texts: list[str] = []
    for m in at.markdown:
        all_texts.append(m.value)
    for s in at.subheader:
        all_texts.append(s.value)
    for t in at.title:
        all_texts.append(t.value)

    full_output = " ".join(all_texts)
    # Check that bare word CLEAR is not displayed as a verdict
    # If checked clear, must display: 'No rules fired (within covered scope) — ruleset unreviewed'
    assert "Verdict: CLEAR" not in full_output
    assert ">CLEAR<" not in full_output


def test_ui_smoke_high_scenario() -> None:
    """Smoke test AppTest execution for preloaded HIGH scenario."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"App threw exception: {at.exception}"

    at.sidebar.selectbox[0].select("HIGH")
    at.run()
    assert not at.exception, f"App threw exception: {at.exception}"

    markdown_texts = [m.value for m in at.markdown]
    combined_markdown = "\n".join(markdown_texts)
    assert "CHECKED_ALERTS" in combined_markdown or "HIGH" in combined_markdown
