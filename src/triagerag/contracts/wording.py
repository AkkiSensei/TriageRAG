"""Canonical verdict wording and clinical copy.

Safety Property (T1.3 / AUB-UX-02):
Single authoritative source of verdict wording shared by API and frontend.
Guarantees consistent terminology, plain-language summaries, permitted UI actions,
and prohibition of bare 'CLEAR' across all presentation layers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from triagerag.config import get_data_dir


@lru_cache(maxsize=1)
def load_verdict_wording(data_dir: Path | None = None) -> dict[str, Any]:
    """Load canonical verdict wording contract from data/wording/verdicts.json."""
    target_dir = data_dir or get_data_dir()
    wording_file = target_dir / "wording" / "verdicts.json"
    if not wording_file.exists():
        wording_file = target_dir.parent / "data" / "wording" / "verdicts.json"
    if not wording_file.exists():
        raise FileNotFoundError(f"Canonical verdict wording file not found: {wording_file}")
    with open(wording_file, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def get_verdict_entry(verdict: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Return dictionary of display, badge, headline, summary, and actions for verdict."""
    data = load_verdict_wording(data_dir)
    verdicts: dict[str, Any] = data.get("verdicts", {})
    key = verdict.upper()
    if key in verdicts:
        return verdicts[key]  # type: ignore[no-any-return]
    return {
        "label": key,
        "display": key,
        "badge": key,
        "headline": f"Triage Result: {key}",
        "summary": "Clinical evaluation complete.",
        "actions": ["Review triage report."],
    }
