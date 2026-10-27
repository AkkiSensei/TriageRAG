"""Tasks runner and verification gateway for TriageRAG.

Safety Property:
Provides deterministic cross-platform commands for formatting, linting,
typechecking, layer isolation checking, test execution, and evaluation.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

# Ensure Windows consoles don't crash on utf-8 characters
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

app = typer.Typer(help="TriageRAG tasks runner and verification gateway")


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Run a subprocess command with clear logging."""
    cwd = cwd or REPO_ROOT
    cmd_str = " ".join(cmd)
    typer.secho(f"--> Running: {cmd_str}", fg=typer.colors.CYAN)
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(REPO_ROOT)
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if check and result.returncode != 0:
        typer.secho(
            f"FAILED (code {result.returncode}): {cmd_str}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=result.returncode)
    return result.returncode


@app.command()
def lint(
    fix: Annotated[bool, typer.Option("--fix", help="Automatically fix fixable errors")] = False,
) -> None:
    """Run ruff linter and code formatter checks."""
    typer.secho("=== Running Linters ===", fg=typer.colors.BLUE, bold=True)
    check_args = ["--fix"] if fix else []
    dirs_to_check = [d for d in ["src", "tests", "tools", "eval"] if (REPO_ROOT / d).exists()]
    _run([sys.executable, "-m", "ruff", "check"] + dirs_to_check + check_args)
    if fix:
        _run([sys.executable, "-m", "ruff", "format"] + dirs_to_check)
    else:
        _run([sys.executable, "-m", "ruff", "format", "--check"] + dirs_to_check)
    typer.secho("[OK] Linting clean", fg=typer.colors.GREEN)


@app.command()
def typecheck() -> None:
    """Run mypy strict type checks."""
    typer.secho("=== Running Type Checking (mypy) ===", fg=typer.colors.BLUE, bold=True)
    dirs_to_check = [d for d in ["src", "tests", "tools", "eval"] if (REPO_ROOT / d).exists()]
    _run([sys.executable, "-m", "mypy"] + dirs_to_check)
    typer.secho("[OK] Types clean", fg=typer.colors.GREEN)


@app.command("lint-imports")
def lint_imports() -> None:
    """Enforce architectural layer isolation contracts."""
    typer.secho(
        "=== Checking Layer Isolation (import-linter) ===",
        fg=typer.colors.BLUE,
        bold=True,
    )
    _run([sys.executable, "-m", "importlinter.cli"])
    typer.secho("[OK] Layer isolation intact", fg=typer.colors.GREEN)


@app.command("validate-data")
def validate_data() -> None:
    """Validate all clinical data schemas."""
    typer.secho("=== Validating Clinical Data Schemas ===", fg=typer.colors.BLUE, bold=True)
    _run([sys.executable, "tools/validate_data.py"])
    typer.secho("[OK] Data validation passed", fg=typer.colors.GREEN)


@app.command()
def test(
    marker: Annotated[str | None, typer.Option("-m", help="Pytest marker expression")] = None,
    path: Annotated[str, typer.Option("-k", help="Test filter expression")] = "",
) -> None:
    """Run pytest suite (unit, property, integration)."""
    typer.secho("=== Running Pytest Suites ===", fg=typer.colors.BLUE, bold=True)
    cmd = [sys.executable, "-m", "pytest", "tests"]
    if marker:
        cmd.extend(["-m", marker])
    if path:
        cmd.extend(["-k", path])
    _run(cmd)
    typer.secho("[OK] Tests passed", fg=typer.colors.GREEN)


@app.command()
def eval(
    suite: Annotated[
        str,
        typer.Argument(
            help="Suite to run: all, golden, mechanics, metamorphic, adversarial, "
            "mutation, retrieval, ablation"
        ),
    ] = "all",
) -> None:
    """Run evaluation suites."""
    typer.secho(f"=== Running Evaluation Suite: {suite} ===", fg=typer.colors.BLUE, bold=True)
    suites = {
        "golden": "eval/run_golden.py",
        "mechanics": "eval/run_mechanics.py",
        "metamorphic": "eval/run_metamorphic.py",
        "adversarial": "eval/run_adversarial.py",
        "mutation": "eval/run_mutation.py",
        "retrieval": "eval/run_retrieval.py",
        "ablation": "eval/run_ablation.py",
    }

    if suite == "all":
        targets = list(suites.values())
    elif suite in suites:
        targets = [suites[suite]]
    else:
        valid_suites = ", ".join(suites.keys())
        err_msg = f"Unknown eval suite: {suite}. Choices: {valid_suites}, all"
        typer.secho(err_msg, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    for target in targets:
        target_path = REPO_ROOT / target
        if target_path.exists():
            _run([sys.executable, target])
        else:
            typer.secho(f"Skipping {target} (not yet implemented)", fg=typer.colors.YELLOW)
    typer.secho("[OK] Evaluation suite complete", fg=typer.colors.GREEN)


@app.command()
def ui() -> None:
    """Launch the Streamlit clinical decision support interface."""
    typer.secho("=== Launching Streamlit UI ===", fg=typer.colors.GREEN, bold=True)
    _run([sys.executable, "-m", "streamlit", "run", "src/triagerag/ui/app.py"])


@app.command()
def verify() -> None:
    """Run full gating verification."""
    typer.secho("=" * 60, fg=typer.colors.MAGENTA, bold=True)
    typer.secho("   TRIAGERAG VERIFICATION GATE RUNNER", fg=typer.colors.MAGENTA, bold=True)
    typer.secho("=" * 60, fg=typer.colors.MAGENTA, bold=True)

    lint()
    typecheck()
    lint_imports()

    if (REPO_ROOT / "tools/validate_data.py").exists():
        validate_data()

    if (REPO_ROOT / "tools/provenance_report.py").exists():
        _run([sys.executable, "tools/provenance_report.py"])

    test_files = list((REPO_ROOT / "tests").glob("**/test_*.py"))
    if test_files:
        test()
    else:
        typer.secho("No test files detected yet (skeleton phase)", fg=typer.colors.YELLOW)

    eval_scripts = [
        "eval/run_golden.py",
        "eval/run_mechanics.py",
        "eval/run_metamorphic.py",
        "eval/run_adversarial.py",
    ]
    for ev in eval_scripts:
        if (REPO_ROOT / ev).exists():
            _run([sys.executable, ev])

    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)
    typer.secho("[OK] ALL VERIFICATION GATES GREEN", fg=typer.colors.GREEN, bold=True)
    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":
    app()
