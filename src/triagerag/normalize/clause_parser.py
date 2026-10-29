"""Deterministic clause-scoped clinical action and drug binding parser (FG-01, FG-16).

Safety Properties (Rules R1, R2, R3, FG-01, FG-16):
1. Parses protocol decision node THEN/ELSE clauses into clause-scoped (action, drug_id) pairs
   using verified formulary and alias lexicons.
2. Splits multi-action clauses on punctuation, contrasting conjunctions, and coordinated action
   verbs ('withhold metoprolol and initiate intravenous fluid resuscitation') so an administer
   verb in a second clause never leaks onto a withheld drug in the first clause.
3. Flips action cue polarity when a negation token ('not', 'never', 'no', 'don't', 'avoid')
   appears within 3 tokens before the cue in the same clause.
4. Marks any clause mentioning a formulary drug without a bindable action cue as 'unparsed'
   (fail closed).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import DrugAction, Provenance
from triagerag.normalize.yaml_loader import load_yaml_decimal


class ActionCuesConfig(BaseModel):
    """Configuration for citation overlap thresholds and clinical action cue lexicons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "2.0.0"
    min_overlap_threshold: float = 0.12
    min_then_coverage: float = 0.20
    min_span_chars: int = 10
    administer_cues: list[str]
    withhold_cues: list[str]
    negation_tokens: list[str] = Field(
        default_factory=lambda: [
            "not",
            "never",
            "no",
            "dont",
            "don't",
            "avoid",
            "without",
            "refrain",
            "neither",
            "nor",
        ]
    )
    non_drug_action_cues: list[str] = Field(
        default_factory=lambda: [
            "obtain",
            "assess",
            "monitor",
            "monitoring",
            "attach",
            "check",
            "support",
            "repeat",
            "consult",
            "select",
            "establish",
            "perform",
            "measure",
            "reassess",
            "position",
            "elevate",
            "secure",
            "provide",
            "escalate",
            "screen",
            "initiate",
        ]
    )
    stopwords: list[str] = Field(
        default_factory=lambda: [
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "if",
            "in",
            "into",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "then",
            "to",
            "under",
            "via",
            "with",
            "patient",
            "adult",
            "paediatric",
        ]
    )
    provenance: Provenance


@lru_cache
def load_action_cues(data_dir: Path | None = None) -> ActionCuesConfig:
    """Load action cue lexicon and citation verification thresholds from YAML."""
    resolved_dir = data_dir if data_dir is not None else get_data_dir()
    cues_path = resolved_dir / "retrieval" / "action_cues.yaml"
    raw = load_yaml_decimal(cues_path)
    return ActionCuesConfig.model_validate(raw)


@lru_cache
def load_default_drug_term_map(data_dir: Path | None = None) -> dict[str, set[str]]:
    """Build mapping from canonical drug_id to lowercase surface forms from formulary & aliases."""
    resolved_dir = data_dir if data_dir is not None else get_data_dir()
    drug_map: dict[str, set[str]] = {}

    formulary_dir = resolved_dir / "formulary"
    if formulary_dir.exists():
        for fpath in sorted(formulary_dir.glob("*.yaml")):
            raw = load_yaml_decimal(fpath)
            if isinstance(raw, dict) and isinstance(raw.get("drug_id"), str):
                did = raw["drug_id"].strip().lower()
                drug_map.setdefault(did, {did, did.replace("_", " ")})

    aliases_path = resolved_dir / "aliases.yaml"
    if aliases_path.exists():
        raw_aliases = load_yaml_decimal(aliases_path)
        if isinstance(raw_aliases, dict) and isinstance(raw_aliases.get("aliases"), dict):
            for alias_name, entry in raw_aliases["aliases"].items():
                if isinstance(entry, dict) and isinstance(entry.get("ingredient_ids"), list):
                    for ing in entry["ingredient_ids"]:
                        if isinstance(ing, str):
                            did = ing.strip().lower()
                            drug_map.setdefault(did, {did, did.replace("_", " ")}).add(
                                str(alias_name).strip().lower()
                            )

    return drug_map


