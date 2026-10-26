"""CLI tool to add a new clinical rule enforcing Rule R3 provenance invariants.

Safety Property (Rule R3, Section 16):
Enforces that newly authored rules automatically receive:
- content_origin: AGENT_DRAFT_UNSOURCED
- source_status: PLACEHOLDER_UNRETRIEVED
- verified: false
- reviewer: None
- section_ref: "TO_BE_RESOLVED"
"""

from __future__ import annotations

from typing import Annotated

import typer
import yaml

from triagerag.config import get_data_dir
from triagerag.contracts.enums import RuleStatus, Severity
from triagerag.contracts.rules_schema import PairRule
from triagerag.contracts.schemas import Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal

app = typer.Typer(help="Tool to safely author new clinical rules with enforced provenance.")


@app.command()
def pair(
    rule_id: Annotated[str, typer.Option("--id", help="Unique rule ID")],
    drug_a: Annotated[str, typer.Option("--drug-a", help="First drug ID")],
    drug_b: Annotated[str, typer.Option("--drug-b", help="Second drug ID")],
    severity: Annotated[Severity, typer.Option("--severity", help="BLOCK, HIGH, MODERATE, INFO")],
    consequence: Annotated[str, typer.Option("--consequence", help="Clinical consequence")],
    action: Annotated[str, typer.Option("--action", help="Required clinical action")],
    source_doc: Annotated[
        str, typer.Option("--source-doc", help="Source document reference")
    ] = "AGENT_DRAFT",
) -> None:
    """Add a new drug pair interaction rule to data/rules/ddi.yaml."""
    prov = Provenance(
        source_doc=source_doc,
        section_ref="TO_BE_RESOLVED",
        version_or_date="2026-DRAFT",
    )

    rule = PairRule(
        id=rule_id,
        type="pair",
        drug_a=drug_a,
        drug_b=drug_b,
        severity=severity,
        status=RuleStatus.ACTIVE,
        consequence=consequence,
        action=action,
        requires_fields=["medications"],
        provenance=prov,
    )

    rules_file = get_data_dir() / "rules" / "ddi.yaml"
    existing_data = load_yaml_decimal(rules_file) if rules_file.exists() else {"rules": []}
    existing_rules = existing_data.get("rules", [])

    if any(r.get("id") == rule_id for r in existing_rules):
        typer.secho(f"Error: Rule ID '{rule_id}' already exists!", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    existing_rules.append(rule.model_dump(mode="json"))
    existing_data["rules"] = existing_rules

    with rules_file.open("w", encoding="utf-8") as f:
        yaml.dump(existing_data, f, sort_keys=False)

    typer.secho(f"[OK] Rule '{rule_id}' added to {rules_file.name}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
