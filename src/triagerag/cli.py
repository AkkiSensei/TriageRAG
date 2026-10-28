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
from triagerag.config import get_audit_path, get_data_dir
from triagerag.contracts.enums import StepStatus, Verdict
from triagerag.contracts.schemas import OverrideRecord, Patient
from triagerag.engine.registry import ClinicalRegistry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestrator import run_triage
from triagerag.rag.chunking import chunk_protocol_markdown, verify_round_trip_invariant
from triagerag.rag.ingest import (
    ingest_protocols_with_report,
    load_corpus_manifest,
)
from triagerag.rag.service import RetrievalService

DISCLAIMER: str = (
    "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
)

app = typer.Typer(
    help="TriageRAG - Emergency triage decision support and plan verification system."
)
corpus_app = typer.Typer(
    help="Corpus validation, provenance report, and chunk inspection commands."
)
app.add_typer(corpus_app, name="corpus")
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
        Path | None,
        typer.Option("--audit-log", help="Path to append-only audit log"),
    ] = None,
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
    service = RetrievalService.create_default(data_dir)
    index = service.index

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
        "audit_log_path": audit_log or get_audit_path(),
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
        Path | None,
        typer.Argument(help="Path to audit log JSONL file"),
    ] = None,
) -> None:
    """Verify cryptographic integrity of audit log."""
    _print_disclaimer()
    target_path = path or get_audit_path()
    if not target_path.exists():
        console.print(f"[red]Error: Audit log file does not exist: {target_path}[/red]")
        raise typer.Exit(code=1)

    is_valid, err = verify_audit_chain(target_path)
    if is_valid:
        console.print(f"[bold green]Audit log '{path}' verified: INTEGRITY INTACT.[/bold green]")
    else:
        console.print(f"[bold red]Audit log TAMPER DETECTED: {err}[/bold red]")
        raise typer.Exit(code=1)


