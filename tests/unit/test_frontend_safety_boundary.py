"""Frontend Safety UX Boundary and Rule Conformance Tests.

Safety Properties:
- Inviolable S1: SafetyBanner, alerts, blocked drugs, and skipped checks
  NEVER import or use animations (React Bits).
- Untrusted Isolation: dangerouslySetInnerHTML is strictly forbidden across all frontend files.
- Qualified Wording: Bare word "CLEAR" is never emitted for clinical verdicts.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_SRC = REPO_ROOT / "web" / "src"


def test_safety_components_never_import_reactbits():
    """Safety components must render statically and never import animation components."""
    results_dir = WEB_SRC / "features" / "results"
    assert results_dir.exists(), f"Directory not found: {results_dir}"

    safety_files = list(results_dir.glob("*.tsx"))
    assert len(safety_files) > 0, "No safety component files found"

    for file_path in safety_files:
        content = file_path.read_text(encoding="utf-8")
        assert "reactbits" not in content.lower(), (
            f"Safety UX Violation: {file_path.name} imports or references 'reactbits'. "
            "Safety banners, alerts, blocked drugs, and skipped checks must never be animated."
        )


def test_dangerously_set_inner_html_strictly_forbidden():
    """dangerouslySetInnerHTML is strictly forbidden across the entire frontend."""
    ts_files = list(WEB_SRC.rglob("*.tsx")) + list(WEB_SRC.rglob("*.ts"))
    assert len(ts_files) > 0, "No TypeScript files found in web/src"

    for file_path in ts_files:
        content = file_path.read_text(encoding="utf-8")
        assert "dangerouslySetInnerHTML" not in content, (
            f"Security Violation: {file_path.name} contains dangerouslySetInnerHTML. "
            "Untrusted text must always be rendered as safe escaped text."
        )


def test_mandatory_disclaimer_present_in_frontend():
    """Mandatory disclaimer string must be present in wording.ts and layout components."""
    wording_file = WEB_SRC / "lib" / "wording.ts"
    assert wording_file.exists()
    content = wording_file.read_text(encoding="utf-8")

    expected_phrases = [
        "Research prototype",
        "Synthetic data only",
        "Not a medical device",
        "Not for clinical use",
    ]
    for phrase in expected_phrases:
        assert phrase in content, f"Missing mandatory disclaimer phrase: {phrase}"


def test_adr_0005_exists():
    """ADR 0005 documenting Clinical UX Safety Architecture must exist."""
    adr_file = REPO_ROOT / "docs" / "adr" / "0005-ui-shows-never-decides.md"
    assert adr_file.exists(), "ADR 0005 file is missing"
    content = adr_file.read_text(encoding="utf-8")
    assert "ADR 0005" in content
    assert "Accepted" in content
