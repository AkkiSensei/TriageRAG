"""FastAPI backend adapter for TriageRAG.

Safety Property:
Thin API adapter over deterministic orchestrator; contains ZERO clinical logic.
"""

from __future__ import annotations

from triagerag.api.app import app, create_app

__all__ = ["app", "create_app"]