@app.command("retrieve")
def retrieve_cmd(
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", help="Preloaded scenario: BLOCK | UNVERIFIED | HIGH | CLEAN"),
    ] = None,
    syndrome: Annotated[
        str | None,
        typer.Option("--syndrome", help="Suspected clinical syndrome to query"),
    ] = None,
    population: Annotated[
        str,
        typer.Option("--population", help="Population slice: adult | paediatric | neonate"),
    ] = "adult",
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Print full BM25 term contribution and abstention trace"),
    ] = True,
    backend: Annotated[
        str,
        typer.Option("--backend", help="Retriever backend: bm25 | dense | hybrid_rrf"),
    ] = "bm25",
) -> None:
    """Execute protocol retrieval and render the Retrieval Inspector diagnostic trace."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from triagerag.contracts.enums import AgeUnit
    from triagerag.contracts.scenarios import get_preloaded_scenario
    from triagerag.contracts.schemas import Age, Measured, Vitals

    _print_disclaimer()
    data_dir = get_data_dir()
    service = RetrievalService.create_default(data_dir, backend=backend)

    if scenario is not None:
        patient, _ = get_preloaded_scenario(scenario)
    else:
        pop_lower = population.lower().strip()
        if pop_lower == "neonate":
            age = Age(value=Decimal("10"), unit=AgeUnit.days)
            weight = Decimal("3.5")
        elif pop_lower == "paediatric":
            age = Age(value=Decimal("6"), unit=AgeUnit.years)
            weight = Decimal("20.0")
        else:
            age = Age(value=Decimal("45"), unit=AgeUnit.years)
            weight = Decimal("75.0")

        patient = Patient(
            assessed_at=datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC),
            age=age,
            sex="female",
            pregnancy="not_applicable" if pop_lower != "adult" else "no",
            weight_kg=Measured[Decimal](value=weight, source="measured"),
            vitals=Vitals(
                heart_rate_bpm=Measured[int](value=115, source="measured"),
                systolic_bp_mmhg=Measured[int](value=85, source="measured"),
            ),
            medication_history_status="confirmed_none",
            allergy_history_status="confirmed_none",
            suspected_syndrome=syndrome,
        )

    trace = service.explain(patient)
    console.print(
        Panel(
            f"Query String: {trace['query']}\n"
            f"Vitals Flags: {trace['vitals_derived_flags']}\n"
            f"Population: {trace['population']} | Raw Syndrome: {trace['raw_syndrome']} -> "
            f"Normalized: {trace['normalized_syndrome']}\n"
            f"Abstained: {trace['abstained']} | AbstainCode: {trace['abstain_code']}\n"
            f"Reason: {trace['reason']}\n"
            f"Corpus Hash: {trace['corpus_hash'][:16]} | Index Version: {trace['index_version']}",
            title="RETRIEVAL INSPECTOR SUMMARY",
            border_style="cyan",
        )
    )

    if explain and trace.get("bm25_trace"):
        bm25_t = trace["bm25_trace"]
        cand_table = Table(title="BM25 CANDIDATE SCORING TRACE", expand=True)
        cand_table.add_column("Chunk ID")
        cand_table.add_column("Syndrome")
        cand_table.add_column("Score", justify="right")
        cand_table.add_column("Term Contributions")
        for cand in bm25_t.get("candidates", []):
            contrib_str = ", ".join(
                f"{k}={v:.3f}" for k, v in cand.get("term_contributions", {}).items()
            )
            cand_table.add_row(
                str(cand.get("chunk_id")),
                str(cand.get("syndrome")),
                f"{cand.get('total_score', 0.0):.4f}",
                contrib_str or "-",
            )
        console.print(cand_table)


@corpus_app.command("validate")
def corpus_validate(
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory containing protocol corpus"),
    ] = None,
) -> None:
    """Validate all protocol files, frontmatter provenance, and round-trip chunking invariants."""
    _print_disclaimer()
    target_dir = data_dir or get_data_dir()
    report = ingest_protocols_with_report(target_dir, strict_unparsed=True)

    errors: list[str] = []
    if report.quarantined:
        for q in report.quarantined:
            errors.append(f"QUARANTINED {q.path}: {q.reason}")

    if report.unparsed_by_doc:
        for doc_id, lines in report.unparsed_by_doc.items():
            errors.append(f"UNPARSED lines in {doc_id}: {lines}")

    manifest_path = target_dir / "corpus" / "manifest.yaml"
    if manifest_path.exists():
        try:
            manifest = load_corpus_manifest(target_dir)
            parent_hashes = {c.doc_id: c.content_hash for c in report.chunks if c.parent_id is None}
            for entry in manifest.documents:
                actual_hash = parent_hashes.get(entry.doc_id)
                if actual_hash is None:
                    errors.append(f"Manifest document {entry.doc_id} missing from loaded corpus")
                elif actual_hash != entry.content_hash:
                    errors.append(
                        f"Content hash mismatch for {entry.doc_id}: "
                        f"manifest={entry.content_hash[:12]} vs actual={actual_hash[:12]}"
                    )
        except Exception as exc:
            errors.append(f"Manifest validation failed: {exc}")

    if not report.loaded_docs and not errors:
        errors.append(f"FAILED: No valid protocol documents found in {target_dir}")

    if errors:
        for err_msg in errors:
            console.print(f"[bold red]{err_msg}[/bold red]")
        console.print(
            f"[bold red]CORPUS VALIDATION FAILED ({len(errors)} error(s), "
            f"{len(report.quarantined)} quarantined).[/bold red]"
        )
        raise typer.Exit(code=1)

    console.print(
        f"[bold green]CORPUS VALIDATED: {len(report.loaded_docs)} documents, "
        f"{len(report.chunks)} chunks, 0 quarantined. "
        f"Corpus Hash: {report.corpus_hash[:16]}[/bold green]"
    )


@corpus_app.command("report")
def corpus_report(
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory containing protocol corpus"),
    ] = None,
) -> None:
    """Print detailed corpus provenance, population/syndrome distribution, and quarantine report."""
    _print_disclaimer()
    target_dir = data_dir or get_data_dir()
    report = ingest_protocols_with_report(target_dir, strict_unparsed=False)

    table = Table(title=f"CORPUS REPORT (Hash: {report.corpus_hash[:16]})", expand=True)
    table.add_column("Chunk ID")
    table.add_column("Doc ID")
    table.add_column("Pop")
    table.add_column("Syndrome")
    table.add_column("Type")
    table.add_column("Version")
    table.add_column("Hash (12)")

    for c in report.chunks:
        kind = "SYNTHETIC" if c.synthetic else f"REAL ({c.source_status.value})"
        table.add_row(
            c.chunk_id,
            c.doc_id,
            c.population,
            c.syndrome,
            kind,
            c.version,
            c.content_hash[:12],
        )
    console.print(table)

    if report.quarantined:
        for q in report.quarantined:
            console.print(f"[yellow]Quarantined: {q.path} -> {q.reason}[/yellow]")


@corpus_app.command("explain")
def corpus_explain(
    target: Annotated[str, typer.Argument(help="Chunk ID or path to markdown protocol file")],
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory containing protocol corpus"),
    ] = None,
) -> None:
    """Inspect how a protocol file or chunk ID is parsed, contextualized, and hashed."""
    _print_disclaimer()
    candidate_path = Path(target)
    if candidate_path.exists() and candidate_path.is_file():
        content = candidate_path.read_text(encoding="utf-8")
        chunks = chunk_protocol_markdown(content, source_path=candidate_path)
        invariant_ok = verify_round_trip_invariant(content, chunks)
        console.print(f"[bold]Round-trip invariant:[/bold] {invariant_ok}")
    else:
        target_dir = data_dir or get_data_dir()
        all_chunks = ingest_protocols_with_report(target_dir, strict_unparsed=False).chunks
        chunks = [c for c in all_chunks if c.chunk_id == target or c.doc_id == target]
        if not chunks:
            console.print(f"[red]No chunk or document found matching '{target}'[/red]")
            raise typer.Exit(code=1)

    for c in chunks:
        console.print(
            Panel(
                f"Doc ID: {c.doc_id}\n"
                f"Chunk ID: {c.chunk_id} (Parent: {c.parent_id})\n"
                f"Population: {c.population} | Syndrome: {c.syndrome}\n"
                f"Synthetic: {c.synthetic} | Status: {c.source_status.value}\n"
                f"Hash: {c.content_hash}\n"
                f"Unparsed Lines: {list(c.unparsed_lines)}\n\n"
                f"--- Indexed Text ---\n{c.indexed_text}",
                title=f"Chunk {c.chunk_id}",
            )
        )


@corpus_app.command("add")
def corpus_add(
    file_path: Annotated[Path, typer.Argument(help="Path to candidate protocol markdown file")],
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory containing protocol corpus"),
    ] = None,
) -> None:
    """Validate and add a protocol markdown file to the corpus."""
    _print_disclaimer()
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(code=1)
    content = file_path.read_text(encoding="utf-8")
    try:
        chunks = chunk_protocol_markdown(content, source_path=file_path)
    except Exception as exc:
        console.print(f"[red]Validation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not verify_round_trip_invariant(content, chunks) or chunks[0].unparsed_lines:
        console.print(f"[red]Protocol has unparsed lines: {list(chunks[0].unparsed_lines)}[/red]")
        raise typer.Exit(code=1)

    target_dir = data_dir or get_data_dir()
    dest_subdir = "protocols_synthetic" if chunks[0].synthetic else "protocols_real"
    dest_dir = target_dir / dest_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / file_path.name
    dest_file.write_text(content, encoding="utf-8")
    console.print(f"[green]Added {file_path.name} -> {dest_file}[/green]")


if __name__ == "__main__":
    app()