_IF_START_RE = re.compile(r"(?:^|\n)\s*(?:\d+\.\s*)?IF\b", re.IGNORECASE)
_THEN_ELSE_RE = re.compile(r"\b(?:THEN|ELSE(?:\s+IF\b.*?\bTHEN)?)\b", re.IGNORECASE | re.DOTALL)


def has_if_then_structure(text: str) -> bool:
    """Return True if text has both an IF condition and a THEN/ELSE clause."""
    return bool(_IF_START_RE.search(text) and _THEN_ELSE_RE.search(text))


def extract_then_else_text(text: str) -> str:
    """Extract the THEN/ELSE action portion of a protocol decision node."""
    match = re.search(r"\bTHEN\b(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return "THEN " + match.group(1).strip()
    return text.strip()


def content_tokens(text: str, stopwords: set[str] | None = None) -> set[str]:
    """Extract lowercase alphanumeric content tokens excluding stopwords."""
    raw_tokens = {t.lower() for t in re.findall(r"\b[A-Za-z0-9]+\b", text)}
    if stopwords is None:
        return raw_tokens
    return {t for t in raw_tokens if t not in stopwords}


def split_action_clauses(action_text: str, cues_cfg: ActionCuesConfig) -> list[str]:
    """Split a THEN/ELSE action region into atomic action clauses."""
    # 1. Split on sentence/clause punctuation and explicit contrast connectors
    primary_parts = re.split(
        r"[.;\n]+|\b(?:but|except|however|whereas|separately)\b",
        action_text,
        flags=re.IGNORECASE,
    )

    all_verb_Starters: set[str] = set()
    for cue in (
        cues_cfg.administer_cues
        + cues_cfg.withhold_cues
        + cues_cfg.non_drug_action_cues
        + cues_cfg.negation_tokens
    ):
        first_word = cue.strip().lower().split()[0]
        if first_word:
            all_verb_Starters.add(first_word)

    verb_alt = "|".join(sorted((re.escape(w) for w in all_verb_Starters), key=len, reverse=True))
    coord_pattern = re.compile(
        rf"(?:,\s*|\s+\b(?:and|then|or)\s+)(?=(?:{verb_alt})\b)",
        flags=re.IGNORECASE,
    )

    clauses: list[str] = []
    for part in primary_parts:
        cleaned = re.sub(r"^\s*(?:THEN|ELSE)\b\s*,?\s*", "", part.strip(), flags=re.IGNORECASE)
        if not cleaned:
            continue
        sub_parts = coord_pattern.split(cleaned)
        for sp in sub_parts:
            sp_clean = sp.strip(" ,")
            if sp_clean:
                clauses.append(sp_clean)
    return clauses


def _find_clause_cues(
    clause_lower: str,
    cues_cfg: ActionCuesConfig,
    *,
    enable_negation_flip: bool = True,
) -> list[tuple[str, int, int]]:
    """Find (polarity, start_char, end_char) for all administer/withhold cues in a clause."""
    word_spans: list[tuple[str, int, int]] = [
        (m.group(0).lower(), m.start(), m.end())
        for m in re.finditer(r"[A-Za-z0-9']+", clause_lower)
    ]
    neg_set = {n.lower() for n in cues_cfg.negation_tokens}

    # Only use single-word cues or multi-word cues that do not embed a negation prefix
    # when negation flip is disabled; when enabled, negation tokens within 3 words flip polarity.
    raw_cues: list[tuple[str, str]] = []
    for c in cues_cfg.administer_cues:
        raw_cues.append(("administer", c.lower()))
    for c in cues_cfg.withhold_cues:
        if not enable_negation_flip and any(w in neg_set for w in c.lower().split()[:-1]):
            continue
        raw_cues.append(("withhold", c.lower()))

    # Sort multi-word cues first so longer spans claim their character ranges first
    raw_cues.sort(key=lambda item: len(item[1]), reverse=True)

    claimed_ranges: list[tuple[int, int]] = []
    found_cues: list[tuple[str, int, int]] = []

    for base_polarity, cue_str in raw_cues:
        for match in re.finditer(rf"\b{re.escape(cue_str)}\b", clause_lower):
            c_start, c_end = match.start(), match.end()
            if any(not (c_end <= s or c_start >= e) for s, e in claimed_ranges):
                continue

            polarity = base_polarity
            if enable_negation_flip and not any(w in neg_set for w in cue_str.split()):
                # Find index of first word of cue in word_spans
                cue_word_idx: int | None = None
                for idx, (_, ws, _) in enumerate(word_spans):
                    if ws == c_start:
                        cue_word_idx = idx
                        break
                if cue_word_idx is not None:
                    window_start = max(0, cue_word_idx - 3)
                    preceding_words = [word_spans[i][0] for i in range(window_start, cue_word_idx)]
                    if any(pw in neg_set for pw in preceding_words):
                        polarity = "withhold" if base_polarity == "administer" else "administer"

            claimed_ranges.append((c_start, c_end))
            found_cues.append((polarity, c_start, c_end))

    found_cues.sort(key=lambda item: item[1])
    return found_cues


def parse_clause_drug_actions(
    text: str,
    drug_term_map: dict[str, set[str]] | None = None,
    cues_cfg: ActionCuesConfig | None = None,
    *,
    data_dir: Path | None = None,
    enable_clause_split: bool = True,
    enable_negation_flip: bool = True,
) -> tuple[DrugAction, ...]:
    """Parse a protocol decision node into clause-bound DrugAction records."""
    cfg = cues_cfg if cues_cfg is not None else load_action_cues(data_dir)
    d_map = drug_term_map if drug_term_map is not None else load_default_drug_term_map(data_dir)

    action_region = extract_then_else_text(text)
    clauses = split_action_clauses(action_region, cfg) if enable_clause_split else [action_region]

    actions: list[DrugAction] = []
    for clause in clauses:
        clause_lower = " ".join(clause.split()).lower()
        if not clause_lower:
            continue

        # Identify all drug occurrences in this clause (including multiple mentions)
        drug_hits: list[tuple[str, int, int]] = []
        claimed_drug_spans: list[tuple[int, int]] = []
        for drug_id, terms in sorted(d_map.items()):
            for term in sorted(terms, key=len, reverse=True):
                for m in re.finditer(rf"\b{re.escape(term)}\b", clause_lower):
                    s, e = m.start(), m.end()
                    if any(not (e <= cs or s >= ce) for cs, ce in claimed_drug_spans):
                        continue
                    claimed_drug_spans.append((s, e))
                    drug_hits.append((drug_id, s, e))

        if not drug_hits:
            continue

        clause_cues = _find_clause_cues(
            clause_lower,
            cfg,
            enable_negation_flip=enable_negation_flip,
        )

        for drug_id, d_start, d_end in sorted(drug_hits, key=lambda x: x[1]):
            preceding = [c for c in clause_cues if c[2] <= d_start]
            following = [c for c in clause_cues if c[1] >= d_end]

            bound_polarity: Literal["administer", "withhold", "unparsed"] = "unparsed"
            if preceding:
                # Bind to nearest preceding cue in this atomic clause
                nearest_prec = max(preceding, key=lambda c: c[2])
                if nearest_prec[0] == "administer":
                    bound_polarity = "administer"
                elif nearest_prec[0] == "withhold":
                    bound_polarity = "withhold"
            elif following:
                polarities = {c[0] for c in following}
                if len(polarities) == 1:
                    sole = next(iter(polarities))
                    if sole == "administer":
                        bound_polarity = "administer"
                    elif sole == "withhold":
                        bound_polarity = "withhold"

            actions.append(
                DrugAction(
                    action=bound_polarity,
                    drug_id=drug_id,
                    clause_text=clause.strip(),
                )
            )

    return tuple(actions)
