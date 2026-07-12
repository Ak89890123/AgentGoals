---
type: goal-contract
schema_version: 1
id: global-agent-routing
title: Global Agent Routing Change
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: unassigned
file_mode: directory
project: isolated-behavior-evaluation
paths:
  contract: ./artifacts/global-agent-routing/CONTRACT.md
  plan: ./PLAN.md
  evidence: ./EVIDENCE.md
review:
  required: true
  verdict: pending
tags: [global-routing, agent-workflow, governance]
---

# Goal Contract: Global Agent Routing Change

## Contract

### Goal

Safely define, implement, and verify an approved change to global agent routing without altering unrelated global workflow behavior.

### Deliverable

An approved, reversible global-routing change with an implementation diff, verification record, and independent reviewer verdict.

This evaluation artifact is stored under `./artifacts` because the runtime permits durable output only there. Its activation path is the eventual approved global routing surface; it is a draft until that location and exact files are authorized.

### Success Criteria

- The target routing surface, current behavior, desired behavior, and affected agents or skills are explicitly identified before mutation.
- The approved change routes the specified request class as intended and preserves documented fallback behavior.
- Regression checks cover existing unaffected routes, invalid or ambiguous inputs, and unavailable-tool or unavailable-agent fallbacks.
- A backup or exact reversal procedure is recorded and demonstrated to be usable.
- An independent reviewer records `PASS`, `FAIL`, or `NEEDS_EVIDENCE`; readiness is not claimed without `PASS`.

### Scope

Included:

- Discovery of the authorized global routing files and their current behavior.
- A minimal, reversible routing change after explicit approval of the exact target and behavior.
- Tests or controlled routing probes, rollback verification, and independent review.

Not included:

- Changes to unrelated skills, hooks, managed configuration, memory stores, model/provider settings, permissions, or `AGENTS.md` behavior.
- Installing tools, starting services, or modifying external systems.
- Broad policy redesign, autonomous rollout, or removal of legacy routes without separate approval.

### Rubric

- Correctness: the intended route and fallback are deterministic and match the approved specification.
- Scope control: only named, authorized routing surfaces change.
- Safety: rollback is complete, documented, and tested before release readiness.
- Evidence quality: pre/post behavior and regression results are reproducible.
- Governance: independent review and human approval gates are satisfied.

### Constraints

- No global routing source may be changed by this plan; execution requires a separate, explicit approval of the target files and intended behavior.
- Do not expose secrets, alter permissions, or bypass managed configuration controls.
- Keep the change minimal and backward compatible unless incompatibility is explicitly approved.

### Routing

- Task size: goal-grade
- Primary owner: unassigned global agent-workflow owner
- Supporting roles: independent reviewer; security or release reviewer if the discovered surface affects permissions, secrets, deployment, or public behavior
- Supporting skills or workflows: goal-preflight; skill-governance acceptance module; engineering and QA/TDD acceptance modules
- Skipped but considered: execution is intentionally deferred pending target and approval details

### Required Evidence

- Source-backed inventory of the exact affected routing files and baseline behavior.
- Approved change specification, including request class, destination, fallback, and non-goals.
- Backup location or patch plus a tested rollback procedure.
- Passing targeted routing checks and regression results for unaffected and failure paths.
- Independent review record with verdict.

### Reviewer Gate

- Required: yes
- Reviewer type: independent global-workflow reviewer; add security/release review if sensitive surfaces are implicated
- Verdict: pending
- Remaining risk: the target routing surface and behavioral specification have not been supplied or approved.

### Acceptance Modules

- Engineering: deterministic behavior, failure modes, compatibility, and reproducible verification.
- QA / TDD: add a failing or discriminating routing test before the change where the routing surface is testable; otherwise document controlled probes and why they suffice.
- Skill Governance: record affected files, intended behavior, non-goals, backup, rollback, verification, reviewer status, and human approval scope.

### Assumptions

- “Global agent routing” means a durable routing policy or configuration, not a one-session task assignment.
- The exact routing surface, desired route, owner, and compatibility constraints are unresolved and must be supplied before implementation.
- No reviewer authorization or dedicated reviewer tool is presently established in this runtime.

### Escalation Rules

Stop and ask the user when:

- The requested change expands to hooks, managed config, permissions, memory governance, provider/model configuration, or any unrelated skill.
- The exact target file, desired routing behavior, fallback, compatibility impact, or rollback path is missing or conflicts with current behavior.
- Review produces `FAIL` or `NEEDS_EVIDENCE`, or required authorization is unavailable.

## Execution Plan

See [PLAN.md](PLAN.md).

## Evidence

See [EVIDENCE.md](EVIDENCE.md).
