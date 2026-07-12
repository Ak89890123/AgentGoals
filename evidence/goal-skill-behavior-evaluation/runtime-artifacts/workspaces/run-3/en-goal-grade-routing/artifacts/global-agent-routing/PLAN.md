---
type: goal-plan
schema_version: 1
goal_id: global-agent-routing
status: draft
updated: 2026-07-11
contract: ./CONTRACT.md
evidence: ./EVIDENCE.md
---

# Plan: Global Agent Routing Change

## Execution Steps

1. Obtain explicit approval for the exact global routing surface, target request class, desired destination, fallback, owner, and compatibility constraints.
2. Inspect only the approved files; record the baseline route and identify existing tests or controlled probes.
3. Prepare a minimal proposed diff and a byte-accurate backup or reversible patch; obtain approval for the implementation scope.
4. Add or update targeted routing tests before implementation when the surface is testable; otherwise define repeatable controlled probes for normal, fallback, ambiguous, and unaffected routes.
5. Apply the approved change and run targeted checks plus relevant regression checks.
6. Exercise the documented rollback in a safe controlled setting or otherwise verify it against the backup, then restore the intended approved state.
7. Submit the diff and evidence to an independent reviewer. Record the verdict in `EVIDENCE.md` and proceed only on `PASS`.

## Verification Plan

- Compare baseline and changed routing behavior using the approved representative request set.
- Verify each intended request class reaches its approved destination.
- Verify unknown, ambiguous, unavailable, and failure conditions use the documented fallback without unsafe routing.
- Verify representative unaffected routes have unchanged behavior.
- Capture test or probe commands, outputs, and rollback evidence in `EVIDENCE.md`.

## Rollback / Recovery

- Stop rollout if results differ from the approved specification or review is not `PASS`.
- Restore the approved pre-change backup or reverse the exact approved patch.
- Re-run the baseline probes and record the restored behavior.
- Escalate any partial restore, hidden dependency, or routing ambiguity before further changes.

## Progress Log

- 2026-07-11: Drafted; implementation blocked pending exact target, behavior, approval scope, and reviewer assignment.

## Open Decisions

- Exact global routing files or configuration surface — user/authorized owner — blocks discovery and implementation.
- Requested routing behavior, fallback, and compatibility expectations — user/authorized owner — blocks acceptance-test design.
- Primary owner and independent reviewer authorization — user/authorized owner — blocks readiness.
