# Goal Lifecycle Harness Usage

## Purpose

Use this harness to rebuild a derived Goal STATE from registered Goal Contract directories.

The source of truth remains:

```text
goals/<status>/<goal-id>/
  CONTRACT.md
  PLAN.md
  EVIDENCE.md
```

`outputs/STATE.json` and `outputs/STATE.md` are generated dashboards only.

## Normal Operator Flow

1. Edit Goal Contract, Plan, and Evidence files directly.
2. Keep machine-readable status values in lowercase snake_case.
3. Put adjustable priority and hard dependencies in Contract `scheduling` metadata.
4. Register only intentional goal roots in `registry/REGISTRY.json`.
5. Run reconcile.
6. Run schema validation.
7. Treat STATE issues as review prompts, not automatic source-file changes.

PowerShell:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry\REGISTRY.json --out outputs
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry\REGISTRY.json --state outputs\STATE.json
```

Run tests before committing harness changes:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pytest
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
  --global-out outputs\global
```

Add `--json` to emit a compact machine summary. Actual output always contains all four stages; this abbreviated example shows the stable field shape for one stage:

```json
{
  "version": 1,
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

Stage status values are `passed`, `issues`, `failed`, and `skipped`. A failed stage skips dependent later stages. Global stages are also skipped, without failure, when no global registry is supplied.

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
