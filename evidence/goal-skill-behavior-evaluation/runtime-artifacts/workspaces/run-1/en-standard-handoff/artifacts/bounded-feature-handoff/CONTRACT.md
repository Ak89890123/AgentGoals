---
type: goal-contract
schema_version: 1
id: bounded-feature-handoff
title: Bounded Feature Implementation Handoff
status: draft
created: 2026-07-11
updated: 2026-07-11
completed:
owner: unassigned-next-engineer
file_mode: directory
project: isolated-behavior-evaluation-runtime
paths:
  contract: artifacts/bounded-feature-handoff/CONTRACT.md
  plan: artifacts/bounded-feature-handoff/PLAN.md
  evidence: artifacts/bounded-feature-handoff/EVIDENCE.md
review:
  required: false
  verdict: pending
tags: [handoff, bounded-feature, incomplete-brief]
---

# Goal Contract: Bounded Feature Implementation Handoff

## Contract

### Goal

Provide a durable, implementation-ready handoff for the bounded feature the user intends to specify.

### Deliverable

A completed contract, execution plan, and evidence record that identify the feature, its target location, acceptance criteria, and verification evidence.

### Success Criteria

- The feature outcome and target project or component are explicitly identified.
- Scope, non-goals, compatibility constraints, and acceptance criteria are agreed.
- The next engineer has an executable plan and a concrete verification method.

### Scope

Included:

- Capturing the requested bounded feature once its details are supplied.
- Defining implementation and verification requirements for the next engineer.

Not included:

- Implementing, deploying, or reviewing an unspecified feature.
- Inferring product, security, or compatibility requirements not provided by the user.

### Rubric

- Correctness: requirements are testable and unambiguous.
- Completeness: outcome, boundaries, and evidence are all specified.
- Handoff quality: a new engineer can begin without material guessing.

### Constraints

- Durable artifacts are confined to `./artifacts` in this evaluation runtime.
- No source files are changed by this preflight artifact.

### Routing

- Task size: goal-grade
- Primary owner: unassigned next engineer
- Supporting roles: product or technical requester for missing requirements
- Skipped but considered: independent review; not required for an ordinary bounded feature unless its eventual scope triggers a reviewer gate.

### Required Evidence

- Feature-specific acceptance verification, such as automated test output, QA steps, or an inspected artifact.

### Reviewer Gate

- Required: no, unless the supplied feature affects security, permissions, release, data integrity, or another policy-triggered area.
- Verdict: pending
- Remaining risk: the feature itself has not been described.

### Assumptions

- The request is for preflight only, not implementation.
- A directory-mode handoff is appropriate because a future engineer will consume and update separate contract, plan, and evidence records.

### Escalation Rules

Stop and request direction if the feature introduces security, privacy, data migration, deployment, permissions, or irreversible behavior.

## Open Requirement

The user has not supplied the bounded feature. Before this draft can become ready, provide the target outcome, affected project or component, and observable acceptance criteria.
