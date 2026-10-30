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
    resolved_cmd = list(cmd)
    if resolved_cmd and not Path(resolved_cmd[0]).is_absolute():
        import shutil

        found = shutil.which(resolved_cmd[0])
        if found:
            resolved_cmd[0] = found
    result = subprocess.run(resolved_cmd, cwd=cwd, env=env)
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
def demo() -> None:
    """Run an offline end-to-end demo across preloaded scenarios + retrieval inspector."""
    typer.secho("=== Running TriageRAG Offline Demo ===", fg=typer.colors.GREEN, bold=True)
    _run([sys.executable, "-m", "triagerag.cli", "corpus", "validate"])
    _run([sys.executable, "-m", "triagerag.cli", "retrieve", "--scenario", "BLOCK", "--explain"])
    _run([sys.executable, "-m", "triagerag.cli", "triage", "--scenario", "BLOCK"])


@app.command()
def api(
    host: Annotated[str, typer.Option("--host", help="Host interface to bind")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port to bind")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload")] = False,
) -> None:
    """Launch the FastAPI backend server with Uvicorn."""
    typer.secho(
        f"=== Launching TriageRAG API on http://{host}:{port} ===",
        fg=typer.colors.GREEN,
        bold=True,
    )
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "triagerag.api.app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    _run(cmd)


@app.command(name="export-openapi")
def export_openapi() -> None:
    """Export OpenAPI schema specification to web/openapi/openapi.json."""
    import json

    from triagerag.api.app import app as fastapi_app

    openapi_schema = fastapi_app.openapi()
    out_dir = REPO_ROOT / "web" / "openapi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openapi.json"
    out_file.write_text(json.dumps(openapi_schema, indent=2), encoding="utf-8")
    typer.secho(f"[OK] Exported OpenAPI specification to {out_file}", fg=typer.colors.GREEN)


@app.command(name="web-install")
def web_install() -> None:
    """Install frontend dependencies via npm in web/."""
    web_dir = REPO_ROOT / "web"
    if not web_dir.exists():
        typer.secho("web/ directory does not exist", fg=typer.colors.YELLOW)
        return
    _run(["npm", "install"], cwd=web_dir)


@app.command(name="web-dev")
def web_dev() -> None:
    """Run Vite development server in web/."""
    web_dir = REPO_ROOT / "web"
    _run(["npm", "run", "dev"], cwd=web_dir)


@app.command(name="web-build")
def web_build() -> None:
    """Build production frontend bundle in web/."""
    web_dir = REPO_ROOT / "web"
    _run(["npm", "run", "build"], cwd=web_dir)


@app.command(name="web-verify")
def web_verify() -> None:
    """Run full frontend verification suite: lint, typecheck, tests, and build."""
    web_dir = REPO_ROOT / "web"
    if not (web_dir / "package.json").exists():
        typer.secho("No web/package.json found; skipping web-verify", fg=typer.colors.YELLOW)
        return
    typer.secho("=== Running Frontend Verification ===", fg=typer.colors.BLUE, bold=True)
    _run(["npm", "run", "lint"], cwd=web_dir)
    _run(["npm", "run", "typecheck"], cwd=web_dir)
    _run(["npm", "run", "test"], cwd=web_dir)
    _run(["npm", "run", "build"], cwd=web_dir)
    typer.secho("[OK] Frontend verification green", fg=typer.colors.GREEN)


@app.command(name="verify-fast")
def verify_fast() -> None:
    """Fast developer gate: static analysis, type checking, architecture, and unit tests."""
    typer.secho("=" * 60, fg=typer.colors.BLUE, bold=True)
    typer.secho("   TRIAGERAG FAST VERIFICATION PROFILE", fg=typer.colors.BLUE, bold=True)
    typer.secho("=" * 60, fg=typer.colors.BLUE, bold=True)

    lint()
    typecheck()
    lint_imports()
    validate_data()

    typer.secho("=== Running Unit Test Suite ===", fg=typer.colors.BLUE, bold=True)
    _run([sys.executable, "-m", "pytest", "tests/unit"])

    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)
    typer.secho(
        "[OK] FAST VERIFICATION GATES GREEN (Static, Types, Architecture, Data, Unit)",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)


@app.command(name="verify-full")
def verify_full() -> None:
    """Comprehensive gate: all linters, type checks, full test suites, and mandatory evaluations."""
    typer.secho("=" * 60, fg=typer.colors.MAGENTA, bold=True)
    typer.secho("   TRIAGERAG FULL VERIFICATION GATE RUNNER", fg=typer.colors.MAGENTA, bold=True)
    typer.secho("=" * 60, fg=typer.colors.MAGENTA, bold=True)

    lint()
    typecheck()
    lint_imports()
    validate_data()

    if (REPO_ROOT / "tools/provenance_report.py").exists():
        _run([sys.executable, "tools/provenance_report.py"])

    test()

    mandatory_evals = [
        "eval/run_golden.py",
        "eval/run_mechanics.py",
        "eval/run_metamorphic.py",
        "eval/run_adversarial.py",
        "eval/run_retrieval.py",
    ]
    for ev in mandatory_evals:
        target_path = REPO_ROOT / ev
        if not target_path.exists():
            typer.secho(f"FATAL: Mandatory evaluation suite missing: {ev}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        typer.secho(f"=== Running Mandatory Eval: {ev} ===", fg=typer.colors.BLUE, bold=True)
        _run([sys.executable, str(target_path)])

    web_verify()

    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)
    typer.secho(
        "[OK] FULL VERIFICATION GATES GREEN (Backend, Evals, Web)",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)


@app.command(name="release-preflight")
def release_preflight() -> None:
    """Release preflight gate: verification, report integrity, dependency lock, security posture."""
    typer.secho("=" * 60, fg=typer.colors.CYAN, bold=True)
    typer.secho("   TRIAGERAG RELEASE PREFLIGHT CHECK", fg=typer.colors.CYAN, bold=True)
    typer.secho("=" * 60, fg=typer.colors.CYAN, bold=True)

    verify_full()

    typer.secho("=== Checking Dependency Lockfile ===", fg=typer.colors.BLUE, bold=True)
    lock_file = REPO_ROOT / "requirements.lock"
    if not lock_file.exists() or lock_file.stat().st_size == 0:
        typer.secho("FATAL: requirements.lock missing or empty", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("[OK] requirements.lock verified", fg=typer.colors.GREEN)

    typer.secho("=== Checking Report Integrity ===", fg=typer.colors.BLUE, bold=True)
    _run([sys.executable, "-m", "pytest", "tests/unit/test_report_integrity.py"])

    typer.secho("=== Checking Docker Container Configuration ===", fg=typer.colors.BLUE, bold=True)
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    if "USER root" in dockerfile or "USER 0" in dockerfile:
        typer.secho("FATAL: Dockerfile cannot run as root user", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if "USER triage" not in dockerfile and "USER " not in dockerfile:
        typer.secho(
            "FATAL: Dockerfile must enforce a non-root user (e.g. USER triage)",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    typer.secho("[OK] Container security posture verified (non-root)", fg=typer.colors.GREEN)

    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)
    typer.secho(
        "[OK] RELEASE PREFLIGHT PASSED — CODEBASE READY FOR ARCHIVAL AND DISTRIBUTION",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.secho("=" * 60, fg=typer.colors.GREEN, bold=True)


@app.command(name="release-check")
def release_check() -> None:
    """Alias for release-preflight."""
    release_preflight()


@app.command()
def verify() -> None:
    """Run full gating verification profile (alias for verify-full)."""
    verify_full()


if __name__ == "__main__":
    app()
