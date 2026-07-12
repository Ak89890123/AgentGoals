---
type: goal-contract
schema_version: 1
id: database-migration-preflight
title: Database Migration Scope, Acceptance, and Rollback Preflight
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: to_be_assigned
file_mode: directory
project: current_project
paths:
  contract: artifacts/database-migration-preflight/CONTRACT.md
  plan: artifacts/database-migration-preflight/PLAN.md
  evidence: artifacts/database-migration-preflight/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags: [database, migration, rollback, preflight]
---

## Contract

Define and approve a safe, reversible database migration before execution.

Deliverable: an approved migration brief that identifies affected databases, schemas, tables, data transformations, compatibility assumptions, deployment sequence, acceptance criteria, evidence, and a tested rollback procedure.

## Scope

- Inventory all schema and data changes, including indexes, constraints, backfills, permissions, and dependent applications.
- Define forward migration, validation, monitoring, rollback trigger, and rollback steps.
- Establish measurable acceptance criteria and required evidence before production execution.

## Non-goals

- Executing the migration or changing application/database source files.
- Broad infrastructure, retention, or product redesign unrelated to this migration.

## Success Criteria

- Target environments, affected data, owners, dependencies, and maintenance-window assumptions are recorded and approved.
- The forward migration is idempotent or has an explicit rerun/recovery procedure.
- Pre- and post-migration checks show schema correctness, data integrity, application compatibility, and expected performance.
- Rollback is documented, tested in a representative non-production environment, and has explicit activation thresholds.
- Backup/restore point, data-loss tolerance, and communications/escalation contacts are confirmed.

## Required Evidence

- Reviewed migration script or runbook with checksums/version identifiers.
- Non-production execution log, timing, and validation results.
- Backup/restore verification and rollback rehearsal results.
- Query-level integrity and reconciliation results, plus application smoke-test results.
- Independent reviewer verdict: `PASS` before readiness is claimed.

## Reviewer Gate

Independent database/security or release reviewer is required because the work affects data integrity and may be difficult to reverse. Until the evidence is supplied and the verdict is `PASS`, this goal remains review pending.

## Assumptions and Escalation

- The migration target, environment sequence, and downtime tolerance are not yet specified.
- Escalate for approval before any destructive, irreversible, or production operation; pause if backup verification, integrity checks, or rollback rehearsal fails.
