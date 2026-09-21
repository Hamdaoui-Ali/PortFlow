# PF-108 Databricks Cloud Comparison Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a credential-free local comparator that validates an operator-supplied Databricks Gold export against the trusted PF-107 expected result.

**Architecture:** Keep the implementation in labs/portflow_databricks/. Reuse PF-107's verified handoff and PF-106's canonical KPI normalizer, guard all PF-108 paths below .databricks/pf108/, and write a deterministic comparison report that records hashes rather than cloud claims. The CLI performs no network, credential, SDK, notebook, or workspace operation.

**Tech Stack:** Python 3.12, pytest, Ruff, mypy, jsonschema, existing PF-106 canonicalization, existing PF-107 artifact/path/manifest helpers.

**Spec:** docs/superpowers/specs/2026-09-21-portflow-pf-108-cloud-comparison-design.md

## Global Constraints

- Keep all PF-108 code in labs/portflow_databricks/; do not add cloud clients, credentials, environment-variable inspection, or workspace API calls.
- Accept only a JSON list of overview_kpis rows using the existing PF-106 RESULT_FIELDS and canonicalization rules.
- Require cloud input and report output to remain below .databricks/pf108/; reject POSIX/Windows absolute paths, traversal, backslashes, links, junctions, and reparse points.
- Reuse PF-107 verify_bundle before trusting the local expected result.
- Use execution_mode: "manual_result_comparison" and cloud_execution: "result_supplied"; do not claim a cloud run.
- Failure output contains only the bounded reason codes in the spec; no raw paths, secrets, subprocess text, or exception text may be emitted or serialized.
- Keep web/public/data, public manifest bytes, PF-107 artifacts, default Compose services, and all existing product behavior unchanged.

## Review Focus

- Cross-platform traversal or reparse paths fail with artifact_path_invalid; pin in tests/unit/test_databricks_comparison_paths.py.
- Malformed, wrapped, extra-field, duplicate-terminal, invalid-timestamp, and non-finite rows fail with cloud_result_invalid; pin in tests/unit/test_databricks_comparison.py.
- A valid semantic mismatch produces a deterministic mismatch report and CLI exit code 1; pin in tests/integration/test_databricks_comparison.py and tests/unit/test_databricks_cli.py.
- Tampered PF-107 handoff, cloud input, and comparison report fail with bounded reasons; pin in tests/integration/test_databricks_comparison.py.
- Hostile exception descriptors and engine failures cannot leak paths or secrets; pin in tests/unit/test_databricks_cli.py.

---

## File Map

| File | Responsibility |
| --- | --- |
| labs/portflow_databricks/comparison.py | PF-108 report schema, safe result loading, canonical comparison, report writing, and report verification. |
| labs/portflow_databricks/paths.py | Existing PF-107 path guard plus the PF-108 default root helper. |
| labs/portflow_databricks/cli.py | Bounded compare command and safe mismatch/failure output. |
| tests/unit/test_databricks_comparison_paths.py | PF-108 root and path containment. |
| tests/unit/test_databricks_comparison.py | Row parsing, schema, deterministic report, mismatch, and tamper-unit tests. |
| tests/unit/test_databricks_cli.py | CLI help, defaults, exit codes, and output-boundary tests. |
| tests/integration/test_databricks_comparison.py | PF-107/PF-108 bundle integration, repeatability, tamper, and public-data isolation. |
| tests/unit/test_databricks_docs.py | Runbook, README, changelog, backlog, and ignored-artifact contract. |
| docs/runbooks/databricks-free-edition.md | Manual export placement, compare command, report interpretation, and cleanup. |
| README.md, CHANGELOG.md, docs/product/BACKLOG.md | Navigation, release note, and PF-108 status. |

---

### Task 1: Add the PF-108 safe root and report schema

