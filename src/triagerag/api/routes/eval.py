"""Evaluation reports endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from triagerag.api.schemas import EvalSummaryResponse
from triagerag.config import get_repo_root

router = APIRouter(prefix="/eval", tags=["eval"])


def _read_report_json(report_path: Path) -> dict[str, Any]:
    if report_path.exists():
        try:
            val = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(val, dict):
                return val
        except Exception:
            return {}
    return {}


@router.get("/summary", response_model=EvalSummaryResponse)
def get_eval_summary() -> EvalSummaryResponse:
    reports_dir = get_repo_root() / "eval" / "reports"

    return EvalSummaryResponse(
        golden=_read_report_json(reports_dir / "golden.json"),
        mechanics=_read_report_json(reports_dir / "mechanics.json"),
        metamorphic=_read_report_json(reports_dir / "metamorphic.json"),
        adversarial=_read_report_json(reports_dir / "adversarial.json"),
        mutation=_read_report_json(reports_dir / "mutation.json"),
        retrieval=_read_report_json(reports_dir / "retrieval.json"),
        ablation=_read_report_json(reports_dir / "ablation.json"),
    )
