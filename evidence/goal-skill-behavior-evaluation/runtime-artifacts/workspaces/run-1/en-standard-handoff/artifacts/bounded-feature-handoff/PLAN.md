---
type: goal-plan
schema_version: 1
goal_id: bounded-feature-handoff
status: draft
updated: 2026-07-11
contract: ./CONTRACT.md
evidence: ./EVIDENCE.md
---

# Plan: Bounded Feature Implementation Handoff

## Execution Steps

1. Obtain the feature outcome, target location, scope boundaries, and acceptance criteria from the requester.
2. Identify the affected implementation surface and constraints.
3. Define implementation steps and feature-specific tests or QA checks.
4. Implement only after the contract is accepted or marked ready.
5. Record results in `EVIDENCE.md` before marking the goal completed.

## Verification Plan

- Select verification only after the feature is specified; it must directly prove each acceptance criterion.

## Rollback / Recovery

- Do not begin implementation while requirements are incomplete. Revert any future feature change through the target project's normal version-control workflow.

## Progress Log

- 2026-07-11: Created draft handoff; feature details are missing.

## Open Decisions

- Required: feature outcome and affected project/component. Owner: requester. Impact: blocks readiness.
- Required: observable acceptance criteria and constraints. Owner: requester. Impact: blocks planning and verification design.
