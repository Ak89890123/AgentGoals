---
type: goal-plan
schema_version: 1
goal_id: database-migration-preflight
status: draft
updated: 2026-07-11
contract: artifacts/database-migration-preflight/CONTRACT.md
evidence: artifacts/database-migration-preflight/EVIDENCE.md
---

## Execution Plan

1. Name the target database(s), environments, migration owner, affected services, and change window.
2. Inventory schema/data changes, dependencies, data volume, locking behavior, compatibility needs, and irreversible operations.
3. Define the versioned forward migration and preflight checks; prepare backups and a restore point.
4. Define acceptance queries, reconciliation thresholds, application smoke tests, latency/error limits, and monitoring period.
5. Write and rehearse rollback in a representative non-production environment, including trigger thresholds and recovery ownership.
6. Obtain independent review of the runbook and evidence.
7. Execute only after the contract is updated to `ready`; record live evidence and final status separately.

## Verification and Recovery

Verify backups before execution, run integrity/reconciliation checks before and after the change, and retain the prior compatible application/database path until the monitoring period passes. If a rollback trigger occurs, stop further rollout, restore or run the reverse migration as approved, validate integrity, and notify the escalation contacts.

## Open Decisions

- Exact migration target and migration type.
- Data-loss/downtime tolerance and maintenance window.
- Rollback method, ownership, and maximum recovery time.
- Required reviewer and production authorization path.
