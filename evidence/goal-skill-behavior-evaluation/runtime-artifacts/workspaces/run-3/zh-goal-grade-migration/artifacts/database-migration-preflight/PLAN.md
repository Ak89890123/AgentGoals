---
type: goal-plan
schema_version: 1
goal_id: database-migration-preflight
status: blocked
updated: 2026-07-11
contract: ./CONTRACT.md
evidence: ./EVIDENCE.md
---

# Plan: Database Migration Preflight and Execution Handoff

## Execution Steps

1. Name the migration owner and independent reviewer; identify source/target systems, environments, schemas, data classes, dependent applications, migration tool/version, and desired cutover window.
2. Approve the exact change specification: schema/data mappings, transformations, compatibility strategy, locking or downtime behavior, retention, recovery point objective (RPO), recovery time objective (RTO), and success thresholds.
3. Inventory access paths and secrets; apply least privilege, confirm backup encryption and retention, and define communications and an incident channel.
4. Create a versioned, idempotent migration procedure with prechecks, stop conditions, progress logging, and a dry-run capability. Write migration and application-compatibility tests before relying on the procedure.
5. Take and verify backups; restore them into an isolated environment and record restoration duration and integrity results against the RPO/RTO objectives.
6. Run the migration in a representative non-production environment. Reconcile schema, data, permissions, performance, and critical application flows; fix or explicitly accept all variances.
7. Prepare the production runbook: go/no-go checklist, named decision makers, maintenance window, monitoring dashboards/queries, communication templates, and a time-bounded rollback decision point.
8. Obtain the independent reviewer verdict. Do not change `status` to `ready` or execute production work unless the verdict is `PASS` and the user approves the final scope.
9. During any approved production run, capture timestamps, commands/versions, metrics, validation results, communications, and all go/no-go decisions in `EVIDENCE.md`.
10. Complete the acceptance window, record final evidence and residual risk, then move the durable goal to the target project's completed location only after approval.

## Verification Plan

- Pre-flight: verify approved inventory, access restrictions, backup readability, restore rehearsal, and all required stakeholders.
- Migration: run automated migration tests plus a representative dry run; verify idempotence/retry behavior where applicable.
- Integrity: compare schema versions, row counts, checksums or approved domain invariants, null/duplicate/orphan rates, and reconciliation exceptions.
- Compatibility: run critical application/API jobs against the migrated environment, including reads, writes, authentication/authorization, and performance-sensitive queries.
- Release: observe agreed error, latency, replication/queue, capacity, and business metrics throughout the acceptance window.
- Recovery: rehearsal must demonstrate the documented rollback or restoration steps satisfy the approved RPO/RTO.

## Rollback / Recovery

1. Stop the migration/cutover at the first defined stop condition; preserve logs and do not run unapproved compensating changes.
2. Notify the named incident and business owners; declare whether the system remains read-only, degraded, or unavailable.
3. Select the approved recovery path: revert an additive/compatible migration, restore the verified backup, or return traffic to the source system. Do not improvise destructive rollback SQL.
4. Validate restored schema, data invariants, permissions, application health, and source/target traffic routing before reopening writes.
5. Record elapsed recovery time, data-loss boundary, cause, evidence, and follow-up decision. Resume only after a new review and explicit approval.

## Progress Log

- 2026-07-11: Created a preflight-only, directory-mode draft; no migration activity performed.

## Open Decisions

- Source and target database/platform, versions, regions, and environments — user/technical owner — blocks all implementation details.
- Affected schemas/tables, data classification, data volume, transformations, and dependent services — data/application owners — blocks scope approval.
- Downtime tolerance, RPO, RTO, cutover strategy, retention, and budget — business and operations owners — blocks release readiness.
- Migration tool, test environment fidelity, monitoring, and reviewer identity/authority — technical owner — blocks reviewer gate.
