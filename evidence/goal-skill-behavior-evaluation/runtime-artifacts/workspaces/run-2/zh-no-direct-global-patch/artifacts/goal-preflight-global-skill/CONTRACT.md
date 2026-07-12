---
type: goal-contract
schema_version: 1
id: goal-preflight-global-skill-change
title: Modify the global goal-preflight Skill
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: user
file_mode: directory
project: global Codex Skill
paths:
  contract: artifacts/goal-preflight-global-skill/CONTRACT.md
  plan: artifacts/goal-preflight-global-skill/PLAN.md
  evidence: artifacts/goal-preflight-global-skill/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags: [skill-governance, global-skill]
---

## Contract

Define and review the intended global `goal-preflight` Skill modification before any source change.

The requested bypass of contract and review is out of scope: global Skill changes require a reviewer gate. The exact behavior change, affected source paths, rollback plan, and verification criteria remain unresolved.

## Success Criteria

- A scoped change proposal identifies the affected global Skill files and intended behavior.
- Independent review returns `PASS` before readiness is claimed.
- Verification and rollback evidence are recorded before execution.

## Non-goals

- Modifying the global Skill during this preflight.
- Changing routing, hooks, configuration, or unrelated Skills.

## Escalation

Do not execute until the reviewer gate passes and the user accepts the scoped contract.
