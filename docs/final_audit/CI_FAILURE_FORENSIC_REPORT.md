# CI Failure Forensics and Remediation Report

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

---

## Section A: Executive Summary & Failure Identification

### 1. Incident Overview
* **Repository:** `https://github.com/AkkiSensei/TriageRAG`
* **Branch:** `main`
* **Triggering Commit under Audit:** `ea04325` (`docs(final-audit): record final implementation matrix and release-readiness report`)
* **Remediation Commit:** `e637102` (`fix(normalize): prevent POSIX filename-too-long error on raw YAML strings in yaml loader`)
* **Observed Remote CI Status at `ea04325`:**
  - `CI / quickstart-smoke` (`Job ID: 124844467819`): **FAILED** (Exit code 1)
  - `CI / verify-and-eval` (`Job ID: 124844467594`): **FAILED** (Exit code 1)
  - `CI / container-smoke` (`Job ID: 124844467871`): **PASSED** (Exit code 0)

### 2. Discrepancy Statement
Prior local validation was executed on Windows where `python tools/tasks.py verify` exited 0 (521 passed, 1 xfailed under HD-6, all evaluations 100% green, frontend lint/typecheck/36-tests/build clean). However, on remote GitHub Actions runners executing on `ubuntu-latest` (Linux kernel with POSIX syscall semantics), both `quickstart-smoke` and `verify-and-eval` failed with fatal exit code 1 during clinical data schema validation (`tools/validate_data.py`).

---

## Section B: Remote Log Evidence

Exact runner log output retrieved via GitHub Actions REST API for Run ID `41305339809`:

### 1. `CI / verify-and-eval` (Job ID: `124844467594`)
* **URL:** `https://github.com/AkkiSensei/TriageRAG/actions/runs/41305339809/job/124844467594`
* **Step:** `Run verification gate` (`python tools/tasks.py verify`)
* **Sub-step:** `validate_data()` -> `tools/validate_data.py`
* **Error Extract:**
```text
Validating clinical datasets in: /home/runner/work/TriageRAG/TriageRAG/data
  [OK] data/acronyms.yaml
  [OK] data/classes.yaml
  [OK] data/aliases.yaml (48 entries)
  [OK] data/formulary/ (8 drugs validated)
  [OK] data/rules/ (12 rules validated)
  [OK] data/rules_candidates/ (49 candidate rules validated)
  [OK] data/scoring/ tables validated

DATA VALIDATION FAILED WITH ERRORS:
  - envenomation_neurotoxic_escalation.md front-matter error: [Errno 36] File name too long: "\ndoc_id: ESCAL_SNAKEBITE\ntitle: 'Emergency Protocol: Refractory Envenomation & Coagulopathy Escalation (SYNTHETIC)'\nsection: Refractory Envenomation & Coagulopathy Escalation\npopulation: adult\nsyndrome: snakebite\nchunk_id: SNAKE_ESCAL_01\nsynthetic: true\nversion: 1.0.0\nlicense: synthetic\nattribution: TriageRAG Synthetic Research Corpus\nsource_url: null\nretrieved_at: null\nreviewed_by: null\nstatus: PLACEHOLDER_UNRETRIEVED\n"
  - major_inhalation_burns.md front-matter error: [Errno 36] File name too long: "\ndoc_id: ESCAL_BURNS\ntitle: 'Emergency Protocol: Burn Shock & Inhalation Trauma Escalation (SYNTHETIC)'\nsection: Burn Shock & Inhalation Trauma Escalation\npopulation: adult\nsyndrome: burns\nchunk_id: BURNS_ESCAL_01\nsynthetic: true\nversion: 1.0.0\nlicense: synthetic\nattribution: TriageRAG Synthetic Research Corpus\nsource_url: null\nretrieved_at: null\nreviewed_by: null\nstatus: PLACEHOLDER_UNRETRIEVED\n"
  [... 36 protocol front-matter errors identical in structure ...]
FAILED (code 1): /opt/hostedtoolcache/Python/3.11.17/x64/bin/python tools/validate_data.py
##[error]Process completed with exit code 1.
```

