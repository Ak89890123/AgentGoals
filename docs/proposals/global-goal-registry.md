---
type: global-change-proposal
schema_version: 1
id: global-goal-registry
title: Global Goal Lifecycle Registry Proposal
status: draft
created: 2026-07-07
updated: 2026-07-07
target_root: C:\Users\jimmy0302\.codex\goal-lifecycle
review:
  required: true
  verdict: pending
approval:
  required_before_patch: true
  token: APPROVE_GLOBAL_GOAL_REGISTRY_PATCH
  received: false
tags:
  - goal-lifecycle
  - global-registry
  - codex-global
  - proposal
---

# Global Goal Lifecycle Registry Proposal

## Purpose

Create a narrow, review-gated global registry location for federated Goal Lifecycle STATE aggregation.

This proposal does not authorize or perform mutation of `C:\Users\jimmy0302\.codex`. It defines the intended global files, schema shape, verification, rollback, and approval boundary.

## Selected Topology

Use a federated STATE model:

- each repo generates its own derived `outputs/STATE.json` and `outputs/STATE.md`;
- global `.codex` stores an allowlist registry and generated aggregate dashboard;
- global aggregation reads only registered repo STATE paths;
- Goal Contract, PLAN, and EVIDENCE files remain authoritative.

## Proposed Global Path

Candidate root:

```text
C:\Users\jimmy0302\.codex\goal-lifecycle\
```

Proposed files:

```text
C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json
C:\Users\jimmy0302\.codex\goal-lifecycle\STATE.json
C:\Users\jimmy0302\.codex\goal-lifecycle\STATE.md
```

Initial patch should create only `REGISTRY.json` unless the implementation includes a reviewed read-only aggregator that can generate `STATE.json` and `STATE.md` from repo-local STATE files.

## Proposed Initial Registry

Initial global registry content should include this harness repo only:

```json
{
  "version": 1,
  "updated": "2026-07-07",
  "roots": [
    {
      "id": "goal-life-cycle",
      "label": "Goal Life Cycle Harness",
      "repo_root": "C:/devhome/goal life cycle",
      "goal_root": "C:/devhome/goal life cycle/goals",
      "state_path": "C:/devhome/goal life cycle/outputs/STATE.json",
      "scope": "harness",
      "project": "goal life cycle",
      "active": true,
      "added": "2026-07-07",
      "last_seen": null
    }
  ]
}
```

## Schema Delta

The current repo-local `registry/REGISTRY.json` schema supports:

- `id`
- `label`
- `goal_root`
- `scope`
- `project`
- `active`
- `added`
- `last_seen`

Global registry should add:

- `repo_root`: stable repo root for operator context;
- `state_path`: repo-local derived STATE file to read during global aggregation.

`goal_root` remains required so the registry can explain source ownership and future repo-local reconcile commands.

## Non-Goals

- Do not edit global `.codex` files until review passes and approval token is supplied.
- Do not add hooks, watchers, daemons, scheduled tasks, or background services.
- Do not mutate repo Goal Contract, PLAN, or EVIDENCE files.
- Do not scan broad filesystem locations.
- Do not make global STATE authoritative.
- Do not change RTK, skill routing, memory stores, provider config, or Codex hooks.

## Read-Only Aggregation Rules

When implemented, the global aggregator must:

1. read only the global registry path supplied by the operator;
2. read only registered `state_path` files;
3. validate every repo-local STATE before merging;
4. report missing or malformed repo STATE as issues;
5. write only the requested aggregate output directory;
6. never edit repo-local source goal files.

## Backup And Rollback

Before any global patch:

- create the target directory only if it does not exist;
- if any target file exists, copy it to a timestamped backup beside the file;
- record SHA-256 hashes for existing files before editing.

Rollback:

- restore timestamped backups if files existed;
- remove newly created files only if they were created by the approved patch and no later user edits occurred;
- re-run repo-local tests, reconcile, and validation;
- record rollback evidence in this repo.

## Verification Plan

Before global patch:

1. Run independent review on this proposal.
2. Confirm target path existence and baseline file hashes, if any.
3. Confirm approval token is supplied exactly:

```text
APPROVE_GLOBAL_GOAL_REGISTRY_PATCH
```

After approved patch:

1. Verify global JSON parses.
2. Validate global registry against the reviewed schema.
3. Confirm no RTK, hooks, skill routing, memory, provider, or config files changed.
4. Run this harness:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pytest
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry/REGISTRY.json --out outputs
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry/REGISTRY.json --state outputs/STATE.json
```

## Reviewer Gate

Reviewer is required before global mutation.

Reviewer should check:

- whether the global path is narrow and appropriate;
- whether the registry remains an allowlist, not write authority;
- whether `repo_root`, `goal_root`, and `state_path` are sufficient and not overbroad;
- whether global aggregation remains read-only;
- whether backup, rollback, and verification are sufficient;
- whether the approval boundary excludes hooks, watchers, skills, RTK, routing, memory, provider config, and background services.

Reviewer verdict must be one of:

- `PASS`
- `FAIL`
- `NEEDS_EVIDENCE`

Current verdict: `pending`

## Approval Boundary

Even after review passes, patching global files requires this exact approval token:

```text
APPROVE_GLOBAL_GOAL_REGISTRY_PATCH
```

Approval is scoped only to:

- creating or updating `C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json`;
- creating the parent directory if missing;
- creating timestamped backups for changed files.

It does not approve global hooks, skill edits, RTK edits, memory-store edits, routing changes, provider/model config changes, watchers, daemons, scheduled tasks, or source goal mutation.

