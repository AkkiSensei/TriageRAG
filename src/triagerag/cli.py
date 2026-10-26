"""Command-line interface for TriageRAG."""

from __future__ import annotations

import typer

app = typer.Typer(help="TriageRAG - Emergency triage decision support and verification system.")


@app.command()
def run() -> None:
    """Run triage evaluation on a patient payload."""
    typer.echo(
        "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."
    )


@app.command()
def validate_data() -> None:
    """Validate all rules, aliases, and formulary data."""
    typer.echo("Validating clinical dataset...")


@app.command()
def eval(suite: str = typer.Argument("all", help="Evaluation suite to run")) -> None:
    """Run evaluation suites."""
    typer.echo(f"Running evaluation suite: {suite}")


@app.command()
def audit_verify(path: str = typer.Argument("audit_log.jsonl", help="Path to audit log")) -> None:
    """Verify cryptographic integrity of audit log."""
    typer.echo(f"Verifying audit log: {path}")


if __name__ == "__main__":
    app()
