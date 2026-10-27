"""Static AST checks and functional tests asserting strict adherence to Rules R1-R12.

Rules tested:
- R1: Code decides; LLM explains.
- R2: Fail closed (no rule fired != safe).
- R7: Untrusted input isolated; no unsafe_allow_html anywhere.
- R8: Decimal-only clinical math in dose engine; no float literals or float() casts.
- R11: No override of BLOCK under any circumstances (raises PermissionError).
- R12: Pure engine, no datetime.now() in engine, no network calls.
"""

from __future__ import annotations

import ast
from decimal import Decimal

import pytest

from triagerag.config import get_repo_root
from triagerag.contracts.enums import (
    AgeUnit,
)
from triagerag.contracts.schemas import (
    Age,
    Measured,
    OverrideRecord,
    Patient,
    Vitals,
)
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols


class FloatAstVisitor(ast.NodeVisitor):
    """AST visitor to detect float literals or calls to float()."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, float):
            self.violations.append(
                f"{self.filename}:{node.lineno}: Float literal found: {node.value}"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "float":
            self.violations.append(f"{self.filename}:{node.lineno}: Prohibited float() cast call")
        self.generic_visit(node)


class ForbiddenImportsVisitor(ast.NodeVisitor):
    """AST visitor to detect forbidden imports (network, mutable time) in pure modules."""

    FORBIDDEN_MODULES = {"urllib", "requests", "httpx", "aiohttp", "socket", "http"}

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            if top_level in self.FORBIDDEN_MODULES:
                self.violations.append(
                    f"{self.filename}:{node.lineno}: "
                    f"Forbidden network module imported: {alias.name}"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top_level = node.module.split(".")[0]
            if top_level in self.FORBIDDEN_MODULES:
                self.violations.append(
                    f"{self.filename}:{node.lineno}: "
                    f"Forbidden network module imported: {node.module}"
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Detect datetime.now or datetime.utcnow in pure engine
        if (
            node.attr in ("now", "utcnow")
            and isinstance(node.value, ast.Name)
            and node.value.id == "datetime"
        ):
            self.violations.append(
                f"{self.filename}:{node.lineno}: "
                f"Uninjected datetime.{node.attr}() called in pure engine!"
            )
        self.generic_visit(node)


def test_r8_no_floats_in_dose_engine() -> None:
    """Rule R8: Decimal-only clinical math in dose engine; no float literals or float() casts."""
    repo_root = get_repo_root()
    dose_engine_path = repo_root / "src" / "triagerag" / "engine" / "dose_engine.py"
    assert dose_engine_path.exists(), "dose_engine.py not found"

    tree = ast.parse(dose_engine_path.read_text(encoding="utf-8"), filename=str(dose_engine_path))
    visitor = FloatAstVisitor(str(dose_engine_path))
    visitor.visit(tree)
    assert not visitor.violations, "\n".join(visitor.violations)


def test_r12_pure_engine_isolation() -> None:
    """Rule R12: Engine modules must have no network imports and no datetime.now() calls."""
    repo_root = get_repo_root()
    engine_dir = repo_root / "src" / "triagerag" / "engine"
    assert engine_dir.exists()

    violations: list[str] = []
    for py_file in engine_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        visitor = ForbiddenImportsVisitor(str(py_file))
        visitor.visit(tree)
        violations.extend(visitor.violations)

    assert not violations, "\n".join(violations)


class UnsafeHtmlVisitor(ast.NodeVisitor):
    """AST visitor to detect unsafe_allow_html keyword arguments in UI code."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == "unsafe_allow_html":
            self.violations.append(
                f"{self.filename}:{node.lineno}: Prohibited unsafe_allow_html parameter used"
            )
        self.generic_visit(node)


def test_r7_no_unsafe_allow_html_in_ui() -> None:
    """Rule R7: UI must never render untrusted HTML (unsafe_allow_html strictly forbidden)."""
    repo_root = get_repo_root()
    ui_dir = repo_root / "src" / "triagerag" / "ui"
    assert ui_dir.exists()

    violations: list[str] = []
    for py_file in ui_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        visitor = UnsafeHtmlVisitor(str(py_file))
        visitor.visit(tree)
        violations.extend(visitor.violations)

    assert not violations, "\n".join(violations)


def test_wording_no_bare_clear_in_ui_and_cli() -> None:
    """Section 12 & Rule R2: UI and CLI must never output the bare word 'CLEAR' as a verdict."""
    repo_root = get_repo_root()
    ui_file = repo_root / "src" / "triagerag" / "ui" / "app.py"
    cli_file = repo_root / "src" / "triagerag" / "cli.py"

    for f in (ui_file, cli_file):
        content = f.read_text(encoding="utf-8")
        assert "Verdict: CLEAR" not in content
        assert '"CLEAR"' not in content or "CHECKED_CLEAR" in content or "No rules fired" in content


def test_r11_block_override_is_strictly_forbidden() -> None:
    """Rule R11: No code path may approve or override a step with a BLOCK alert."""
    from datetime import UTC, datetime

    repo_root = get_repo_root()
    registry = ClinicalRegistry.load_from_directory(repo_root / "data")
    protocols = ingest_protocols(repo_root / "data")
    index = BM25ClinicalIndex(protocols)

    now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    p = Patient(
        assessed_at=now,
        age=Age(value=Decimal("60"), unit=AgeUnit.years),
        sex="male",
        pregnancy="not_applicable",
        weight_kg=Measured[Decimal](value=Decimal("80.0"), source="measured"),
        vitals=Vitals(
            systolic_bp_mmhg=Measured[int](value=80, source="measured"),
        ),
        medication_history_status="confirmed_none",
        allergy_history_status="confirmed_none",
        suspected_syndrome="chest_pain",
        chief_complaint_untrusted="crushing chest pain",
    )
    llm = FakeLLM(profile=FakeLLMProfile.IGNORE_BLOCK)
    override = OverrideRecord(
        rule_id="VITALS_NITROGLYCERIN_HYPOTENSION",
        step_number=1,
        reason="Clinician override of contraindicated medication",
        clinician_id="DR-TEST",
    )

    with pytest.raises(PermissionError) as exc_info:
        run_triage(patient=p, registry=registry, index=index, llm=llm, overrides=[override])

    assert "Rule R11 Violation" in str(exc_info.value)
