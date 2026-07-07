# Production State Topology

## Decision

Use a federated STATE topology:

- each repository generates its own derived STATE from its local Goal Contract files;
- a global `.codex` registry records known repo STATE locations and goal roots;
- central views are rebuilt from registered repo outputs, not from whole-disk scans;
- Goal Contract, PLAN, and EVIDENCE files remain the source of truth.

## Why This Shape

This keeps source ownership local while still allowing a global operator dashboard.

Repo-local STATE gives each project a fast, reviewable view of its own lifecycle. The global `.codex` registry acts as an allowlist and aggregation map, not as write authority over repo goals.

## Proposed Layout

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

Global `.codex` candidate:

```text
C:/Users/jimmy0302/.codex/goal-lifecycle/
  REGISTRY.json
  STATE.json
  STATE.md
```

The global files above are not created by this step. Creating them requires a separate global mutation proposal, independent review, explicit approval, patch, and verification.

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

The registry is an allowlist. It does not grant permission to mutate repo goals.

## Aggregation Flow

1. Run repo-local reconcile in each registered repo.
2. Validate each repo-local `outputs/STATE.json`.
3. Read only registered STATE paths from the global registry.
4. Merge entries into a global derived STATE.
5. Render global `STATE.md`.
6. Report missing or stale repo STATE as issues.

## Boundary

Allowed for the next implementation proposal:

- schema extension for repo-local STATE paths;
- read-only global aggregator command;
- tests using fixture registries and fixture repo STATE outputs;
- generated global STATE under a repo-local fixture output path.

Not allowed without separate approval:

- writing under `C:/Users/jimmy0302/.codex`;
- adding hooks, watchers, daemons, scheduled tasks, or background services;
- auto-editing repo Goal Contract, PLAN, or EVIDENCE files;
- scanning outside registered roots or registered STATE paths.

## Open Questions

- Exact global `.codex` path name: `goal-lifecycle`, `goals`, or another stable directory.
- Whether global registry should store both `goal_root` and `state_path`, or infer one from the other.
- Whether repo-local generated STATE should remain ignored everywhere or be committed in selected repos.
- Whether the global aggregate should include completed goals by default or only active and review-pending goals.