**Files:**
- Modify: labs/portflow_databricks/paths.py
- Create: labs/portflow_databricks/comparison.py
- Create: tests/unit/test_databricks_comparison_paths.py
- Create: tests/unit/test_databricks_comparison.py

**Interfaces:**
- Consume the existing PF-107 reparse-point and cross-platform path helpers.
- Produce DEFAULT_COMPARISON_ROOT, resolve_comparison_root, resolve_comparison_path, ComparisonVerificationError(reason_code), ComparisonSpec, build_comparison_report, build_mismatch_report, and write_comparison_report. The report reference includes a safe PF-107-relative manifest_path so later verification can reopen the exact handoff.

- [ ] Step 1: Write failing path and schema tests.

~~~
def test_comparison_root_is_below_databricks_root(tmp_path: Path) -> None:
    root = resolve_comparison_root(repository_root=tmp_path)
    assert root == (tmp_path / ".databricks" / "pf108").resolve()


@pytest.mark.parametrize(
    "value", ["../escape.json", r"..\escape.json", "/tmp/result.json", r"C:\tmp\result.json"]
)
def test_comparison_paths_reject_cross_platform_escape(tmp_path: Path, value: str) -> None:
    root = resolve_comparison_root(repository_root=tmp_path)
    with pytest.raises(ArtifactPathError, match="artifact path"):
        resolve_comparison_path(root, value)
~~~

Also test that a match report has exact PF-108, manual_result_comparison,
result_supplied, reference/cloud hash fields, and comparison:
{status: "match", reason_code: null, verifier_version: "1"}.

- [ ] Step 2: Run focused tests and verify the expected red failure.

Run:

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q tests/unit/test_databricks_comparison_paths.py tests/unit/test_databricks_comparison.py
~~~

Expected: FAIL because the PF-108 path and report interfaces do not exist.

- [ ] Step 3: Implement the root/path and JSON-schema boundary.

Add DEFAULT_COMPARISON_ROOT = Path(".databricks") / "pf108". Reuse the
existing _reject_reparse_components and relative-path validation. Define an
exact schema with the fields schema_version, task, target, execution_mode,
cloud_execution, reference, cloud_result, and comparison. Require the
reference task to be PF-107, lower-case 64-character hashes, non-negative row
counts, a safe relative cloud_result.path, and comparison status match or
mismatch. Reject extra fields, unsafe paths, unsafe reasons, or wrong execution
markers with only comparison_invalid or artifact_path_invalid. Serialize
sorted, indented JSON with exactly one terminating LF.

- [ ] Step 4: Run focused tests and verify green.

Run the command from Step 2. Expected: all path and schema tests pass.

- [ ] Step 5: Commit the boundary slice.

~~~
git add labs/portflow_databricks/paths.py labs/portflow_databricks/comparison.py tests/unit/test_databricks_comparison_paths.py tests/unit/test_databricks_comparison.py
git commit -m "feat: add PF-108 comparison artifact boundary"
~~~

### Task 2: Add strict cloud-result canonicalization and comparison

**Files:**
- Modify: labs/portflow_databricks/comparison.py
- Modify: tests/unit/test_databricks_comparison.py

**Interfaces:**
- Consume RESULT_FIELDS, canonicalize_rows, and result_sha256 from PF-106.
- Consume PF-107 verify_bundle and manifest fields.
- Produce load_result_rows and compare_result(ComparisonSpec).

- [ ] Step 1: Write failing canonicalization and comparison tests.

Use a valid PF-107 expected-result row as the fixture. Test that
load_result_rows decodes its two trailing-Z timestamps and returns the same
canonical hash. Parameterize invalid input for a wrapper object, an extra
field, a duplicate terminal, a naive timestamp, and a non-finite metric; every
case must raise exactly ComparisonVerificationError("cloud_result_invalid").
Test that different canonical hashes build a mismatch report with status
"mismatch" and reason_code "result_hash_mismatch".

- [ ] Step 2: Run the new tests and verify the expected red failure.

