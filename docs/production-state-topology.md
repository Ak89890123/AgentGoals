# Production State Topology

## Decision

Use a read-only federated STATE topology as the current production model:

- each repository generates its own derived STATE from its local Goal Contract files;
- a global `.codex` registry records known repo STATE locations and goal roots;
- central views are rebuilt from registered repo outputs, not from whole-disk scans;
- Goal Contract, PLAN, and EVIDENCE files remain the source of truth.

Status: this model is the current approved production/operator topology for Goal Lifecycle STATE. It is still read-only: it does not approve writers, watchers, hooks, daemons, scheduled tasks, source goal mutation, or additional global `.codex` writes.

## Why This Shape

This keeps source ownership local while still allowing a global operator dashboard.

Repo-local STATE gives each project a fast, reviewable view of its own lifecycle. The global `.codex` registry acts as an allowlist and aggregation map, not as write authority over repo goals.

## Current Layout

Repo-local:

```text
<repo>/
  goals/
    active/<goal-id>/
      CONTRACT.md
      PLAN.md
      EVIDENCE.md
    completed/<goal-id>/
      CONTRACT.md
      PLAN.md
      EVIDENCE.md
  outputs/
    STATE.json
    STATE.md
```

Global `.codex` registry:

```text
C:/Users/jimmy0302/.codex/goal-lifecycle/
  REGISTRY.json
```

The reviewed global registry file exists at `C:/Users/jimmy0302/.codex/goal-lifecycle/REGISTRY.json`. Global aggregate STATE output is generated into caller-selected output directories, such as `outputs/global`, and is not written under `.codex` by the current read-only model.

## Registry Semantics

A global registry entry should identify:

- stable repo id;
- display label;
- repo root;
- goal root;
- repo-local STATE path;
- scope (`repo`, `global`, or `harness`);
- active flag;
- added date;
- last seen timestamp.

The registry is an allowlist. `repo_root`, `goal_root`, and `state_path` must be absolute paths. `goal_root` and `state_path` must stay under `repo_root`. The registry does not grant permission to mutate repo goals.

## Aggregation Flow

1. Run repo-local reconcile in each registered repo.
2. Validate each repo-local `outputs/STATE.json`.
3. Read only registered STATE paths from the global registry.
4. Merge entries into a global derived STATE.
5. Render global `STATE.md`.
6. Report missing or stale repo STATE as issues.

Current implementation:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.aggregate --registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json --out outputs\global
```

The command validates the global registry against `schemas/global-registry.schema.json` and validates each repo-local STATE against `schemas/goal-state.schema.json` before merging. Repo-local relative entry paths are rebased against the registered `repo_root` and must remain under the registered `goal_root`.

## Boundary

Implemented in the read-only aggregator:

- schema extension for repo-local STATE paths;
- read-only global aggregator command;
- tests using fixture registries and fixture repo STATE outputs, including absolute path enforcement, path-scope rejection, BOM handling, and multi-root merge coverage;
- generated global STATE under a requested output path.

Not allowed without separate approval:

- writing under `C:/Users/jimmy0302/.codex`;
- adding hooks, watchers, daemons, scheduled tasks, or background services;
- auto-editing repo Goal Contract, PLAN, or EVIDENCE files;
- scanning outside registered roots or registered STATE paths.

## Settled Current Choices

- Current global registry path: `C:/Users/jimmy0302/.codex/goal-lifecycle/REGISTRY.json`.
- Current registry shape stores explicit `repo_root`, `goal_root`, and `state_path`.
- Current repo-local generated STATE remains derived output and is ignored in this repo.
- Current aggregate includes the entries present in each registered repo STATE, including completed goals.

Future changes to these choices require a new proposal, independent review, explicit approval, patch, and verification if they touch global `.codex`, RTK, hooks, routing, memory, skills, or always-on workflow behavior.
