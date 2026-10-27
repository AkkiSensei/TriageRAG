"""Configuration loader for TriageRAG.

Safety Property:
This module imports nothing from triagerag. It resolves filesystem paths
and environment variables safely and deterministically.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root discovery: this file is at src/triagerag/config.py
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_repo_root() -> Path:
    """Return the absolute path to the repository root directory."""
    return _DEFAULT_REPO_ROOT


def get_data_dir() -> Path:
    """Resolve data directory via env TRIAGERAG_DATA_DIR or repo root discovery."""
    env_dir = os.environ.get("TRIAGERAG_DATA_DIR")
    if env_dir:
        resolved = Path(env_dir).resolve()
        if resolved.exists():
            return resolved
    data_dir = get_repo_root() / "data"
    return data_dir


def is_complaint_included_in_llm() -> bool:
    """Return whether untrusted chief complaint should be passed to LLM (default False)."""
    val = os.environ.get("TRIAGERAG_INCLUDE_COMPLAINT_IN_LLM", "false").lower()
    return val in ("1", "true", "yes", "on")


def get_audit_path() -> Path:
    """Resolve audit log path via env TRIAGERAG_AUDIT_PATH or default to var/audit_log.jsonl."""
    env_path = os.environ.get("TRIAGERAG_AUDIT_PATH")
    if env_path:
        return Path(env_path).resolve()
    return get_repo_root() / "var" / "audit_log.jsonl"
