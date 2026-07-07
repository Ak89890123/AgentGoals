# Design: Central Goal State Index

## Problem

Goal Contracts can exist across repo-local goal roots and global Codex/Skill goal roots. A user needs one place to see unfinished work, blocked contracts, pending reviewers, incomplete evidence, and recently completed goals.

## Decision

Create a centralized derived index.

The central STATE is not authoritative. It is rebuilt from contract, plan, and evidence frontmatter.

## Components

### Registry

`REGISTRY.json` records known goal roots.

It prevents expensive or surprising whole-disk scans.

### Reconciler

The reconciler rebuilds state from registered roots:

```text
for each goal_root in REGISTRY:
  scan active/**
  scan completed/**
  parse frontmatter
  normalize entry
  detect folder/status mismatch
  emit STATE.json
  render STATE.md
```

### Watcher

Watcher is optional and later-phase.

It should observe registered `active/` and `completed/` paths, debounce events, update changed entries when safe, and fall back to reconcile for ambiguous rename/delete/move events.

## Source Of Truth

Priority order:

1. Contract frontmatter.
2. Plan/evidence frontmatter when present.
3. Folder location as validation signal.
4. Central STATE as cache/dashboard only.

If STATE disagrees with source files, repair STATE.

## Completion Rule

A completed goal should satisfy both:

- contract status is `completed` or `cancelled`
- source path is under `completed/`

If only one is true, flag `status_folder_mismatch`.

## Safety Notes

- Do not scan the whole disk.
- Do not run a long-lived watcher from Codex shell.
- Do not mutate source contracts during read-only reconcile.
- Use atomic writes for generated STATE files.
- Use UTF-8 for all reads/writes.
