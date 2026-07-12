# Goal Lifecycle Harness Usage

## Purpose

Use this harness to rebuild a derived Goal STATE from registered Goal Contract files.

The source of truth remains:

```text
goals/<status>/<goal-id>/
  CONTRACT.md
  PLAN.md
  EVIDENCE.md

# or a standard single-file Goal Contract
goals/<status>/<subject>-goal-contract.md
```

`outputs/STATE.json` and `outputs/STATE.md` are generated dashboards only.

## Normal Operator Flow

1. Edit Goal Contract, Plan, and Evidence files directly.
2. Keep machine-readable status values in lowercase snake_case.
3. Put adjustable priority and hard dependencies in Contract `scheduling` metadata.
4. Register only intentional goal roots in `registry/REGISTRY.json`.
5. For local-only diagnostics, run reconcile and schema validation.
6. For a Dashboard/global refresh, run the deterministic orchestrator with `--global-registry --require-global`.
7. Treat STATE issues as review prompts, not automatic source-file changes.

PowerShell:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry\REGISTRY.json --out outputs
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry\REGISTRY.json --state outputs\STATE.json
```

Global refresh, with one bounded command that chains local reconcile, local validation,
global aggregation, global validation, operation-ID matching, timestamp ordering, and
canonical Goal-key visibility:

```powershell
\.\.venv\Scripts\python -m goal_lifecycle.run `
  --registry registry\REGISTRY.json `
  --out outputs `
  --global-registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --global-out outputs\global `
  --require-global `
  --json
```

Run tests before committing harness changes:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pytest
```

## Deterministic Goal Artifact Tool

`goal_lifecycle.artifact_tool` materializes an already-decided Goal layout; it
does not classify work, infer scope, or grant write permission. It defaults to
a no-write preview and reports only target paths, actions, and SHA-256 hashes.

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.artifact_tool `
  --repo-root <absolute-repository-root> `
  --artifact-root <repository-contained-output-root> `
  --decision <artifact-decision.json>
```

After the preview has been reviewed and the user has explicitly authorized the
exact target root, add `--apply`. Add `--audit` only when a local, hash-only
SQLite receipt is required. It is stored at
`<repo>/.goal-lifecycle/artifact-audit.sqlite`, never under `goals/`, and is
ignored by Git. Receipts contain only receipt/Goal IDs, operation status,
timestamps, file counts, error class, repo-relative paths, actions, and SHA-256
values — never generated Goal content. The command reports the audit database as
a repo-relative path, rejects paths outside the repository root, incompatible
size/layout decisions, and existing artifact targets. Do not invoke it from the
global Skill until the separate integration proposal and review gate have passed.

If an apply created valid files but the final SQLite update was interrupted,
first inspect the pending receipt, then explicitly finalize it with a hash-only
result payload after independently confirming those files are the intended
artifacts:

```powershell
python -m goal_lifecycle.artifact_audit --repo-root <repo> --list-receipts --goal-id <goal-id>
python -m goal_lifecycle.artifact_audit --repo-root <repo> --finalize-pending <receipt-id> --result <hash-only-result.json>
```

Finalization rereads every listed artifact and refuses to close the receipt if
any SHA-256 value differs. It never deletes files or repairs a receipt
automatically.

An audit receipt is first stored as `pending`, then finalized as `applied` or
`failed`. A pending receipt means the artifact may exist but its audit
finalization was interrupted; inspect it before retrying. Legacy JSONL receipts
are imported only by an explicit command and are never deleted automatically:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.artifact_audit `
  --repo-root <absolute-repository-root> `
  --import-legacy <legacy-receipts.jsonl>
```

Query receipts without writing anything:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.artifact_audit `
  --repo-root <absolute-repository-root> `
  --list-receipts --goal-id <goal-id>
```

Benchmark receipt storage with a repeatable local comparison:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python scripts\benchmark_artifact_audit.py --iterations 100
```

## Deterministic Operator Flow

Use the orchestrator when the caller should not have to select and inspect each lifecycle command separately:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.run --registry registry\REGISTRY.json --out outputs
```

To continue through the registered global STATE:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.run `
  --registry registry\REGISTRY.json `
  --out outputs `
  --global-registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --global-out outputs\global `
  --require-global
```

