"""Protocol decision node patient applicability verification module.

Safety Properties (Rule R1, Rule R2, Rule R3, AUB Phase 5 Task T5.1 / AUB-GRD-01):
1. Verifies that structured patient context satisfies the IF-clause preconditions
   of cited protocol nodes.
2. Tri-state outcomes:
   - MET: Patient satisfies all required predicates and triggers no contraindications.
   - NOT_MET: Patient fails one or more required predicates, or triggers a contraindication.
     Step status resolves to NOT_APPLICABLE.
   - UNKNOWN: Patient data is missing or unmeasured for one or more required predicates.
     Step status resolves to REQUIRES_CLINICIAN_CONFIRMATION.
3. Does not invent clinical criteria; relies exclusively on verified synthetic node predicates.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from triagerag.rag.aliases import load_node_aliases, load_reverse_node_aliases
from triagerag.rag.node_predicates import load_node_predicates_config
from triagerag.rag.predicates import (
    PredicateEvalResult,
    evaluate_predicate,
    load_predicate_vocabulary,
)

if TYPE_CHECKING:
    from triagerag.contracts.schemas import Patient


class ApplicabilityStatus(StrEnum):
    """Evaluation status of a cited protocol node against a patient's clinical state."""

    MET = "MET"
    NOT_MET = "NOT_MET"
    UNKNOWN = "UNKNOWN"


class NodeApplicabilityResult(BaseModel):
    """Applicability assessment for a protocol decision node against patient data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    status: ApplicabilityStatus
    requires_predicates: tuple[str, ...] = ()
    contraindicated_by: tuple[str, ...] = ()
    predicate_evaluations: dict[str, str] = Field(default_factory=dict)
    reason: str


def verify_node_applicability(
    node_id: str,
    patient: Patient,
    *,
    data_dir: Path | None = None,
) -> NodeApplicabilityResult:
    """Verify whether a cited protocol node's preconditions apply to a given patient.

    Args:
        node_id: Unique chunk or node identifier (positional or content-addressed).
        patient: Structured patient record.
        data_dir: Optional data directory for loading predicate definitions.

    Returns:
        NodeApplicabilityResult with status MET, NOT_MET, or UNKNOWN.
    """
    node_predicates_cfg = load_node_predicates_config(data_dir)
    vocab = load_predicate_vocabulary(data_dir)
    pred_map = {p.id: p for p in vocab.predicates}

    # Resolve node_id in node predicate declarations
    decl = node_predicates_cfg.nodes.get(node_id)
    if decl is None:
        # Check alias map
        try:
            aliases = load_node_aliases(data_dir)
            # Try legacy -> content
            canonical_id = aliases.get(node_id)
            if canonical_id and canonical_id in node_predicates_cfg.nodes:
                decl = node_predicates_cfg.nodes[canonical_id]
            else:
                # Try content -> legacy
                rev_aliases = load_reverse_node_aliases(data_dir)
                legacy_id = rev_aliases.get(node_id)
                if legacy_id and legacy_id in node_predicates_cfg.nodes:
                    decl = node_predicates_cfg.nodes[legacy_id]
        except Exception:
            decl = None

    if decl is None:
        # If node_id looks like an IF/THEN decision node but is undeclared, fail closed as UNKNOWN
        if "_NODE_" in node_id or "_NODE" in node_id:
            return NodeApplicabilityResult(
                node_id=node_id,
                status=ApplicabilityStatus.UNKNOWN,
                reason=(
                    f"Decision node '{node_id}' has no declared predicate "
                    "requirements (fail closed)"
                ),
            )
        # Parent / non-decision chunk: no IF conditions declared
        return NodeApplicabilityResult(
            node_id=node_id,
            status=ApplicabilityStatus.MET,
            reason="Parent or non-decision chunk; no IF-clause preconditions required",
        )

    # If explicitly always applicable and has no conditions
    if decl.always_applicable and not decl.requires_predicates and not decl.contraindicated_by:
        return NodeApplicabilityResult(
            node_id=node_id,
            status=ApplicabilityStatus.MET,
            requires_predicates=decl.requires_predicates,
            contraindicated_by=decl.contraindicated_by,
            reason="Node declared always_applicable without preconditions",
        )

    evaluations: dict[str, str] = {}
    unknown_predicates: list[str] = []
    unmet_predicates: list[str] = []
    triggered_contraindications: list[str] = []

    # 1. Evaluate contraindications
    for c_id in decl.contraindicated_by:
        pred_def = pred_map.get(c_id)
        if pred_def is None:
            evaluations[c_id] = "UNKNOWN_PREDICATE_DEFINITION"
            unknown_predicates.append(c_id)
            continue

        res = evaluate_predicate(pred_def, patient)
        evaluations[c_id] = res.value
        if res == PredicateEvalResult.SATISFIED:
            triggered_contraindications.append(c_id)

    if triggered_contraindications:
        contra_str = ", ".join(triggered_contraindications)
        return NodeApplicabilityResult(
            node_id=node_id,
            status=ApplicabilityStatus.NOT_MET,
            requires_predicates=decl.requires_predicates,
            contraindicated_by=decl.contraindicated_by,
            predicate_evaluations=evaluations,
            reason=f"Patient triggers contraindication predicate(s): {contra_str}",
        )

    # 2. Evaluate required preconditions
    for r_id in decl.requires_predicates:
        pred_def = pred_map.get(r_id)
        if pred_def is None:
            evaluations[r_id] = "UNKNOWN_PREDICATE_DEFINITION"
            unknown_predicates.append(r_id)
            continue

        res = evaluate_predicate(pred_def, patient)
        evaluations[r_id] = res.value
        if res == PredicateEvalResult.NOT_SATISFIED:
            unmet_predicates.append(r_id)
        elif res == PredicateEvalResult.UNKNOWN:
            unknown_predicates.append(r_id)

    if unmet_predicates:
        unmet_str = ", ".join(unmet_predicates)
        return NodeApplicabilityResult(
            node_id=node_id,
            status=ApplicabilityStatus.NOT_MET,
            requires_predicates=decl.requires_predicates,
            contraindicated_by=decl.contraindicated_by,
            predicate_evaluations=evaluations,
            reason=f"Patient clinical data does not satisfy required predicate(s): {unmet_str}",
        )

    if unknown_predicates:
        unknown_str = ", ".join(unknown_predicates)
        return NodeApplicabilityResult(
            node_id=node_id,
            status=ApplicabilityStatus.UNKNOWN,
            requires_predicates=decl.requires_predicates,
            contraindicated_by=decl.contraindicated_by,
            predicate_evaluations=evaluations,
            reason=(
                f"Patient clinical data is missing or unmeasured for predicate(s): {unknown_str}"
            ),
        )

    return NodeApplicabilityResult(
        node_id=node_id,
        status=ApplicabilityStatus.MET,
        requires_predicates=decl.requires_predicates,
        contraindicated_by=decl.contraindicated_by,
        predicate_evaluations=evaluations,
        reason="All required node predicates satisfied by patient",
    )
