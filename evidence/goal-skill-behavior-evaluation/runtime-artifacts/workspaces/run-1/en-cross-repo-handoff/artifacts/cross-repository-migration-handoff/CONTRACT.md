---
type: goal-contract
schema_version: 1
id: cross-repository-migration-handoff
title: Cross-Repository Migration Handoff
status: draft
created: 2026-07-11
updated: 2026-07-11
completed:
owner: unassigned
file_mode: directory
project: isolated-behavior-evaluation
paths:
  contract: ./artifacts/cross-repository-migration-handoff/CONTRACT.md
  plan: ./PLAN.md
  evidence: ./EVIDENCE.md
review:
  required: false
  verdict: pending
tags: [migration, cross-repository, handoff]
---

# Goal Contract: Cross-Repository Migration Handoff

## Contract

### Goal

Provide durable execution state for a cross-repository migration that can be safely resumed across multiple sessions.

### Deliverable

This directory-mode handoff: `CONTRACT.md`, `PLAN.md`, and `EVIDENCE.md`.

### Success Criteria

- The participating repositories, migration outcome, and ownership are identified.
- Scope, non-goals, sequencing, rollback, and verification are agreed before migration execution.
- A later session can record evidence and resume from `PLAN.md` without relying on chat history.

### Scope

Included:

- Pre-execution migration handoff and its execution/evidence structure.

Not included:

- Selecting repositories, changing source files, running migration steps, or releasing changes.

### Rubric

- Completeness: all repositories, dependencies, and target state are named.
- Safety: rollback and data-integrity risks are explicit.
- Handoff quality: next actions, owners, and evidence locations are unambiguous.
- Verifiability: each migration phase has observable acceptance evidence.

### Constraints

- No repository or migration target has been supplied; do not begin execution.
- Store durable handoff artifacts only in this directory until the target project locations are confirmed.

### Routing

- Task size: goal-grade
- Primary owner: unassigned
- Supporting roles: repository owners; migration reviewer when risk requires it
- Supporting skills or workflows: Goal Preflight
- Skipped but considered: migration execution, because this request is handoff-only

### Required Evidence

- Repository inventory and source/target mapping.
- Approved migration sequence and dependency order.
- Per-repository verification results and rollback evidence.

### Reviewer Gate

- Required: no, unless the finalized migration affects data integrity, permissions, security, deployment/release, or is hard to roll back.
- Reviewer type: independent migration or domain reviewer when required.
- Verdict: pending
- Remaining risk: migration details are not yet known.

### Assumptions

- This is a planning-only request; no execution authority is implied.
- The final durable handoff should move to a confirmed target project's `goals/active/` directory when writable.

### Escalation Rules

Stop and ask the user when:

- The target outcome, repository set, ownership, data/privacy impact, rollback feasibility, or release scope is unknown or changes materially.

## Execution Plan

See [PLAN.md](PLAN.md).

## Completion Notes

- Final status: not started
- Evidence summary: pending
- Final reviewer verdict: pending
