---
type: goal-plan
schema_version: 1
goal_id: cross-repository-migration
status: draft
updated: 2026-07-11
contract: artifacts/cross-repository-migration/CONTRACT.md
evidence: artifacts/cross-repository-migration/EVIDENCE.md
---

## Execution Plan

1. Confirm the target outcome, participating repositories, owners, and constraints.
2. Inventory migration units, dependencies, compatibility requirements, and irreversible actions.
3. Define the target-state mapping and phased rollout order.
4. Agree validation, recovery, and reviewer gates for each phase.
5. Execute only after the contract is updated to `ready` or `in_progress` and applicable gates are satisfied.

## Verification Plan

Record per-repository checks, cross-repository integration checks, and recovery tests in `EVIDENCE.md`.

## Rollback and Recovery

No migration step may proceed until its rollback or recovery path is identified and recorded. Escalate any action that cannot be safely reversed.

## Progress Log

- 2026-07-11: Durable handoff skeleton created; awaiting migration specifics.

## Open Decisions

- Which repositories and migration units are in scope?
- What target state and compatibility window are required?
- Is any phase destructive, regulated, or difficult to reverse?

