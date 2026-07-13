---
type: reference
schema_version: 1
id: skill-evaluation-reference-split
title: Skill Evaluation Reference Split
source_path: <reference-source-path>
created: 2026-07-07
updated: 2026-07-07
tags:
  - goal-preflight
  - skill-governance
  - references
  - handoff
---

# Skill Evaluation Reference Split

## Purpose

Capture the handoff recommendation from `技能評估建議.md` as one reference input for the Goal Life Cycle harness.

This document is not an instruction to edit the global `goal-preflight` skill. It records reference design guidance that can be consulted when deciding how reusable Goal Contract templates, acceptance modules, and local routing conventions should be split out of a skill body.

## Source Summary

The source evaluates a `goal-preflight` style skill as mature and useful, with strongest value in:

- clear trigger boundaries;
- size-based output levels;
- durable Goal Contract / Plan / Evidence files;
- reviewer gates for global workflow or governance changes;
- explicit file lifecycle and frontmatter metadata.

The source also identifies cleanup areas:

- clarify that explicit trigger does not require exact keywords;
- keep machine-readable statuses lowercase snake_case;
- define a no-write fallback that returns an unsaved draft and intended path;
- add examples for `small`, `standard`, and `goal-grade`;
- centralize fallbacks for unavailable reviewers, files, or references.

## Reference Split Recommendation

Keep core decision rules in the main skill:

- trigger policy;
- size classification;
- status conventions;
- file output rules;
- reviewer gate;
- fallback behavior.

Move heavier reusable material into references that are loaded only when relevant:

- `goal-contract-template.md` for full contracts, handoff files, goal-grade contracts, and directory-mode `CONTRACT.md`;
- `acceptance-modules.md` for domain-specific acceptance criteria and evidence checklists;
- `plan-template.md` for directory-mode or explicitly requested `PLAN.md`;
- `evidence-template.md` for directory-mode or evidence-heavy goals;
- `ai-company-os-routing.md` only for local department-agent or CEO-routing conventions.

## Load Policy

Do not load reference files just to browse options. Load a reference only when the current task clearly needs that template, checklist, or local routing convention.

Reference content must not be treated as runtime capability. If a reference mentions reviewers, roles, tools, models, or routing paths, the active environment still determines what is actually available.

## Applicability To This Harness

This project can use the source as design input when modeling:

- central Goal Contract lifecycle metadata;
- reference-aware `goal-preflight` governance;
- derived state fields for reviewer state, evidence state, and fallback state;
- future reference files under a skill package.

Before applying these recommendations to global skills or always-on workflow behavior, follow the project gate:

1. proposal;
2. independent review;
3. explicit approval;
4. patch;
5. verification.
