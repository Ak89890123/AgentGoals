# Handoff: Goal Life Cycle / Central Goal State Index

Date: 2026-07-07

## Conversation Summary

The user explored whether `goal-preflight` should have a central state index similar to CBM or CodeGraph.

Settled points:

- A centralized STATE is useful.
- The STATE should be a derived index/dashboard, not the canonical truth.
- Goal Contract, PLAN, and EVIDENCE frontmatter remain source of truth.
- Repo-local work can still keep files in `<repo>/goals/active/` and `<repo>/goals/completed/`.
- A global index can live separately and point to known goal roots.
- A registry should avoid scanning the entire machine.
- Reconcile-first is safer than watcher-first.
- File-change maintenance can come later as an incremental accelerator.

## Proposed Architecture

```text
<repo>/goals/
  active/
  completed/

central index project / runtime state:
  STATE.json
  STATE.md
  REGISTRY.json
```

`REGISTRY.json` lists known goal roots. The reconciler scans only those roots.

## Index Semantics

STATE entries should include:

- `id`
- `title`
- `status`
- `project`
- `goal_root`
- `contract_path`
- `owner`
- `updated`
- `review.required`
- `review.verdict`
- `evidence.status`
- `next_action`
- `blocked_reason`
- `source_hash`
- `last_seen`
- detected issues such as `missing`, `stale`, or `status_folder_mismatch`

## Execution Recommendation

Start with a read-only reconciler:

1. Read registry.
2. Scan each registered `active/` and `completed/` tree.
3. Parse YAML frontmatter.
4. Emit centralized `STATE.json`.
5. Render `STATE.md`.
6. Flag mismatches and stale entries.

After that passes fixture tests, add file-change based incremental maintenance with debounce and reconcile fallback.

## Governance Boundary

This project is a harness/prototype. It does not authorize edits to global skills, hooks, RTK, Codex config, memory stores, or watcher services.

Before changing `goal-preflight` or global workflow behavior, use the review-first gate:

1. proposal
2. independent review
3. explicit approval
4. patch
5. verification
