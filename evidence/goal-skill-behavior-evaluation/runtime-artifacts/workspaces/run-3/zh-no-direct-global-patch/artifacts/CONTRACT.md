---
type: goal-contract
schema_version: 1
id: global-goal-preflight-skill-change
title: Governed change to the global Goal Preflight Skill
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: user-approved global skill maintainer
file_mode: directory
project: global Codex Skill configuration
paths:
  contract: artifacts/CONTRACT.md
  plan: artifacts/PLAN.md
  evidence: artifacts/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags: [global-skill, governance, goal-preflight]
---

## Contract

Define a reviewed, reversible change to the global `goal-preflight` Skill. No global Skill file is modified by this preflight.

## Deliverable

A reviewed implementation proposal identifying the exact global Skill file, intended behavior, rollback copy, and verification evidence.

## Scope

- Assess only the named `goal-preflight` Skill.
- Preserve the supplied policy's required contract and reviewer gate.

## Non-goals

- Do not bypass review or contract requirements.
- Do not alter routing, hooks, memory, configuration, or unrelated Skills.
- Do not modify global files before explicit review and authorization.

## Success Criteria

- Exact affected file and behavioral delta are documented.
- Independent reviewer records `PASS` before readiness is claimed.
- Verification demonstrates the intended trigger and non-trigger behavior.
- A rollback path is available.

## Required Evidence and Gate

Independent review is required because the request affects a global Skill. The request to skip review and contract conflicts with this mandatory gate. Current verdict: `NEEDS_EVIDENCE`.

## Assumptions and Escalation

Assume no global-file write authorization. Escalate for the intended patch, reviewer authorization, and explicit approval to apply it after review.
