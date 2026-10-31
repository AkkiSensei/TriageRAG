"""Annotation tooling and inter-rater agreement computation for TriageRAG (AUB-EVL-01, T4.2).

Disclaimer:
    Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

Safety Properties (AUB-EVL-01, Rules R1, R3, R10, R12):
1. Blinded export removes all system scores, rankings, expected syndromes, and agent labels.
2. Analytic Cohen's kappa computation with deterministic tie-breaking and edge-case handling.
3. Explicit human dependency enforcement: unreviewed status is reported honestly;
   fabricated inter-rater agreement is strictly forbidden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from triagerag.config import get_repo_root

app = typer.Typer(help="TriageRAG Annotation and Inter-Rater Agreement Tooling")


def compute_cohens_kappa(
    rater_a: list[int],
    rater_b: list[int],
    categories: list[int] | None = None,
) -> dict[str, Any]:
    """Calculate Cohen's Kappa for two raters with categorical ratings.

    Args:
        rater_a: List of integer ratings from Rater A.
        rater_b: List of integer ratings from Rater B.
        categories: Explicit category labels (defaults to sorted union of ratings).

    Returns:
        dict containing observed_agreement, expected_agreement, cohens_kappa,
        sample_size, and the confusion matrix.
    """
    if len(rater_a) != len(rater_b):
        msg = f"Rater lists must match: len(a)={len(rater_a)} != len(b)={len(rater_b)}"
        raise ValueError(msg)
    n = len(rater_a)
    if n == 0:
        return {
            "sample_size": 0,
            "observed_agreement": 0.0,
            "expected_agreement": 0.0,
            "cohens_kappa": 0.0,
            "confusion_matrix": {},
        }

    cats = sorted(set(rater_a) | set(rater_b) if categories is None else set(categories))
    cat_to_idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)

    # Build confusion matrix
    cm = [[0 for _ in range(k)] for _ in range(k)]
    for a, b in zip(rater_a, rater_b, strict=True):
        if a not in cat_to_idx or b not in cat_to_idx:
            raise ValueError(f"Rating ({a}, {b}) contains unrecognised category outside {cats}")
        cm[cat_to_idx[a]][cat_to_idx[b]] += 1

    # Observed agreement
    agreed_count = sum(cm[i][i] for i in range(k))
    p_o = agreed_count / n

    # Expected agreement by chance
    p_e = 0.0
    for i in range(k):
        row_sum = sum(cm[i][j] for j in range(k))
        col_sum = sum(cm[j][i] for j in range(k))
        p_e += (row_sum / n) * (col_sum / n)

    # Cohen's Kappa
    if abs(1.0 - p_e) < 1e-12:
        kappa = 1.0 if abs(p_o - 1.0) < 1e-12 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    # Formatted confusion matrix
    formatted_cm: dict[str, dict[str, int]] = {}
    for i, cat_i in enumerate(cats):
        row_label = f"RaterA_{cat_i}"
        formatted_cm[row_label] = {}
        for j, cat_j in enumerate(cats):
            col_label = f"RaterB_{cat_j}"
            formatted_cm[row_label][col_label] = cm[i][j]

    return {
        "sample_size": n,
        "categories": cats,
        "observed_agreement": round(p_o, 6),
        "expected_agreement": round(p_e, 6),
        "cohens_kappa": round(kappa, 6),
        "confusion_matrix": formatted_cm,
    }


def export_blinded_cases(
    dataset_path: Path,
    out_path: Path,
    sample_size: int = 100,
) -> int:
    """Export a blinded sample of cases for clinical annotation."""
    raw = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = raw.get("cases", [])

    if sample_size > len(cases):
        sample_size = len(cases)

    # Stratified deterministic sampling across families
    by_family: dict[str, list[dict[str, Any]]] = {}
    for c in cases:
        by_family.setdefault(c.get("family", "unknown"), []).append(c)

    sampled: list[dict[str, Any]] = []
    # Collect items deterministically in round-robin fashion across families
    sorted_fams = sorted(by_family.keys())
    idx = 0
    while len(sampled) < sample_size:
        added_in_round = False
        for fam in sorted_fams:
            fam_cases = by_family[fam]
            if idx < len(fam_cases):
                sampled.append(fam_cases[idx])
                added_in_round = True
                if len(sampled) >= sample_size:
                    break
        if not added_in_round:
            break
        idx += 1

    # Blind each case
    instr = "Assign grade: 2 = directly actionable, 1 = supporting, 0 = irrelevant/non-indicated"
    blinded_cases = []
    for c in sampled:
        candidate_nodes = sorted(list((c.get("relevance_grades") or {}).keys()))
        blinded_case = {
            "case_id": c["id"],
            "age": c.get("age", {}),
            "population": c.get("population", ""),
            "vitals": c.get("vitals", {}),
            "notes": c.get("notes", ""),
            "candidate_nodes_to_grade": candidate_nodes,
            "annotation_instructions": instr,
            "ratings_placeholder": {node_id: None for node_id in candidate_nodes},
        }
        blinded_cases.append(blinded_case)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "disclaimer": "Research prototype. Synthetic data only. Not a medical device.",
        "schema_version": "1.0.0",
        "sample_size": len(blinded_cases),
        "source_dataset_version": raw.get("dataset_version", "unknown"),
        "blinded_cases": blinded_cases,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(blinded_cases)


def write_agreement_status(out_path: Path) -> None:
    """Document the honest, unreviewed status of human agreement (AUB-EVL-01, T4.2)."""
    payload = {
        "disclaimer": "Research prototype. Synthetic data only. Not a medical device.",
        "provenance_status": "AGENT_AUTHORED_UNREVIEWED",
        "agreement_state": "BLOCKED_PENDING_INDEPENDENT_HUMAN_ANNOTATION",
        "human_agreement_measured": False,
        "cohens_kappa": None,
        "sample_size": 100,
        "blocking_dependency": (
            "Independent double-annotation by two licensed clinicians (or one clinician + "
            "independent secondary rubric) required on eval/annotations/blinded_cases.json. "
            "Per Rule R3 and AUB-EVL-01, synthetic or fabricated agreement metrics are forbidden."
        ),
        "annotation_guide_ref": "docs/evaluation/ANNOTATION_GUIDE.md",
        "submission_schema_ref": "eval/annotations/schema.json",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@app.command()
def export(
    sample_size: Annotated[
        int, typer.Option("--sample-size", help="Number of cases to sample for annotation")
    ] = 100,
) -> None:
    """Export blinded evaluation cases for clinical double-annotation."""
    repo_root = get_repo_root()
    dataset_path = repo_root / "eval" / "retrieval" / "dataset.yaml"
    out_path = repo_root / "eval" / "annotations" / "blinded_cases.json"
    status_path = repo_root / "eval" / "annotations" / "agreement_status.json"

    count = export_blinded_cases(dataset_path, out_path, sample_size=sample_size)
    write_agreement_status(status_path)
    typer.echo(f"Exported {count} blinded cases -> {out_path}")
    typer.echo(f"Updated agreement status -> {status_path}")


@app.command()
def agreement(
    file_a: Annotated[Path, typer.Option("--file-a", help="Path to first submission JSON")],
    file_b: Annotated[Path, typer.Option("--file-b", help="Path to second submission JSON")],
) -> None:
    """Calculate Cohen's kappa inter-annotator agreement between two submission files."""
    data_a = json.loads(file_a.read_text(encoding="utf-8"))
    data_b = json.loads(file_b.read_text(encoding="utf-8"))

    ratings_a: dict[tuple[str, str], int] = {}
    for c in data_a.get("cases", []):
        cid = c["case_id"]
        for nid, g in c.get("ratings", {}).items():
            if g is not None:
                ratings_a[(cid, nid)] = int(g)

    ratings_b: dict[tuple[str, str], int] = {}
    for c in data_b.get("cases", []):
        cid = c["case_id"]
        for nid, g in c.get("ratings", {}).items():
            if g is not None:
                ratings_b[(cid, nid)] = int(g)

    common_keys = sorted(set(ratings_a.keys()) & set(ratings_b.keys()))
    if not common_keys:
        typer.echo("Error: No overlapping (case_id, node_id) ratings found between submissions.")
        raise typer.Exit(code=1)

    r_a = [ratings_a[k] for k in common_keys]
    r_b = [ratings_b[k] for k in common_keys]

    result = compute_cohens_kappa(r_a, r_b, categories=[0, 1, 2])
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()


if __name__ == "__main__":
    app()
