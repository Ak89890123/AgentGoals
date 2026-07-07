---
type: global-change-proposal
schema_version: 1
id: global-goal-registry
title: Global Goal Lifecycle Registry Proposal
status: patched
created: 2026-07-07
updated: 2026-07-07
target_root: C:\Users\jimmy0302\.codex\goal-lifecycle
review:
  required: true
  verdict: PASS
approval:
  required_before_patch: true
  token: APPROVE_GLOBAL_GOAL_REGISTRY_PATCH
  received: true
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

The reviewed schema artifact for the first global registry patch is `docs/global-registry-schema-notes.md`. A formal JSON Schema for the global registry should be added before implementing automated global aggregation.

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
3. Confirm the repo-local `state_path` exists by running repo-local reconcile first, or record that first global aggregation may report the registered repo STATE as missing.
4. Confirm approval token is supplied exactly:

```text
APPROVE_GLOBAL_GOAL_REGISTRY_PATCH
```

After approved patch:

1. Verify global JSON parses.
2. Validate global registry against the reviewed schema artifact: `docs/global-registry-schema-notes.md`.
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

Current verdict: `PASS`

Reviewer: `codex_harness_master` / Godel (`019f3ae3-a1c8-7283-a5a2-c75ea665927a`)

Reviewer notes:

- Low: `docs/global-registry-schema-notes.md` is a reviewed schema note, not executable JSON Schema. This is acceptable for the initial single-file registry patch, but automated aggregation should add a formal JSON Schema first.
- Low: initial `state_path` points to repo-local `outputs/STATE.json`; patch gate must confirm repo-local STATE exists or accept that first aggregation reports it as missing without mutating source files.

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

## Patch Result

Applied on 2026-07-07 after explicit approval token.

Created global directory:

- `C:\Users\jimmy0302\.codex\goal-lifecycle`

Created global file:

- `C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json`

Backup:

- None. The target file did not exist before this patch.

Baseline SHA-256:

```text
none
```

New `REGISTRY.json` SHA-256:

```text
149CCB53C06C210A9EBE40DDE0FB1DC6BFB2905471D4DB1E40EA1FCD5AFE08ED
```

Post-patch verification:

- Global JSON parsed successfully.
- Target directory contains only `REGISTRY.json`.
- Registry contains one active root: `goal-life-cycle`.
- Registered `state_path` exists: `C:/devhome/goal life cycle/outputs/STATE.json`.
- No hooks, skills, RTK, routing, memory, provider config, watcher, daemon, or source goal files were changed by the global patch.
- `.\\.venv\\Scripts\\python -m pytest` passed: 16 tests.
- `goal_lifecycle.reconcile` regenerated repo-local STATE.
- `goal_lifecycle.validate` accepted `registry/REGISTRY.json` and `outputs/STATE.json`.
