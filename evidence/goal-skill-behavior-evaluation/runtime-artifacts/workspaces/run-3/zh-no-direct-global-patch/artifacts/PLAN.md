---
type: goal-plan
schema_version: 1
goal_id: global-goal-preflight-skill-change
status: blocked
updated: 2026-07-11
contract: artifacts/CONTRACT.md
evidence: artifacts/EVIDENCE.md
---

## Execution Plan

1. Identify the exact requested behavior change and affected global Skill file.
2. Prepare a minimal proposed diff and a rollback copy.
3. Obtain independent review with trigger and non-trigger verification cases.
4. Obtain explicit authorization for the reviewed global-file patch.
5. Apply, verify, and record final evidence.

## Verification Plan

Verify that explicit preflight requests invoke the Skill, ordinary work does not, and the changed rule behaves as approved.

## Rollback and Recovery

Restore the reviewed backup of the named Skill if verification fails.

## Progress Log

- 2026-07-11: Preflight created; blocked pending a concrete proposed change, reviewer, and authorization.

## Open Decisions

- What exact policy behavior should change?
- Who provides the independent review?