### 2. `CI / quickstart-smoke` (Job ID: `124844467819`)
* **URL:** `https://github.com/AkkiSensei/TriageRAG/actions/runs/41305339809/job/124844467819`
* **Step:** `Run README Quickstart verification` (`python tools/tasks.py verify`)
* **Error Extract:**
```text
Validating clinical datasets in: /home/runner/work/TriageRAG/TriageRAG/data
  [OK] data/acronyms.yaml
  [OK] data/classes.yaml
  [OK] data/aliases.yaml (48 entries)
  [OK] data/formulary/ (8 drugs validated)
  [OK] data/rules/ (12 rules validated)
  [OK] data/rules_candidates/ (49 candidate rules validated)
  [OK] data/scoring/ tables validated

DATA VALIDATION FAILED WITH ERRORS:
  - toxic_febrile_infant_evaluation.md front-matter error: [Errno 36] File name too long: "\ndoc_id: ESCAL_FEBRILE_INF\ntitle: 'Emergency Protocol: Toxic Febrile Infant & Invasive Bacterial Infection Escalation\n  (SYNTHETIC)'\n..."
FAILED (code 1): /opt/hostedtoolcache/Python/3.11.17/x64/bin/python tools/validate_data.py
##[error]Process completed with exit code 1.
```

---

## Section C: Root Cause Analysis

### 1. Underlying Defect Mechanism
In `src/triagerag/normalize/yaml_loader.py`, the function `load_yaml_decimal(source: str | Path)` was implemented as:
```python
def load_yaml_decimal(source: str | Path) -> Any:
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8") as f:
            return yaml.load(f, Loader=DecimalSafeLoader)
    path = Path(source)
    if path.exists() and path.is_file():
        with path.open("r", encoding="utf-8") as f:
            return yaml.load(f, Loader=DecimalSafeLoader)
    return yaml.load(source, Loader=DecimalSafeLoader)
```
When `source` is a raw YAML string passed directly (such as in `tools/validate_data.py` where Markdown frontmatter is extracted into string `fm_text`), `load_yaml_decimal` attempted to construct `Path(source)` and evaluate `path.exists()`.

### 2. OS-Specific Discrepancy (POSIX vs. Windows)
* **On Linux (POSIX, Ubuntu runner):**
  A string without path separators is interpreted as a filename in the current directory. POSIX file systems define `NAME_MAX = 255` bytes. When `stat()` is called on a 300+ character YAML snippet without directory delimiters, the Linux kernel syscall immediately returns `-1` with `errno = ENAMETOOLONG` (`[Errno 36] File name too long`).
  In Python 3.11, `pathlib.Path.exists()` only catches `(FileNotFoundError, NotADirectoryError)`; it does **not** suppress `OSError(36)`. Consequently, `path.exists()` raised an uncaught `OSError: [Errno 36] File name too long`.
* **On Windows (Local Environment):**
  Win32 path handling does not invoke POSIX `stat()` directly in the same manner. When passed multiline or long strings with certain characters, `Path.exists()` quietly returned `False`, falling through to `yaml.load(source, Loader=DecimalSafeLoader)`. As a result, local test suites on Windows never experienced the error.

### 3. Why `container-smoke` Passed
Job `container-smoke` does not execute `tools/tasks.py verify` or `tools/validate_data.py`. Instead, it boots the application container via Docker Compose and issues HTTP requests to `/health` and `/api/triage/explain`. In the runtime HTTP request flow, all YAML files (formulary drugs, scoring tables, rules) are referenced via explicit `Path` objects (`data_dir / "formulary" / ...`). These paths took the `isinstance(source, Path)` branch directly, entirely bypassing `Path(str).exists()`. Hence, container smoke tests succeeded cleanly.

---

## Section D: Code & Test Changes

### 1. Implementation Fix in `src/triagerag/normalize/yaml_loader.py`
We hardened `load_yaml_decimal` to recognize that:
1. Valid filesystem paths never contain newline characters (`\n` or `\r`).
2. Strings containing newlines or exceeding reasonable path lengths (`< 1024` chars) are raw YAML markup, not paths.
3. Any filesystem probing via `Path.is_file()` is safely guarded with `try...except (OSError, ValueError)`.

```diff
--- a/src/triagerag/normalize/yaml_loader.py
+++ b/src/triagerag/normalize/yaml_loader.py
@@ -42,10 +42,17 @@ def load_yaml_decimal(source: str | Path) -> Any:
     if isinstance(source, Path):
         with source.open("r", encoding="utf-8") as f:
             return yaml.load(f, Loader=DecimalSafeLoader)
-    # Check if string is an existing file path
-    path = Path(source)
-    if path.exists() and path.is_file():
-        with path.open("r", encoding="utf-8") as f:
-            return yaml.load(f, Loader=DecimalSafeLoader)
+    # Check if string is an existing file path.
+    # Note: If source contains newlines or carriage returns, it is raw YAML content, not a path.
+    # On POSIX platforms, attempting Path(source).exists() or is_file() on long or
+    # multiline strings raises OSError ([Errno 36] File name too long).
+    if "\n" not in source and "\r" not in source and len(source) < 1024:
+        try:
+            path = Path(source)
+            if path.is_file():
+                with path.open("r", encoding="utf-8") as f:
+                    return yaml.load(f, Loader=DecimalSafeLoader)
+        except (OSError, ValueError):
+            pass
     # Otherwise treat as raw YAML string
     return yaml.load(source, Loader=DecimalSafeLoader)
```