Run:

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q tests/unit/test_databricks_comparison.py
~~~

Expected: FAIL because result loading and orchestration are not implemented.

- [ ] Step 3: Implement strict JSON loading and canonical comparison.

Read only a JSON list. Convert source_period_start and source_period_end
strings ending in Z to aware UTC datetime values, then call PF-106
canonicalize_rows. Convert every JSON decode, file, type, numeric, timestamp,
duplicate, and canonicalization failure to
ComparisonVerificationError("cloud_result_invalid") without retaining the
underlying text.

compare_result must resolve PF-108 paths, call PF-107 verify_bundle, read the
verified PF-107 result metadata, load and hash the cloud rows, build match when
row count and canonical hash equal, otherwise build mismatch, write the sorted
report, call verify_comparison, and return the report. Do not import a cloud
client, HTTP library, subprocess, or credential library, and do not inspect
os.environ.

- [ ] Step 4: Run focused comparison tests and verify green.

Run the command from Step 2. Expected: all valid, invalid, match, and mismatch
tests pass.

- [ ] Step 5: Commit the canonical comparison slice.

~~~
git add labs/portflow_databricks/comparison.py tests/unit/test_databricks_comparison.py
git commit -m "feat: compare PF-107 and supplied cloud results"
~~~

### Task 3: Add report verification and bounded CLI behavior

**Files:**
- Modify: labs/portflow_databricks/comparison.py
- Modify: labs/portflow_databricks/cli.py
- Modify: tests/unit/test_databricks_cli.py
- Create: tests/integration/test_databricks_comparison.py

**Interfaces:**
- Consume compare_result, verify_comparison, and the PF-108 safe reason set.
- Produce the compare subcommand with default paths and shell-friendly exit codes.

- [ ] Step 1: Write failing CLI and integration tests.

Test main(["compare"]) with monkeypatched compare_result for exact match output
and test a mismatch report for exact non-zero output. Add integration coverage
that generates PF-107, copies its expected result to the PF-108 cloud result
path, compares twice, asserts byte-identical reports, then exercises a tampered
cloud file, tampered PF-107 handoff, tampered report, and unchanged
web/public/data bytes.

- [ ] Step 2: Run the new tests and verify the expected red failure.

Run:

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q tests/unit/test_databricks_cli.py tests/integration/test_databricks_comparison.py
~~~

Expected: FAIL because the CLI has no compare command and report verification is
incomplete.

- [ ] Step 3: Implement verify_comparison.

Guard the report below .databricks/pf108/, validate its exact schema, resolve
the recorded PF-107-relative reference manifest below .databricks/pf107/, guard
the declared cloud-result relative path, verify its exact file SHA-256, reload
and canonicalize the rows, and check the recorded cloud hash and row count.
Re-run PF-107 verify_bundle and compare its manifest/result metadata with the
report. Map report schema/reference disagreement to comparison_invalid,
changed cloud bytes to cloud_result_hash_mismatch, and an invalid PF-107 handoff
to handoff_invalid.

- [ ] Step 4: Implement the compare CLI command.

Add these parser arguments:

~~~
compare = commands.add_parser("compare", help="compare a supplied Gold result with PF-107")
compare.add_argument("--handoff-manifest", type=Path, default=Path(".databricks/pf107/manifest.json"))
compare.add_argument("--cloud-result", type=Path, default=Path(".databricks/pf108/cloud-result.json"))
compare.add_argument("--output", type=Path, default=Path(".databricks/pf108/comparison.json"))
~~~

Print exactly one bounded line:
databricks comparison matched,
databricks comparison mismatch: result_hash_mismatch, or
databricks comparison failed: <safe-reason-code>. Hostile exception
attributes and engine failures must not leak their messages.

- [ ] Step 5: Run CLI/integration tests and verify green.

Run the command from Step 2. Expected: all new CLI and integration tests pass.

