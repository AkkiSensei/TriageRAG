"""Immutable clinical registry holding formulary drugs, rules, aliases, and score tables.

Safety Property (Rule R12):
The registry is pure and immutable. No global mutable state exists. Functions receive
the registry by dependency injection, enabling safe testing, mutation testing, and
strict determinism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import TypeAdapter

from triagerag.config import get_data_dir
from triagerag.contracts.data_schemas import (
    AcronymMapping,
    AliasEntry,
    ClassesMapping,
    EWSTable,
    FormularyDrug,
)
from triagerag.contracts.rules_schema import (
    ClinicalRule,
)
from triagerag.normalize.aliases import AliasResolver
from triagerag.normalize.yaml_loader import load_yaml_decimal

# Known explicit coverage gaps mandated by Section 5
DEFAULT_COVERAGE_GAPS: tuple[str, ...] = (
    "Dose-dependent drug-drug interactions outside specified thresholds",
    "Herbal, over-the-counter (OTC), and food-drug interactions",
    "Drug-disease contraindications beyond explicit vitals interlocks",
    "Renal and hepatic impairment dose titration adjustments",
    "Medications and investigational agents outside the skeleton formulary",
    "Pharmacogenomic HLA-B*5701 / CYP450 metabolic variants",
)


@dataclass(frozen=True)
class ClinicalRegistry:
    """Immutable in-memory store of all clinical rules and formulary assets."""

    formulary_drugs: dict[str, FormularyDrug]
    aliases: dict[str, AliasEntry]
    classes: ClassesMapping
    acronyms: AcronymMapping
    rules: list[ClinicalRule]
    scoring_tables: dict[str, EWSTable]
    coverage_gaps: tuple[str, ...] = DEFAULT_COVERAGE_GAPS
    version: str = "0.1.0"
    resolver: AliasResolver = field(init=False)

    def __post_init__(self) -> None:
        # Build deterministic alias resolver
        resolver = AliasResolver(
            aliases=self.aliases,
            formulary_drugs=self.formulary_drugs,
            classes=self.classes,
        )
        object.__setattr__(self, "resolver", resolver)

    def get_drug(self, drug_id: str) -> FormularyDrug | None:
        """Lookup formulary drug by ID."""
        return self.formulary_drugs.get(drug_id)

    def get_classes_for_ingredient(self, ingredient_id: str) -> list[str]:
        """Lookup clinical classes for an ingredient."""
        return self.classes.ingredient_to_classes.get(ingredient_id, [])

    def get_scoring_table(self, population_name: str) -> EWSTable | None:
        """Lookup physiological scoring table for a population category."""
        return self.scoring_tables.get(population_name)

    @classmethod
    def load_from_directory(cls, base_dir: Path) -> ClinicalRegistry:
        """Load clinical registry from base data directory."""
        return load_registry(base_dir)

    def with_rules(self, rules: list[ClinicalRule]) -> ClinicalRegistry:
        """Return a copy of the registry with replaced rules (used for mutation testing)."""
        return ClinicalRegistry(
            formulary_drugs=self.formulary_drugs,
            aliases=self.aliases,
            classes=self.classes,
            acronyms=self.acronyms,
            rules=rules,
            scoring_tables=self.scoring_tables,
            coverage_gaps=self.coverage_gaps,
            version=self.version,
        )


def load_registry(data_dir: Path | None = None) -> ClinicalRegistry:
    """Pure factory function loading all YAML datasets into an immutable ClinicalRegistry."""
    base_dir = data_dir or get_data_dir()

    # 1. Load classes
    classes_data = load_yaml_decimal(base_dir / "classes.yaml")
    classes = ClassesMapping.model_validate(classes_data)

    # 2. Load acronyms
    acronyms_data = load_yaml_decimal(base_dir / "acronyms.yaml")
    acronyms = AcronymMapping.model_validate(acronyms_data)

    # 3. Load aliases
    aliases_data = load_yaml_decimal(base_dir / "aliases.yaml")
    aliases: dict[str, AliasEntry] = {}
    for name, a_item in aliases_data.get("aliases", {}).items():
        aliases[name] = AliasEntry.model_validate(a_item)

    # 4. Load formulary
    formulary_drugs: dict[str, FormularyDrug] = {}
    for f in sorted((base_dir / "formulary").glob("*.yaml")):
        drug_data = load_yaml_decimal(f)
        drug = FormularyDrug.model_validate(drug_data)
        formulary_drugs[drug.drug_id] = drug

    # 5. Load rules
    rules: list[ClinicalRule] = []
    rule_adapter = TypeAdapter(ClinicalRule)
    for f in sorted((base_dir / "rules").glob("*.yaml")):
        data = load_yaml_decimal(f)
        for r in data.get("rules", []):
            validated_rule = rule_adapter.validate_python(r)
            rules.append(validated_rule)

    # 6. Load scoring tables
    scoring_tables: dict[str, EWSTable] = {}
    for f in sorted((base_dir / "scoring").glob("*.yaml")):
        score_data = load_yaml_decimal(f)
        table = EWSTable.model_validate(score_data)
        scoring_tables[str(table.population)] = table

    return ClinicalRegistry(
        formulary_drugs=formulary_drugs,
        aliases=aliases,
        classes=classes,
        acronyms=acronyms,
        rules=rules,
        scoring_tables=scoring_tables,
    )
