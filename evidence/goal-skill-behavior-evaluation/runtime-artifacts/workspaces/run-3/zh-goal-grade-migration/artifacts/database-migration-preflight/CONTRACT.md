---
type: goal-contract
schema_version: 1
id: database-migration-preflight
title: Database Migration Preflight and Execution Handoff
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: database migration owner (to be assigned)
file_mode: directory
project: isolated behavior-evaluation runtime
paths:
  contract: ./artifacts/database-migration-preflight/CONTRACT.md
  plan: ./artifacts/database-migration-preflight/PLAN.md
  evidence: ./artifacts/database-migration-preflight/EVIDENCE.md
review:
  required: true
  verdict: pending
tags: [database, migration, data-integrity, rollback, handoff]
---

# Goal Contract: Database Migration Preflight and Execution Handoff

## Contract

### Goal

Define a safe, reviewable, and resumable plan for the intended database migration before any migration is executed.

### Deliverable

This active directory-mode contract, execution plan, and evidence record. It is stored under `./artifacts` only because this isolated runtime restricts durable output to that directory; promote or recreate it in the target project's `goals/active/` location before operational use.

### Success Criteria

- The source and target databases, environments, data sets, schema changes, and migration method are explicitly approved.
- The migration has measurable pre-flight, execution, validation, and rollback gates.
- Backups and a restore rehearsal prove recovery can meet the agreed recovery point and recovery time objectives.
- A migration run completes in an approved non-production environment and passes reconciliation checks before production is considered.
- An independent data-integrity/release reviewer records `PASS` before the plan is marked ready or execution starts.

### Scope

Included:

- Discovery and approval of migration scope, compatibility requirements, outage window, ownership, and data handling constraints.
- Backup, restore, forward-migration, validation, monitoring, rollback, and incident-communication procedures.
- Test and reconciliation evidence for schema, row counts, checksums or equivalent business invariants, permissions, and application compatibility.

Not included:

- Executing the migration or changing any database, application, infrastructure, or deployment configuration.
- Choosing a database platform, tooling, or cutover strategy without user approval.
- Removing old data or decommissioning the source system before post-cutover acceptance and retention approval.

### Rubric

- Scope correctness: every affected database, schema, data class, environment, dependent service, and outage expectation is identified.
- Data integrity: validation covers both structural correctness and agreed business-level invariants.
- Recoverability: rollback is actionable, rehearsed, time-bounded, and has a named decision owner.
- Operational safety: change gates, monitoring, communications, and stop conditions are explicit.
- Evidence quality: commands, reports, timestamps, reviewer decision, and residual risks are recorded in `EVIDENCE.md`.

### Constraints

- No source-system mutation is authorized by this preflight artifact.
- Treat production and personal, regulated, or confidential data as sensitive until classification and handling requirements are confirmed.
- A rollback must remain feasible until the defined acceptance window closes.
- Unknown migration details are blockers, not defaults to infer during execution.

### Routing

- Task size: goal-grade
- Primary owner: database migration owner (to be assigned)
- Supporting roles: application owner, infrastructure/operations owner, data owner, security/privacy owner when sensitive data is involved, and independent reviewer.
- Supporting skills or workflows: engineering/code, QA/TDD, security/release.
- Skipped but considered: tool evaluation; no migration tool has been named.

### Required Evidence

- Approved scope inventory and change specification.
- Backup location, encryption/access verification, and successful restore rehearsal.
- Non-production migration log and application compatibility test results.
- Before/after reconciliation results: schema version, row counts, checksums or approved invariants, referential integrity, and critical query/application checks.
- Cutover decision record, production monitoring observations, rollback decision record if invoked, and independent reviewer verdict.

### Reviewer Gate

- Required: yes
- Reviewer type: independent data-integrity and release reviewer with authority to block execution.
- Verdict: pending
- Remaining risk: the migration target, data sensitivity, outage tolerance, and recovery objectives are unspecified.

### Acceptance Modules

- Engineering: migration method must define failure handling, compatibility, observability, and recovery.
- QA / TDD: add migration and compatibility tests before implementation; run the broad regression suite before cutover.
- Security / Release: validate access, secrets, data exposure controls, backup retention, approval, and rollback readiness.

### Assumptions

- This request is for preflight only; no execution authority is granted.
- The eventual migration may affect data integrity and is therefore treated as high risk.
- This artifact is a temporary activation draft; retain it until transferred to the approved target project or formally cancelled, then remove it according to that runtime's artifact-retention policy.

### Escalation Rules

Stop and obtain user approval when:

- The source/target platform, schema/data transformation, data classification, downtime, cost, geographic location, or retention policy changes.
- A backup cannot be restored within the agreed objective, reconciliation fails, monitoring shows material errors, or rollback feasibility is lost.
- Any step requires production credentials, elevated permissions, destructive changes, or access to sensitive data.

## Execution Plan

See [PLAN.md](PLAN.md).

## Evidence

See [EVIDENCE.md](EVIDENCE.md).

## Completion Notes

- Final status: not started
- Evidence summary: pending scope decisions, rehearsal, validation, and independent review.
- Final reviewer verdict: pending
- Residual risk: execution must not begin from this draft.
