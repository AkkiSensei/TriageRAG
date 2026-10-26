"""Command-line interface for TriageRAG.

Safety property: CLI renders deterministic EngineReports first and enforces
the mandatory research disclaimer on all outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from triagerag.audit.chain import verify_audit_chain
from triagerag.config import get_data_dir
from triagerag.contracts.enums import StepStatus, Verdict
from triagerag.contracts.schemas import OverrideRecord, Patient
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.index import BM25ClinicalIndex
from triagerag.rag.ingest import ingest_protocols

DISCLAIMER: str = (
    "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
)

app = typer.Typer(
    help="TriageRAG - Emergency triage decision support and plan verification system."
)
console = Console()


def _print_disclaimer() -> None:
    console.print(
        Panel(
            f"[bold red]{DISCLAIMER}[/bold red]",
            border_style="red",
            title="SAFETY NOTICE",
        )
    )


@app.command()
def run(
    patient_file: Annotated[
        Path | None,
        typer.Argument(help="Path to JSON file containing patient payload"),
    ] = None,
    demo: Annotated[
        bool,
        typer.Option("--demo", help="Run with a built-in synthetic scenario (defaults to BLOCK)"),
    ] = False,
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", help="Preloaded scenario: BLOCK | UNVERIFIED | HIGH | CLEAN"),
    ] = None,
    audit_log: Annotated[
        Path,
        typer.Option("--audit-log", help="Path to append-only audit log"),
    ] = Path("audit_log.jsonl"),
    include_complaint_in_llm: Annotated[
        bool,
        typer.Option(
            "--include-complaint-in-llm",
            help="Rule R7: Pass untrusted chief complaint inside delimited prompt block",
        ),
    ] = False,
    overrides_file: Annotated[
        Path | None,
        typer.Option("--overrides", help="Path to JSON file containing list of OverrideRecord"),
    ] = None,
) -> None:
    """Run deterministic triage and plan verification on a patient payload."""
    _print_disclaimer()

    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)
    chunks = ingest_protocols(data_dir)
    index = BM25ClinicalIndex(chunks)

    from triagerag.contracts.scenarios import get_preloaded_scenario

    default_overrides: list[OverrideRecord] = []
    if patient_file is not None:
        if not patient_file.exists():
            console.print(f"[red]Error: Patient file not found: {patient_file}[/red]")
            raise typer.Exit(code=1)
        with open(patient_file, encoding="utf-8") as f:
            patient = Patient.model_validate_json(f.read())
    elif scenario is not None:
        patient, default_overrides = get_preloaded_scenario(scenario)
        console.print(f"[cyan]Loaded preloaded scenario: {scenario.upper()}[/cyan]")
    elif demo:
        patient, default_overrides = get_preloaded_scenario("BLOCK")
        console.print(
            "[cyan]Loaded demo patient scenario: BLOCK (Sildenafil + Nitroglycerin)[/cyan]"
        )
    else:
        console.print(
            "[yellow]No patient file provided. Use --demo or "
            "--scenario [BLOCK|UNVERIFIED|HIGH|CLEAN], "
            "or pass a path to a patient JSON file.[/yellow]"
        )
        raise typer.Exit(code=1)

    overrides: list[OverrideRecord] = []
    if overrides_file is not None and overrides_file.exists():
        with open(overrides_file, encoding="utf-8") as f:
            raw_overrides = json.load(f)
            overrides = [OverrideRecord.model_validate(o) for o in raw_overrides]
    elif default_overrides:
        overrides = default_overrides

    config = {
        "include_complaint_in_llm": include_complaint_in_llm,
        "audit_log_path": audit_log,
    }
    llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)

    response = run_triage(
        patient=patient,
        llm=llm,
        index=index,
        registry=registry,
        config=config,
        overrides=overrides,
    )

    engine = response.engine

    # 1. Fixed Banner (Rule R1, Section 12)
    verdict_color = (
        "red"
        if engine.verdict == Verdict.BLOCKED
        else (
            "yellow" if engine.verdict in (Verdict.UNVERIFIED, Verdict.CHECKED_ALERTS) else "green"
        )
    )

    verdict_display = engine.verdict.value
    if engine.verdict == Verdict.CHECKED_CLEAR:
        # Section 12 wording rule: never show the bare word "CLEAR"
        verdict_display = "No rules fired (within covered scope) — ruleset unreviewed"

    score_val = engine.score.total_score if engine.score else "N/A"
    score_band = engine.score.band.value if engine.score else "UNSCORED"

    banner_table = Table(title="TRIAGE ENGINE REPORT BANNER", expand=True)
    banner_table.add_column("Verdict", style=f"bold {verdict_color}")
    banner_table.add_column("EWS Score", style="bold")
    banner_table.add_column("Band", style="bold")
    banner_table.add_column("Checks Run", justify="right")
    banner_table.add_column("Checks Skipped", justify="right")
    banner_table.add_column("Ruleset Review State", style="italic")

    banner_table.add_row(
        verdict_display,
        str(score_val),
        score_band,
        str(engine.checks_run),
        str(len(engine.checks_skipped)),
        engine.ruleset_review_state,
    )
    console.print(banner_table)

    # 2. Alerts and blocked drugs
    all_alerts = engine.baseline_alerts + engine.plan_alerts
    if all_alerts:
        alert_table = Table(title="CLINICAL SAFETY ALERTS", expand=True)
        alert_table.add_column("Severity", style="bold")
        alert_table.add_column("Rule ID")
        alert_table.add_column("Status")
        alert_table.add_column("Consequence")
        alert_table.add_column("Action")

        for alert in all_alerts:
            sev_color = "red" if alert.severity.value == "BLOCK" else "yellow"
            status_badge = (
                "[dim](UNSOURCED DRAFT)[/dim]"
                if (alert.unverified or not alert.provenance.verified)
                else ""
            )
            alert_table.add_row(
                f"[{sev_color}]{alert.severity.value}[/{sev_color}]",
                alert.rule_id,
                f"{alert.rule_type} {status_badge}",
                alert.consequence,
                alert.action,
            )
        console.print(alert_table)

    # 3. What I couldn't check (Section 12)
    if engine.checks_skipped or engine.unresolved_entities:
        skip_reasons = "\n".join(f" - [{s.rule_id}] {s.reason}" for s in engine.checks_skipped[:5])
        if len(engine.checks_skipped) > 5:
            skip_reasons += f"\n - ... and {len(engine.checks_skipped) - 5} more"
        skip_panel_content = (
            f"Checks Skipped: {len(engine.checks_skipped)}\n"
            f"Unresolved Entities: {', '.join(engine.unresolved_entities) or 'None'}\n"
            f"Reasons (sample):\n{skip_reasons or 'None'}\n"
            "Fail-closed safety active (Rule R2)."
        )
        console.print(
            Panel(
                skip_panel_content,
                title="WHAT I COULD NOT CHECK (FAIL-CLOSED)",
                border_style="yellow",
            )
        )

    # 4. Coverage Gaps (Section 5, 12)
    gap_text = "\n".join(f" - {gap}" for gap in engine.coverage_gaps)
    console.print(Panel(gap_text, title="KNOWN COVERAGE GAPS", border_style="dim"))

    # 5. Verified Plan Steps (Section 10, 12)
    if response.verified_steps:
        plan_table = Table(title="VERIFIED PROTOCOL PLAN STEPS", expand=True)
        plan_table.add_column("#", justify="right")
        plan_table.add_column("Status", style="bold")
        plan_table.add_column("Action")
        plan_table.add_column("Drug")
        plan_table.add_column("Dose")
        plan_table.add_column("Citations")
        plan_table.add_column("Rejection / Warning Notes")

        for v_step in response.verified_steps:
            st = v_step.status
            st_color = (
                "green"
                if st == StepStatus.APPROVED
                else ("red" if st == StepStatus.BLOCKED_STRUCK_THROUGH else "yellow")
            )
            dose_str = (
                f"{v_step.draft.requested_dose.amount} {v_step.draft.requested_dose.unit.value}"
                if v_step.draft.requested_dose
                else "-"
            )
            cites = ", ".join(c.chunk_id for c in v_step.draft.citations)
            notes = "; ".join(v_step.rejection_reasons) or "-"

            plan_table.add_row(
                str(v_step.draft.step_number),
                f"[{st_color}]{st.value}[/{st_color}]",
                v_step.draft.action_type.value,
                v_step.draft.drug_id or "-",
                dose_str,
                cites,
                notes,
            )
        console.print(plan_table)

    # 6. LLM narrative last (Section 12)
    if not response.llm_fallback_mode and response.verified_steps:
        narrative_lines = [
            f"Step {s.draft.step_number}: {s.draft.narrative_instruction}"
            for s in response.verified_steps
        ]
        console.print(
            Panel(
                "\n".join(narrative_lines),
                title="LLM PLAN DRAFT (SYNTHETIC EXPLANATION - DO NOT USE CLINICALLY)",
                border_style="blue",
            )
        )
    elif response.llm_fallback_mode:
        console.print(
            Panel(
                "LLM was bypassed or failed. Safe extractive fallback rendered above.",
                title="LLM FALLBACK MODE ACTIVE",
                border_style="dim",
            )
        )

    console.print(f"[dim]Audit Record Hash: {response.audit_hash}[/dim]")


@app.command()
def validate_data() -> None:
    """Validate all rules, aliases, and formulary data schemas."""
    _print_disclaimer()
    import subprocess
    import sys

    from triagerag.config import get_repo_root

    script = get_repo_root() / "tools" / "validate_data.py"
    res = subprocess.run([sys.executable, str(script)], check=False)
    if res.returncode != 0:
        raise typer.Exit(code=1)


@app.command(name="eval")
def run_eval(
    suite: Annotated[
        str, typer.Argument(help="Evaluation suite to run: golden|mechanics|all")
    ] = "all",
) -> None:
    """Run clinical evaluation suites."""
    _print_disclaimer()
    import subprocess
    import sys

    from triagerag.config import get_repo_root

    repo_root = get_repo_root()
    suite_lower = suite.lower()
    if suite_lower in ("golden", "all"):
        console.print("[bold]Running Golden Suite...[/bold]")
        script = repo_root / "eval" / "run_golden.py"
        res = subprocess.run([sys.executable, str(script)], check=False)
        if res.returncode != 0:
            console.print("[red]Golden suite failed.[/red]")
            raise typer.Exit(code=1)

    if suite_lower in ("mechanics", "all"):
        console.print("[bold]Running Mechanics Suite...[/bold]")
        script = repo_root / "eval" / "run_mechanics.py"
        res = subprocess.run([sys.executable, str(script)], check=False)
        if res.returncode != 0:
            console.print("[red]Mechanics suite failed.[/red]")
            raise typer.Exit(code=1)


@app.command()
def audit_verify(
    path: Annotated[
        Path,
        typer.Argument(help="Path to audit log JSONL file"),
    ] = Path("audit_log.jsonl"),
) -> None:
    """Verify cryptographic integrity of audit log."""
    _print_disclaimer()
    if not path.exists():
        console.print(f"[red]Error: Audit log file does not exist: {path}[/red]")
        raise typer.Exit(code=1)

    is_valid, err = verify_audit_chain(path)
    if is_valid:
        console.print(f"[bold green]Audit log '{path}' verified: INTEGRITY INTACT.[/bold green]")
    else:
        console.print(f"[bold red]Audit log TAMPER DETECTED: {err}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