Add `--json` to emit a compact machine summary. Actual output always contains all four stages; this abbreviated example shows the stable field shape for one stage:

```json
{
  "version": 1,
  "operation_id": "<pipeline-operation-id>",
  "status": "passed",
  "exit_code": 0,
  "stages": [
    {
      "name": "reconcile",
      "status": "passed",
      "output_path": "C:\\path\\to\\outputs\\STATE.json",
      "entry_count": 3,
      "issue_count": 0,
      "message": null
    }
  ]
}
```

Stage status values are `passed`, `issues`, `failed`, and `skipped`. A failed stage skips dependent later stages. Without `--require-global`, no global registry means an intentional local-only run and global stages are skipped. With `--require-global`, a missing global registry fails before local derived outputs are written.

The global validation stage also requires the local and global STATE files to share the
same `operation_id`, requires global `generated_at` to be no earlier than local
`generated_at`, and requires all local canonical Goal IDs to be visible under the
registered global root ID. Local IDs may be rebased during aggregation.

Exit codes:

- `0`: clean run;
- `1`: operational or validation failure;
- `2`: run completed with lifecycle issues.

The orchestrator calls existing Python APIs directly. It does not start child Codex sessions, invoke an LLM, mutate Goal source files, move goals, or run in the background.
It also canonicalizes output paths and rejects local or global output directories under the user's global `.codex` directory.

## Deterministic Goal Queue

Contract source metadata:

```yaml
scheduling:
  priority: 80
  depends_on:
    - prerequisite-goal
    - other-root/cross-repo-prerequisite
```

- Priority is an integer from `0` through `100`; larger values sort first among peers.
- Missing scheduling metadata defaults to priority `50` with no dependencies.
- Bare dependency IDs resolve within the same registry root.
- Canonical `<root-id>/<goal-id>` dependencies can resolve across registered repos during global aggregation.
- Dependencies always win over priority.
- `queue_position`, scheduling status, unmet dependencies, and queue summaries are derived STATE fields.

Query a generated STATE:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.queue --state outputs\STATE.json
```

Query registered repo STATE files directly without writing aggregate output:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.queue `
  --registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --json
```

Scheduling status values:

- `runnable`: ready and all dependencies are complete;
- `in_progress`: already running and dependency-safe;
- `dependency_blocked`: one or more dependencies are incomplete or unavailable;
- `not_ready`: draft or review-pending with no unmet dependency;
- `blocked`: lifecycle status is blocked;
- `done`: completed or cancelled;
- `invalid`: malformed scheduling, missing same-scope dependency, dependency cycle, or invalid source entry.

`next_goal` is the first runnable or in-progress Goal. `next_planned_goal` is the first open Goal even if it still needs acceptance or review. Agents may change source `priority` after an explicit user request, then reconcile; they must never edit derived queue fields directly.
Invalid Goals are excluded from queue positions and returned separately with their issue codes and Contract paths.

## Session Handoff Query

For a repository with an explicit fresh onboarding report and matching validated global STATE:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.session_handoff `
  --report outputs\ONBOARDING.json `
  --state outputs\global\STATE.json
```

The command is read-only. A valid result selects `next_goal`, or `next_planned_goal` when no Goal is runnable, and returns only the selected Goal's lifecycle, gate, review, evidence, health, issue, and source-path context. The caller must confirm source Contract frontmatter and inspect Git independently.

Exit code `2` means the fast path was rejected. Report `fallback_reason` and use the existing source/worktree scan. Do not run onboarding with `--apply`, refresh STATE, or mutate registration merely to avoid a fallback. See `docs/session-handoff.md` for the versioned decision table.

## Goal Control Desktop Application

Goal Control consumes `outputs\global\STATE.json` through the existing JSON schema validator and presents a read-only desktop dashboard. It never reconciles, onboards, edits a Goal, writes a registry, or refreshes STATE on the user's behalf.

