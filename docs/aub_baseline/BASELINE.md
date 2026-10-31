# AUB Phase 0 — Baseline (recorded before any Phase 0 implementation)

> Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

Controlling spec: `AUB.md` (repo root). Ledger: `docs/AUB_STATUS.md`.

## Environment

| Item | Value |
|---|---|
| Repo HEAD (starting) | `3e8a45bded1a9bd39e5e644a0957c62bb0fb8315` (`main`, = `origin/main`) |
| Working branch | `aub/phase-0-rebaseline` |
| OS | Windows (PowerShell) |
| Python | 3.13.7 (project `requires-python` >= 3.11) |
| Node / npm | v25.9.0 / 11.12.1 |
| Key deps | pydantic 2.14.1, rank-bm25 0.2.2, RapidFuzz 3.14.6, fastapi 0.162.0, pytest 9.1.1, ruff 0.17.2, mypy 2.4.0, import-linter 2.15, hypothesis 6.170.11 |
| Full lists | `pip_freeze.txt`, `npm_ls.txt` |
| Pre-existing untracked | `AUB.md` only (backed up to `var/backup_pre_phase0/`, git-ignored) |
| Network | not used |

## Results REPRODUCED on HEAD in this session

| Check | Result | Evidence file |
|---|---|---|
| `pytest tests` (original repo, with `.git`) | **237 passed, 1 xfailed, 0 failed** | `pytest_head.txt` |
| `python tools/tasks.py verify` (scratch copy of HEAD) | **FAILED at mypy**: 3 errors in `tests/unit/test_explainability_and_intake_hardening.py` (non-existent `StepStatus` members). Introduced by the previous session, which only ran `mypy src`. Gate never reached the eval stage. | `verify_head.txt` |
| `tests/unit/test_fg4_eval_and_calibration.py` in a `.git`-less copy | **1 failed, 5 passed** (`test_dataset_matches_frozen_commit`: `git cat-file` → "not a git repository") | `nogit_dataset_test.txt` |
| `eval/run_golden.py` | 65/65 | `eval_golden.txt` |
| `eval/run_mechanics.py` | 41/41 | `eval_mechanics.txt` |
| `eval/run_metamorphic.py` | 3/3 | `eval_metamorphic.txt` |
| `eval/run_adversarial.py` | 19/19 | `eval_adversarial.txt` |
| `eval/run_retrieval.py` | Test split: syndrome-provided Recall@5 100 %; vitals-only Recall@1 0 %; wrong-protocol 0.0; hard-negative abstain recall 1.0; abstain accuracy 82.95 %; ECE 0.1453 (observational) | `eval_retrieval.txt` |
| Tracked files dirtied by an ordinary eval run | `eval/reports/retrieval.json`, `eval/reports/retrieval_calibration.md` (latency/timing fields only; metric values reproduced bit-for-bit) | `eval_dirtied_tracked_files.txt` |
| Frontend `tools/tasks.py web-verify` | green (lint, typecheck, vitest 8/8, build) | `web_verify_head.txt` |

All eval runs above were executed in a throw-away copy of the repository
(`%TEMP%\triage_base_git`) so that tracked `eval/reports/*` in the real repo were
not touched.

## Hashes

| Item | Value |
|---|---|
| `eval/retrieval/dataset.yaml` SHA-256 (working-tree bytes, CRLF as checked out here) | `7a80ecd7fc3847f2380ac898c10eb5615f0a2a151dbf75d06beadb696b2ddce1` |
| `dataset.yaml` git blob | `ed3e72c2ef2416207dd6a96dd7f2c93495674aa9` |
| Corpus hash (from `eval/reports/retrieval.json`, reproduced) | `591c6cd10f3067be58abf29ecbda0d5dd2b46eee6d09d99e36057de25aed763b` |
| Retrieval config hash (reproduced) | `ffb6892cc1524c60cb9b354c2718da1f4ea504be36376fcb57fea32de6c5f44b` |
| Index / dataset version | 2.0.0 / 2.0.0 |
| Dataset size | 224 cases (136 dev / 88 test) |
| Retrieval config | `data/retrieval/config.yaml`: top_k 5, calibrated_threshold 0.15, syndrome_inferred_threshold 0.35, min_syndrome_margin 0.25, bm25 k1 1.5 / b 0.75, calibration_run `CALIB_FG4_DEV_SWEEP_V1` |

Note: the dataset file in the working tree has CRLF line endings although
`.gitattributes` requests LF. The T0.1 lock therefore hashes LF-normalised bytes.

## Read from HISTORICAL reports (not re-run here)

* `eval/reports/mutation.json` (52/52 mutants) — **not re-run** (long-running; not
  needed for Phase 0 acceptance). Counts quoted in docs are therefore only as valid
  as that artifact.
* `eval/reports/latency_benchmark.json` (10 000-chunk benchmark) — **not re-run**.
* `eval/reports/retrieval_ablation.json/.md`, `ablation.*` — **not re-run** in
  baseline (the ablation runner overwrites tracked reports; see T0.8).

## Environmental limitations

* `tools/tasks.py verify` could not complete on HEAD (see above), so the
  post-mypy stages (pytest-in-verify, eval scripts, web) were run individually.
* Python 3.13 / Node 25 are newer than a typical CI matrix; results are not claimed for other versions.
