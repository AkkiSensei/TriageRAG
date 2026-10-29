"""Fix-Gate G0 re-baseline recorder.

Safety Property (Fix Gate G0, Honesty rule):
Every number written by this tool is parsed from the output of a command that was actually
executed in the current checkout. If a command cannot be run (missing toolchain, no network),
the value is recorded as the string "NOT VERIFIED" together with the reason. Nothing is
estimated or carried over from prose.

Usage:
    python tools/fg0_baseline.py --out eval/reports/baseline_fg0.json [--skip-web]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
NOT_VERIFIED = "NOT VERIFIED"


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run a command and return (exit_code, combined_output)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    exe = shutil.which(cmd[0]) or cmd[0]
    try:
        proc = subprocess.run(
            [exe, *cmd[1:]],
            cwd=cwd or REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _search_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _pytest(py: str, junit_path: Path) -> dict[str, Any]:
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    code, out = _run(
        [py, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", f"--junitxml={junit_path}"]
    )
    result: dict[str, Any] = {"exit_code": code}
    if junit_path.exists():
        root = ET.parse(junit_path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is not None:
            total = int(suite.get("tests", "0"))
            failures = int(suite.get("failures", "0"))
            errors = int(suite.get("errors", "0"))
            skipped = int(suite.get("skipped", "0"))
            result.update(
                collected=total,
                passed=total - failures - errors - skipped,
                failed=failures,
                errors=errors,
                skipped=skipped,
            )
    else:
        result["collected"] = NOT_VERIFIED
        result["reason"] = out[-2000:]
    return result


def _collected_test_functions(py: str) -> set[str]:
    _, out = _run([py, "-m", "pytest", "tests", "--collect-only", "-q", "-p", "no:cacheprovider"])
    names: set[str] = set()
    for line in out.splitlines():
        if "::" in line:
            func = line.split("::")[-1]
            names.add(func.split("[")[0].strip())
    return names


def _eval_suite(py: str, script: str, pattern: str) -> dict[str, Any]:
    code, out = _run([py, script])
    match = re.search(pattern, out)
    if not match:
        return {
            "exit_code": code,
            "passed": NOT_VERIFIED,
            "total": NOT_VERIFIED,
            "reason": out[-1500:],
        }
    return {"exit_code": code, "passed": int(match.group(1)), "total": int(match.group(2))}


def _web(skip: bool) -> dict[str, Any]:
    if skip:
        return {"status": NOT_VERIFIED, "reason": "--skip-web passed"}
    web = REPO_ROOT / "web"
    if shutil.which("npm") is None:
        return {"status": NOT_VERIFIED, "reason": "npm not on PATH"}
    if not (web / "node_modules").exists():
        code, out = _run(["npm", "ci", "--no-audit", "--no-fund"], cwd=web)
        if code != 0:
            return {"status": NOT_VERIFIED, "reason": f"npm ci failed: {out[-800:]}"}
    result: dict[str, Any] = {}
    for step in ("lint", "typecheck", "test", "build"):
        code, out = _run(["npm", "run", step], cwd=web)
        result[f"{step}_exit_code"] = code
        if step == "test":
            result["vitest_passed"] = _search_int(r"Tests\s+(\d+) passed", out)
    result["status"] = (
        "PASS" if all(v == 0 for k, v in result.items() if k.endswith("_exit_code")) else "FAIL"
    )
    return result


def _report_discrepancies(report_md: Path, collected: set[str]) -> dict[str, Any]:
    """Compare a prose report against collected tests and committed JSON artefacts."""
    if not report_md.exists():
        return {"report": str(report_md.name), "present": False}
    text = report_md.read_text(encoding="utf-8")
    test_files = {p.stem for p in (REPO_ROOT / "tests").rglob("test_*.py")}
    cited = sorted(set(re.findall(r"\btest_[a-z0-9_]+\b", text)))
    cited_functions = [t for t in cited if t not in test_files]
    phantom = [t for t in cited_functions if t not in collected]

    numbers: list[dict[str, Any]] = []
    latency_path = REPO_ROOT / "eval" / "reports" / "latency_benchmark.json"
    if latency_path.exists():
        lat = json.loads(latency_path.read_text(encoding="utf-8"))
        for key, label in (("p50_latency_ms", "p50"), ("p95_latency_ms", "p95")):
            match = re.search(rf"`{label} = ([0-9.]+) ms`", text)
            if match:
                claimed = float(match.group(1))
                numbers.append(
                    {
                        "claim": f"10k-chunk {label}",
                        "report": claimed,
                        "artefact": lat[key],
                        "match": claimed == lat[key],
                    }
                )
    retrieval_path = REPO_ROOT / "eval" / "reports" / "retrieval.json"
    if retrieval_path.exists():
        ret = json.loads(retrieval_path.read_text(encoding="utf-8"))
        dev = ret.get("dev", {})
        row = re.search(r"\*\*Node-Level MRR\*\* \| `([0-9.]+)`", text)
        if row and "mrr" in dev:
            numbers.append(
                {
                    "claim": "dev MRR",
                    "report": float(row.group(1)),
                    "artefact": dev["mrr"],
                    "match": float(row.group(1)) == dev["mrr"],
                }
            )
        row = re.search(r"Expected Calibration Error \(ECE\)\*\* \| `([0-9.]+)`", text)
        if row and "ece" in dev:
            numbers.append(
                {
                    "claim": "dev ECE",
                    "report": float(row.group(1)),
                    "artefact": dev["ece"],
                    "match": float(row.group(1)) == dev["ece"],
                }
            )
    return {
        "report": report_md.name,
        "present": True,
        "cited_test_functions": len(cited_functions),
        "phantom_test_functions": phantom,
        "number_checks": numbers,
        "number_mismatches": sum(1 for n in numbers if not n["match"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="eval/reports/baseline_fg0.json")
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--report", default="Postmortem-Response.MD")
    args = parser.parse_args()

    py = sys.executable
    _, head = _run(["git", "rev-parse", "HEAD"])
    junit = REPO_ROOT / "var" / "junit_fg0.xml"

    code, ruff_out = _run([py, "-m", "ruff", "check", "src", "tests", "tools", "eval"])
    fcode, fmt_out = _run([py, "-m", "ruff", "format", "--check", "src", "tests", "tools", "eval"])
    mcode, mypy_out = _run([py, "-m", "mypy", "src", "tests", "tools", "eval"])
    icode, imp_out = _run([py, "-m", "importlinter.cli"])

    baseline: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": head.strip(),
        "python": sys.version.split()[0],
        "ruff_check": {"exit_code": code, "clean": "All checks passed" in ruff_out},
        "ruff_format": {
            "exit_code": fcode,
            "files": _search_int(r"(\d+) files? already formatted", fmt_out),
        },
        "mypy": {
            "exit_code": mcode,
            "source_files": _search_int(r"in (\d+) source files?", mypy_out),
            "errors": 0 if mcode == 0 else _search_int(r"Found (\d+) errors?", mypy_out),
        },
        "import_linter": {
            "exit_code": icode,
            "kept": _search_int(r"(\d+)\s+(?:contracts?\s+)?kept", imp_out),
            "broken": _search_int(r"(\d+)\s+(?:contracts?\s+)?broken", imp_out),
        },
        "pytest": _pytest(py, junit),
        "golden": _eval_suite(py, "eval/run_golden.py", r"Results: (\d+)/(\d+) passed"),
        "mechanics": _eval_suite(py, "eval/run_mechanics.py", r"Results: (\d+)/(\d+) passed"),
        "metamorphic": _eval_suite(py, "eval/run_metamorphic.py", r"Results: (\d+)/(\d+) passed"),
        "adversarial": _eval_suite(py, "eval/run_adversarial.py", r"Results: (\d+)/(\d+) passed"),
    }
    mcode2, _ = _run([py, "eval/run_mutation.py"])
    mut_path = REPO_ROOT / "eval" / "reports" / "mutation.json"
    if mut_path.exists():
        mut = json.loads(mut_path.read_text(encoding="utf-8"))
        baseline["mutation"] = {
            "exit_code": mcode2,
            "killed": mut["overall_mutants_killed"],
            "total": mut["overall_mutants_total"],
            "rule": f"{mut['rule_mutants_killed']}/{mut['rule_mutants_total']}",
            "code": f"{mut['code_mutants_killed']}/{mut['code_mutants_total']}",
        }
    else:
        baseline["mutation"] = {"status": NOT_VERIFIED, "exit_code": mcode2}
    baseline["web"] = _web(args.skip_web)
    baseline["report_discrepancies"] = _report_discrepancies(
        REPO_ROOT / args.report, _collected_test_functions(py)
    )

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(baseline, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
