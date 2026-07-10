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
3. Register only intentional goal roots in `registry/REGISTRY.json`.
4. Run reconcile.
5. Run schema validation.
6. Treat STATE issues as review prompts, not automatic source-file changes.

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

## Issue Interpretation

- `missing`: registered root or expected goal path is missing.
- `missing_plan`: a directory-mode goal has no `PLAN.md`.
- `missing_evidence`: a directory-mode goal has no `EVIDENCE.md`.
- `parse_error`: frontmatter could not be parsed.
- `status_folder_mismatch`: goal status and folder location disagree.
- `stale`: contract freshness cannot be confirmed because `updated` is missing.
- `review_pending`: contract or evidence says review is still pending.
- `evidence_incomplete`: evidence is absent or still partial.

## Production Use Boundary

Allowed now:

- Read registered roots.
- Generate ignored STATE outputs.
- Validate registry and STATE JSON.
- Use STATE as a reviewer/operator dashboard.
- Use issues as prompts for manual edits.

Not allowed without a separate reviewed proposal:

- Mutating Goal Contract, Plan, or Evidence files from the reconciler.
- Scanning broad filesystem locations.
- Running a watcher or background service.
- Moving active goals to completed automatically.
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
