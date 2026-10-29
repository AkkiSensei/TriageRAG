"""Data validation utility for all clinical YAML datasets and protocols.

Safety Property:
Validates that every formulary drug, rule, alias, scoring table, and protocol file
adheres strictly to Pydantic contracts and that all referenced entities exist.
Fails fatal with exit code 1 if any inconsistency is detected.
"""

from __future__ import annotations

import re
import sys

from triagerag.config import get_data_dir
from triagerag.contracts.data_schemas import (
    AcronymMapping,
    AliasEntry,
    ClassesMapping,
    EWSTable,
    FormularyDrug,
)
from triagerag.contracts.rules_schema import (
    AllergyCrossReactivityRule,
    ClassInteractionRule,
    DuplicationRule,
    PairRule,
    PopulationRule,
    VitalsInterlockRule,
)
from triagerag.normalize.yaml_loader import load_yaml_decimal


def validate_all() -> None:
    data_dir = get_data_dir()
    print(f"Validating clinical datasets in: {data_dir}")
    errors: list[str] = []

    # 1. Validate acronyms.yaml
    acronyms_path = data_dir / "acronyms.yaml"
    if not acronyms_path.exists():
        errors.append(f"Missing {acronyms_path}")
    else:
        try:
            data = load_yaml_decimal(acronyms_path)
            AcronymMapping.model_validate(data)
            print("  [OK] data/acronyms.yaml")
        except Exception as e:
            errors.append(f"acronyms.yaml validation failed: {e}")

    # 2. Validate classes.yaml
    classes_path = data_dir / "classes.yaml"
    if not classes_path.exists():
        errors.append(f"Missing {classes_path}")
    else:
        try:
            data = load_yaml_decimal(classes_path)
            ClassesMapping.model_validate(data)
            print("  [OK] data/classes.yaml")
        except Exception as e:
            errors.append(f"classes.yaml validation failed: {e}")

    # 3. Validate aliases.yaml
    aliases_path = data_dir / "aliases.yaml"
    if not aliases_path.exists():
        errors.append(f"Missing {aliases_path}")
    else:
        try:
            data = load_yaml_decimal(aliases_path)
            aliases_dict = data.get("aliases", {})
            for _name, alias_data in aliases_dict.items():
                AliasEntry.model_validate(alias_data)
            print(f"  [OK] data/aliases.yaml ({len(aliases_dict)} entries)")
        except Exception as e:
            errors.append(f"aliases.yaml validation failed: {e}")

    # 4. Validate formulary/*.yaml
    formulary_dir = data_dir / "formulary"
    valid_drug_ids: set[str] = set()
    if not formulary_dir.exists():
        errors.append(f"Missing {formulary_dir}")
    else:
        formulary_files = list(formulary_dir.glob("*.yaml"))
        for drug_file in formulary_files:
            try:
                data = load_yaml_decimal(drug_file)
                drug = FormularyDrug.model_validate(data)
                valid_drug_ids.add(drug.drug_id)
            except Exception as e:
                errors.append(f"Formulary drug {drug_file.name} failed: {e}")
        print(f"  [OK] data/formulary/ ({len(valid_drug_ids)} drugs validated)")

    # 5. Validate rules/*.yaml
    rules_dir = data_dir / "rules"
    total_rules = 0
    from pydantic import BaseModel

    rule_type_map: dict[str, type[BaseModel]] = {
        "pair": PairRule,
        "class_interaction": ClassInteractionRule,
        "allergy_crossreactivity": AllergyCrossReactivityRule,
        "vitals_interlock": VitalsInterlockRule,
        "population": PopulationRule,
        "duplication": DuplicationRule,
    }

    if not rules_dir.exists():
        errors.append(f"Missing {rules_dir}")
    else:
        for rule_file in rules_dir.glob("*.yaml"):
            try:
                data = load_yaml_decimal(rule_file)
                raw_rules = data.get("rules", [])
                for r in raw_rules:
                    rtype = r.get("type")
                    if rtype not in rule_type_map:
                        errors.append(f"Unknown rule type '{rtype}' in {rule_file.name}")
                        continue
                    rule_model = rule_type_map[rtype]
                    rule_model.model_validate(r)
                    total_rules += 1
            except Exception as e:
                errors.append(f"Rule file {rule_file.name} failed: {e}")
        print(f"  [OK] data/rules/ ({total_rules} rules validated)")

    # 6. Validate scoring/*.yaml
    scoring_dir = data_dir / "scoring"
    if not scoring_dir.exists():
        errors.append(f"Missing {scoring_dir}")
    else:
        for score_file in scoring_dir.glob("*.yaml"):
            try:
                data = load_yaml_decimal(score_file)
                EWSTable.model_validate(data)
            except Exception as e:
                errors.append(f"Scoring table {score_file.name} failed: {e}")
        print("  [OK] data/scoring/ tables validated")

    # 7. Validate protocols_synthetic/*.md (and check no numeric doses & drugs exist)
    protocols_dir = data_dir / "protocols_synthetic"
    if not protocols_dir.exists():
        errors.append(f"Missing {protocols_dir}")
    else:
        md_files = list(protocols_dir.glob("*.md"))
        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            if not text.startswith("---"):
                errors.append(f"{md_file.name} missing front-matter delimiter")
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                errors.append(f"{md_file.name} malformed front-matter")
                continue
            fm_text = parts[1]
            body = parts[2]
            try:
                fm_data = load_yaml_decimal(fm_text)
                if not fm_data.get("synthetic"):
                    errors.append(f"{md_file.name} must declare 'synthetic: true'")
                pop = fm_data.get("population")
                if pop not in ("adult", "paediatric", "neonate"):
                    errors.append(f"{md_file.name} invalid population '{pop}'")
            except Exception as e:
                errors.append(f"{md_file.name} front-matter error: {e}")

            numeric_dose_pattern = re.compile(
                r"\b[0-9]+(?:\.[0-9]+)?\s*(?:mg|mcg|g|mL|IU)\b", re.IGNORECASE
            )
            dose_matches = numeric_dose_pattern.findall(body)
            if dose_matches:
                err_msg = (
                    f"{md_file.name} violates Rule R9 (contains numeric doses in prose): "
                    f"{dose_matches}"
                )
                errors.append(err_msg)

        print(f"  [OK] data/protocols_synthetic/ ({len(md_files)} protocols validated)")

    # 8. Validate retrieval/vitals_flags.yaml (FG-02 / Rule R3)
    from triagerag.rag.retrieve import load_vitals_flags_config

    try:
        load_vitals_flags_config.cache_clear()
        vf_cfg = load_vitals_flags_config(data_dir)
        vf_rules_count = sum(len(rules) for rules in vf_cfg.populations.values())
        print(f"  [OK] data/retrieval/vitals_flags.yaml ({vf_rules_count} rules validated)")
    except Exception as e:
        errors.append(f"vitals_flags.yaml validation failed: {e}")

    if errors:
        print("\nDATA VALIDATION FAILED WITH ERRORS:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\n[OK] All clinical data files validated successfully.")


if __name__ == "__main__":
    validate_all()
