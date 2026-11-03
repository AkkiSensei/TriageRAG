"""Unit tests for honest architecture and documentation terminology (AUB-GEN-01 / AUB-DOC-03 / T0.7).

Safety Properties (Rule R3, Rule R18):
1. Verifies that documentation accurately describes the offline deterministic mock generator (FakeLLM).
2. Forbids misleading terminology ("Merkle", ungrounded "dense", bare "LLM explains") in user-facing documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_readme_and_handoff_forbid_merkle() -> None:
    """T0.7 / AUB-DOC-03: Audit log is a SHA-256 linear hash chain; 'Merkle' is forbidden in docs."""
    for filename in ("README.md", "HANDOFF.md"):
        path = REPO_ROOT / filename
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "merkle" not in text.lower(), f"Forbidden term 'Merkle' found in {filename}"


def test_readme_forbids_unqualified_dense_retrieval() -> None:
    """T0.7 / AUB-RET-05 / D6: Offline retrieval is lexical; 'dense' is forbidden in README."""
    readme_path = REPO_ROOT / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    # Word boundary match for 'dense'
    assert not re.search(r"\bdense\b", text, flags=re.IGNORECASE), (
        "Forbidden term 'dense' found in README.md"
    )


def test_readme_llm_explains_has_mock_qualifier() -> None:
    """T0.7 / AUB-GEN-01: 'LLM explains' must carry the deterministic mock qualification."""
    readme_path = REPO_ROOT / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    for match in re.finditer(r"llm\s+explains", text, flags=re.IGNORECASE):
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 150)
        window = text[start:end].lower()
        assert "mock" in window or "interface" in window, (
            f"Bare 'LLM explains' found without mock/interface qualifier in context:\n{window}"
        )