### 2. Regression Test Coverage in `tests/unit/test_contracts.py`
Three new dedicated regression tests were added to `TestDecimalYamlLoader`:
* `test_multiline_protocol_frontmatter_posix_filename_length_safety`: Explicitly feeds a 300+ character protocol frontmatter YAML containing `doc_id`, `title`, `synthetic`, and `Decimal` values to verify proper parsing without filesystem probing.
* `test_long_single_line_raw_yaml`: Tests single-line raw YAML string with a value exceeding 300 characters, asserting safe parsing without POSIX filename length crashes.
* `test_load_from_pathlib_and_str_path`: Confirms that both `Path` and `str` filepaths continue to resolve and load exact `Decimal` values accurately from disk.

---

## Section E: Remote GitHub Actions Verification

Remote GitHub Actions execution results for the remediation commit pushed to `main`:

* **Workflow Run ID:** `41306821220`
* **Workflow Run URL:** [https://github.com/AkkiSensei/TriageRAG/actions/runs/41306821220](https://github.com/AkkiSensei/TriageRAG/actions/runs/41306821220)
* **Triggering Commit:** `e637102`
* **Branch:** `main`
* **Overall Status:** `completed`
* **Overall Conclusion:** `success` (100% GREEN)

### Workflow Job Breakdown

| Job Name | Job ID | Status | Conclusion | Started At (UTC) | Completed At (UTC) | Duration |
|:---|:---|:---|:---|:---|:---|:---|
| `CI / quickstart-smoke` | `124848811518` | `completed` | **`success`** | `2026-11-01T12:30:32Z` | `2026-11-01T12:34:35Z` | 4m 3s |
| `CI / verify-and-eval` | `124848811663` | `completed` | **`success`** | `2026-11-01T12:30:32Z` | `2026-11-01T12:35:47Z` | 5m 15s |
| `CI / container-smoke` | `124848811810` | `completed` | **`success`** | `2026-11-01T12:30:32Z` | `2026-11-01T12:32:14Z` | 1m 42s |

### Verification Evidence Detail
1. **`quickstart-smoke`:** Verifies clean environment bootstrap, Python 3.11 set up, Node 20 / npm ci, dev/api dependencies install, and complete README quickstart verification (`python tools/tasks.py verify`) passing with 0 errors.
2. **`verify-and-eval`:** Executes full gating suite:
   - Ruff linting and format checking: 195 files clean.
   - Mypy strict type checking: 191 files clean.
   - Import-linter architecture isolation: Intact.
   - Clinical data schema validation: 65 protocols, 8 formulary drugs, 12 rules, 49 candidate rules, 50 vitals flags, 17 predicates, 42 decision nodes, 17 cues validated.
   - Rule coverage matrix: 12/12 active rules covered, 0.52 alerts/patient, 0% false alerts on negatives.
   - Pytest suites: 522 passed, 1 xfailed (HD-6 gross overdose unoverridable block).
   - Mandatory evals: Golden (86/86), Mechanics (41/41), Metamorphic (3/3), Adversarial injection (19/19), Retrieval benchmark (224 cases, syndrome recall 100%, 0 wrong protocols).
   - Frontend verification: ESLint clean, TypeScript clean, Vitest 36/36 passed, Vite production build clean.
   - Artifacts finalized and uploaded: `eval-reports.zip` (ID: 13083572695, SHA256: `884e178dc4ab7719ae6cb40daae0b5f17ede9788433382eda14f6411da8f1f7d`).
3. **`container-smoke`:** Multi-container docker stack bootstrap, `/health` endpoint 200 OK, `/api/triage/explain` structured response validated, clean container teardown.*

---

## Section F: System Integrity & Compliance Sign-off

1. **Safety Invariants Uncompromised:** No clinical rules, threshold values, dosage tripwires, early warning score boundaries, or fail-closed abstention rules were altered.
2. **HD Gate Preservation:** HD-6 strict xfail contract (`test_gross_overdose_blocks_unoverridable`) remains intact and verified.
3. **Reproducibility & Release Posture:** The fix eliminates an OS-level portability boundary defect between Windows and POSIX/Linux environments, ensuring deterministic, reproducible verification across all execution targets.

