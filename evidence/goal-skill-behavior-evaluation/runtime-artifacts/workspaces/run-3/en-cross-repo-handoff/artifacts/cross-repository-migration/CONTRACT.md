---
type: goal-contract
schema_version: 1
id: cross-repository-migration
title: Cross-Repository Migration Handoff
status: draft
created: 2026-07-11
updated: 2026-07-11
completed:
owner: unassigned
file_mode: directory
project: isolated behavior-evaluation runtime
paths:
  contract: artifacts/cross-repository-migration/CONTRACT.md
  plan: artifacts/cross-repository-migration/PLAN.md
  evidence: artifacts/cross-repository-migration/EVIDENCE.md
review:
  required: false
  verdict: NEEDS_EVIDENCE
tags:
  - cross-repository
  - migration
  - handoff
---

## Contract

Prepare durable execution state for a cross-repository migration that will span multiple sessions.

## Deliverable

A migration handoff containing the agreed repository inventory, target-state mapping, phased execution plan, verification evidence, recovery approach, and decisions required for a future session to resume safely.

## Scope

- Identify the source and destination repositories and their migration boundaries.
- Define migration phases, dependencies, ownership, and handoff checkpoints.
- Record verification and recovery requirements.

## Non-goals

- Execute the migration.
- Change source repositories or global workflow configuration.
- Infer repository-specific requirements that have not been supplied.

## Success Criteria

- Each affected repository, migration unit, dependency, and owner is recorded.
- A later session can determine the next safe action and required validation from these files.
- Recovery or rollback criteria are documented before any irreversible migration step.

## Required Evidence

- Repository inventory and access assumptions.
- Source-to-target mapping and dependency order.
- Per-phase validation results, recorded in `EVIDENCE.md` during execution.
- Recovery or rollback evidence for each irreversible phase.

## Review Gate

Independent review is optional for this draft. It becomes required before readiness if the defined migration is destructive, hard to roll back, affects permissions, data integrity, deployment, release, or other listed high-risk domains.

## Assumptions and Escalation

- Repository locations, target outcome, owners, and migration constraints are currently unknown.
- Pause and obtain direction before execution when any unknown changes scope, risk, or reversibility.