Development launch:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.dashboard_app --state outputs\global\STATE.json
```

The application provides:

- open, runnable, blocked, review-pending, stale, and completed counts;
- search plus status, project, owner, repository, and health filters;
- queue-first Goal ordering and a scrollable Goal dossier;
- safe system opening for Contract, PLAN, and EVIDENCE;
- manual refresh only, with visible malformed/missing STATE and path errors;
- compact, standard, and wide desktop breakpoints. Compact mode hides duplicate Project/Owner table columns while retaining that information in the dossier.

Package and verify:

```powershell
.\.venv\Scripts\python -m pip install -e ".[desktop]"
.\scripts\build_dashboard.ps1
.\scripts\benchmark_dashboard_package.ps1
```

`build_dashboard.ps1` creates an onedir windowed package at `dist\goal-dashboard\GoalControl`. Onedir is intentional: it avoids one-file extraction latency and keeps cold start inside the Contract budget. Do not move `GoalControl.exe` away from its `_internal` directory. Every build verifies the bundled schema hash and launches the packaged application in smoke mode. It uses the current global STATE when available and otherwise falls back to `fixtures\dashboard\clean-state.json`; `-SmokeStatePath` can select an explicit schema-valid STATE for release verification.

The build fails if the bundled Goal STATE schema differs from the source schema. When
`outputs\global\STATE.json` exists, it also launches the packaged executable in hidden
smoke mode and requires a successful model load before reporting a successful build.

Machine-readable smoke or benchmark output can be written even though the executable has no console:

```powershell
dist\goal-dashboard\GoalControl\GoalControl.exe `
  --state outputs\global\STATE.json `
  --smoke `
  --probe-output outputs\dashboard-smoke.json
```

The packaged app discovers a relative default STATE from the executable's ancestor directories. An explicit `--state` path remains preferred for automation. Missing STATE, invalid schema, out-of-root source paths, or missing files are reported without mutation.

## Issue Interpretation

- `missing`: registered root or expected goal path is missing.
- `missing_plan`: a directory-mode goal has no `PLAN.md`.
- `missing_evidence`: a directory-mode goal has no `EVIDENCE.md`.
- `parse_error`: frontmatter could not be parsed.
- `status_folder_mismatch`: goal status and folder location disagree.
- `stale`: contract freshness cannot be confirmed because `updated` is missing.
- `review_pending`: contract or evidence says review is still pending.
- `evidence_incomplete`: evidence is absent or still partial.
- `invalid_scheduling`: priority or dependency metadata is malformed.
- `dependency_missing`: a required dependency cannot be resolved in the applicable registry scope.
- `dependency_cycle`: dependencies form a cycle and cannot produce a valid execution order.
- `duplicate_goal_key`: two entries resolve to the same registry-root/Goal namespace and cannot be ordered safely.
- `health_stale`: an enabled health policy threshold was exceeded.
- `health_date_missing`: a required health-policy date is absent.
- `health_date_invalid`: a health-policy date is not strict `YYYY-MM-DD`.
- `health_date_future`: a health-policy date is after the injected UTC evaluation date.
- `health_date_order`: an activity or completion date precedes `created`.
- `health_completion_inconsistent`: an active Goal declares a completion date.
- `health_evidence_incomplete`: a completed Goal does not have complete evidence.

Health policy is opt-in and report-only. See `docs/health-policy.md` for version-1
defaults, threshold overrides, structured findings, and fixed evaluation dates.

## Production Use Boundary

Allowed now:

- Read registered roots.
- Generate ignored STATE outputs.
- Validate registry and STATE JSON.
- Use STATE as a reviewer/operator dashboard.
- Query deterministic local or global Goal order without an LLM choosing the sequence.
- Use issues as prompts for manual edits.

Not allowed without a separate reviewed proposal:

- Mutating Goal Contract, Plan, or Evidence files from the reconciler.
- Scanning broad filesystem locations.
- Running a watcher or background service.
- Moving active goals to completed automatically.
- Editing source priority or dependencies from read-only queue commands.
- Editing global Codex skills, RTK, hooks, routing, config, or memory stores.

## Adding a Goal Root

Add a root only when it has a stable owner and a known path:

```json
{
  "id": "example-project",
  "label": "Example Project",
  "goal_root": "C:/path/to/project/goals",
  "scope": "repo",
  "project": "example",
  "active": true,
  "added": "2026-07-07",
  "last_seen": null
}
```

Then run reconcile and validation. Do not add roots that require whole-disk discovery.
