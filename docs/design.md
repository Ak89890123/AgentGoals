# Design: Central Goal State Index

## Problem

Goal Contracts can exist across repo-local goal roots and global Codex/Skill goal roots. A user needs one place to see unfinished work, blocked contracts, pending reviewers, incomplete evidence, and recently completed goals.

## Decision

Create a federated derived index.

Each repo can generate its own derived STATE from contract, plan, and evidence frontmatter. A central global registry can aggregate registered repo STATE outputs. No generated STATE is authoritative.

## Components

### Registry

`REGISTRY.json` records known goal roots.

It prevents expensive or surprising whole-disk scans.

In production topology, each repo should own its local generated STATE. A global `.codex` registry should record registered repo goal roots and repo-local STATE paths for read-only aggregation.

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

### Global Aggregator

The global aggregator is a later read-only command. It should read only registered repo-local `STATE.json` files from a global `.codex` registry, validate each STATE, merge entries, and render a global dashboard.

It must not scan the whole disk and must not mutate repo-local contracts.

### Watcher

Watcher is optional and later-phase.

It should observe registered `active/` and `completed/` paths, debounce events, update changed entries when safe, and fall back to reconcile for ambiguous rename/delete/move events.

## Source Of Truth

Priority order:

1. Contract frontmatter.
2. Plan/evidence frontmatter when present.
3. Folder location as validation signal.
4. Repo-local or global STATE as cache/dashboard only.

If STATE disagrees with source files, repair generated STATE by reconciling from the source files.

## Completion Rule

A completed goal should satisfy both:

- contract status is `completed` or `cancelled`
- source path is under `completed/`

If only one is true, flag `status_folder_mismatch`.

## Safety Notes

- Do not scan the whole disk.
- Do not run a long-lived watcher from Codex shell.
- Do not mutate source contracts during read-only reconcile.
- Do not create or edit global `.codex` registry files without proposal, independent review, explicit approval, patch, and verification.
- Use atomic writes for generated STATE files.
- Use UTF-8 for all reads/writes.
