"""Medication and allergen alias resolution and fuzzy suggestion.

Safety Property:
Exact and normalized matches are resolved. Fuzzy matches (via rapidfuzz) produce
suggestions ONLY with resolved=False. The engine NEVER silently auto-resolves ambiguous
or misspelled medication names.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rapidfuzz import process, utils

if TYPE_CHECKING:
    from triagerag.contracts.data_schemas import AliasEntry, ClassesMapping, FormularyDrug


def clean_text(text: str) -> str:
    """Normalize text by case-folding, stripping punctuation, and collapsing whitespace."""
    lower = text.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]", " ", lower)
    return " ".join(cleaned.split())


class AliasResolver:
    """Resolver for drug brand names, active ingredients, and class memberships."""

    def __init__(
        self,
        aliases: dict[str, AliasEntry],
        formulary_drugs: dict[str, FormularyDrug],
        classes: ClassesMapping | None = None,
        fuzzy_threshold: float = 75.0,
    ) -> None:
        self.aliases = aliases
        self.formulary_drugs = formulary_drugs
        self.classes = classes
        self.fuzzy_threshold = fuzzy_threshold

        self._exact_lookup: dict[str, str] = {}
        self._clean_lookup: dict[str, str] = {}
        self._all_candidates: list[str] = []

        # 1. Register brand aliases
        for alias_key in aliases:
            self._exact_lookup[alias_key] = alias_key
            self._clean_lookup[clean_text(alias_key)] = alias_key
            self._all_candidates.append(alias_key)

        # 2. Register formulary drugs
        for drug_id, drug in formulary_drugs.items():
            self._exact_lookup[drug_id] = drug_id
            self._clean_lookup[clean_text(drug_id)] = drug_id
            self._clean_lookup[clean_text(drug.display_name)] = drug_id
            self._all_candidates.append(drug_id)
            self._all_candidates.append(drug.display_name)

        # 3. Register all active ingredients from classes.yaml
        if classes:
            for ing in classes.ingredient_to_classes:
                if ing not in self._exact_lookup:
                    self._exact_lookup[ing] = ing
                    self._clean_lookup[clean_text(ing)] = ing
                    self._all_candidates.append(ing)

    def resolve(self, raw_name: str) -> tuple[bool, str | None, str | None]:
        """Resolve a raw medication or allergen name.

        Returns:
            (resolved, resolved_key, suggestion)
            - If exact or stripped match: (True, matched_key, None)
            - If fuzzy match: (False, None, suggested_key)
            - If unresolvable: (False, None, None)
        """
        raw_stripped = raw_name.strip()
        if not raw_stripped:
            return False, None, None

        # 1. Exact match
        if raw_stripped in self._exact_lookup:
            return True, self._exact_lookup[raw_stripped], None

        # 2. Casefold and punctuation-stripped match
        cleaned = clean_text(raw_stripped)
        if cleaned in self._clean_lookup:
            return True, self._clean_lookup[cleaned], None

        # 3. Fuzzy match -> Suggestion ONLY, resolved=False
        match_result = process.extractOne(
            raw_stripped,
            self._all_candidates,
            processor=utils.default_process,
            score_cutoff=self.fuzzy_threshold,
        )

        if match_result:
            matched_candidate, _, _ = match_result
            return False, None, matched_candidate

        return False, None, None
