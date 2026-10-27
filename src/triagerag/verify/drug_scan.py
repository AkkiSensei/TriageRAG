"""Drug prose scan verification module.

Safety Property (Section 10):
Detects leaked drug names, active ingredients, brands, and classes inside
narrative instructions. Enforces that drug actions are bound strictly
via the structured drug_id field, never via free-text instructions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from triagerag.engine.registry import ClinicalRegistry


class DrugLexicon:
    """Compiled lookup lexicon for clinical drugs, aliases, and classes."""

    def __init__(self, registry: ClinicalRegistry) -> None:
        self.lexicon: set[str] = set()

        for drug_id, drug in registry.formulary_drugs.items():
            self.lexicon.add(drug_id.lower())
            for ing in drug.ingredient_ids:
                self.lexicon.add(ing.lower())
            for cls in drug.classes:
                self.lexicon.add(cls.lower().replace("_", " "))

        for alias_key in registry.aliases:
            self.lexicon.add(alias_key.lower().replace("-", " "))

        for ing, clss in registry.classes.ingredient_to_classes.items():
            self.lexicon.add(ing.lower())
            for c in clss:
                self.lexicon.add(c.lower().replace("_", " "))

        # Filter out very short words that could trigger false positives
        self.lexicon = {w for w in self.lexicon if len(w) >= 3}


def scan_narrative_for_drug_leaks(
    narrative: str,
    bound_drug_id: str | None,
    registry: ClinicalRegistry,
) -> list[str]:
    """Scan narrative instruction for drug or class tokens.

    Section 10: Any drug/class token in narrative_instruction not equal to
    the bound drug_id constitutes a prose leak violation.
    """
    lexicon_words = DrugLexicon(registry).lexicon
    bound_tokens: set[str] = set()
    if bound_drug_id:
        bound_clean = bound_drug_id.lower().strip()
        bound_tokens.add(bound_clean)
        drug = registry.get_drug(bound_clean)
        if drug:
            for ing in drug.ingredient_ids:
                bound_tokens.add(ing.lower())

    # Tokenize narrative
    narrative_clean = re.sub(r"[^A-Za-z0-9\s]", " ", narrative.lower())
    tokens = narrative_clean.split()

    leaks: list[str] = []
    for token in tokens:
        if len(token) < 4:
            continue

        # If token matches the explicitly bound drug or its ingredient, it is permitted
        if token in bound_tokens:
            continue

        # Check exact membership in lexicon
        if token in lexicon_words:
            leaks.append(token)
            continue

        # Fuzzy check against lexicon for misspellings (min length 5)
        if len(token) >= 5:
            for target in lexicon_words:
                if target in bound_tokens:
                    continue
                if len(target) >= 5 and abs(len(token) - len(target)) <= 2:
                    ratio = fuzz.ratio(token, target)
                    if ratio >= 88:
                        leaks.append(f"{token} (matched {target})")
                        break

    return leaks
