"""Provenance audit and reporting tool.

Safety Property:
Scans all data assets to ensure 100% provenance compliance. Detects any unverified
facts falsely claiming verified status, enforcing Rule R3.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from triagerag.config import get_data_dir
from triagerag.normalize.yaml_loader import load_yaml_decimal


def generate_provenance_report() -> int:
    console = Console()
    data_dir = get_data_dir()

    table = Table(title="TriageRAG Clinical Data Provenance Audit")
    table.add_column("Category", style="cyan")
    table.add_column("File / Entity", style="magenta")
    table.add_column("Source Status", style="yellow")
    table.add_column("Content Origin", style="blue")
    table.add_column("Verified?", style="bold")
    table.add_column("Reviewer", style="green")

    total_entities = 0
    verified_count = 0
    unverified_count = 0
    violations: list[str] = []

    def audit_provenance(item: dict[str, Any], label: str) -> None:
        nonlocal total_entities, verified_count, unverified_count
        prov = item.get("provenance")
        if not prov:
            violations.append(f"{label} is missing a 'provenance' block!")
            return

        total_entities += 1
        src_status = str(prov.get("source_status", "UNKNOWN"))
        origin = str(prov.get("content_origin", "UNKNOWN"))
        verified = bool(prov.get("verified", False))
        reviewer = str(prov.get("reviewer") or "None")

        if verified:
            verified_count += 1
            if src_status != "REVIEWED" or not reviewer or reviewer == "None":
                err_msg = (
                    f"{label}: verified=True requires source_status='REVIEWED' "
                    "and non-empty reviewer"
                )
                violations.append(err_msg)
            verified_display = "[green]YES (REVIEWED)[/green]"

        else:
            unverified_count += 1
            verified_display = "[red]NO (DRAFT)[/red]"

        parts = label.split(":", 1)
        cat = parts[0]
        entity = parts[1] if len(parts) > 1 else label
        table.add_row(cat, entity, src_status, origin, verified_display, reviewer)

    # Formulary drugs
    for f in sorted((data_dir / "formulary").glob("*.yaml")):
        data = load_yaml_decimal(f)
        audit_provenance(data, f"Formulary:{f.name}")

    # Aliases
    aliases_data = load_yaml_decimal(data_dir / "aliases.yaml")
    for alias_name, alias_item in aliases_data.get("aliases", {}).items():
        audit_provenance(alias_item, f"Alias:{alias_name}")

    # Rules
    for f in sorted((data_dir / "rules").glob("*.yaml")):
        rules_data = load_yaml_decimal(f)
        for r in rules_data.get("rules", []):
            audit_provenance(r, f"Rule:{r.get('id', 'unknown')}")

    # Classes
    classes_data = load_yaml_decimal(data_dir / "classes.yaml")
    audit_provenance(classes_data, "Classes:classes.yaml")

    # Scoring
    for f in sorted((data_dir / "scoring").glob("*.yaml")):
        score_data = load_yaml_decimal(f)
        audit_provenance(score_data, f"Scoring:{f.name}")

    console.print(table)
    console.print(f"\n[bold]Total Entities Audited:[/bold] {total_entities}")
    console.print(f"[bold red]Unverified / Draft:[/bold red] {unverified_count}")
    console.print(f"[bold green]Verified (Reviewed):[/bold green] {verified_count}")

    if violations:
        console.print("\n[bold red]PROVENANCE COMPLIANCE VIOLATIONS:[/bold red]")
        for v in violations:
            console.print(f"  - {v}")
        return 1

    msg = "\n[bold green][OK] Provenance audit passed. No unauthorized verified flags.[/bold green]"
    console.print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(generate_provenance_report())