- [ ] Step 6: Commit the CLI and verification slice.

~~~
git add labs/portflow_databricks/comparison.py labs/portflow_databricks/cli.py tests/unit/test_databricks_cli.py tests/integration/test_databricks_comparison.py
git commit -m "feat: add PF-108 comparison CLI and verification"
~~~

### Task 4: Document and close the repository-side PF-108 contract

**Files:**
- Modify: docs/runbooks/databricks-free-edition.md
- Modify: README.md
- Modify: CHANGELOG.md
- Modify: docs/product/BACKLOG.md
- Modify: tests/unit/test_databricks_docs.py

- [ ] Step 1: Write failing documentation assertions.

Assert the runbook contains PF-108, cloud-result.json,
python -m labs.portflow_databricks compare, result_hash_mismatch,
does not execute, and Remove-Item .databricks -Recurse -Force.

- [ ] Step 2: Run the documentation test and verify the expected red failure.

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q tests/unit/test_databricks_docs.py
~~~

Expected: FAIL because PF-108 documentation is not present.

- [ ] Step 3: Document manual result placement and report interpretation.

Explain that an operator may export only the Gold row list, place it at
.databricks/pf108/cloud-result.json, and run compare. Explain that match means
canonical equality with PF-107, mismatch is non-zero and needs investigation,
and cloud_execution: result_supplied is not proof of automatic execution. Keep
cleanup scoped to disposable .databricks/ artifacts and workspace resources;
never copy anything to web/public/data.

Update README navigation, add a dated changelog entry, and change the backlog
current action to record the repository-side PF-108 comparison contract as
complete while explicitly noting that no real Databricks workspace run was
performed. Preserve the repository-hardening follow-up note.

- [ ] Step 4: Run documentation tests and verify green.

Run the command from Step 2. Expected: documentation and ignore-contract
assertions pass.

- [ ] Step 5: Commit the documentation slice.

~~~
git add docs/runbooks/databricks-free-edition.md README.md CHANGELOG.md docs/product/BACKLOG.md tests/unit/test_databricks_docs.py
git commit -m "docs: record PF-108 comparison handoff"
~~~

### Task 5: Run the full quality gates and review the branch

- [ ] Step 1: Run focused PF-108 tests.

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q tests/unit/test_databricks_comparison_paths.py tests/unit/test_databricks_comparison.py tests/unit/test_databricks_cli.py tests/unit/test_databricks_docs.py tests/integration/test_databricks_comparison.py
~~~

Expected: all focused tests pass.

- [ ] Step 2: Run repository tests and static checks.

~~~
$env:PYTHONPATH = (Resolve-Path "src").Path
$env:Path = "C:\Users\aliha\AppData\Local\Programs\Python\Python312\Scripts;" + $env:Path
& "C:\Users\aliha\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q
ruff check .
ruff format --check .
mypy src
~~~

Expected: the full suite passes with only environment-declared skips, Ruff and
formatting pass, and mypy reports no errors.

- [ ] Step 3: Verify public-data and repository safety boundaries.

~~~
git diff -- web/public/data
git diff --check
git status --short
rg -n "requests|urllib|httpx|databricks|DATABRICKS_|os\\.environ" labs/portflow_databricks tests/unit tests/integration
~~~

Expected: the public-data diff is empty, no tracked generated .databricks/
files appear, and no cloud client or credential inspection is introduced.

- [ ] Step 4: Perform the whole-branch review.

Check every diff against the PF-108 spec, especially path containment, report
schema, mismatch semantics, error-code allowlisting, and the distinction
between a supplied result and cloud execution. Fix any issue, rerun affected
tests, and commit a focused follow-up.

- [ ] Step 5: Confirm a clean handoff.

~~~
git status --short
git log --oneline --decorate -12
~~~

Expected: the branch is clean, all required commits are present, and the final
handoff cites exact verification output without claiming a cloud run.
