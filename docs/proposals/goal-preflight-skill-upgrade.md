---
type: skill-change-proposal
schema_version: 1
id: goal-preflight-skill-upgrade
title: Goal Preflight Skill Upgrade Proposal
status: review_passed
created: 2026-07-07
updated: 2026-07-07
target_skill: C:\Users\jimmy0302\.codex\skills\goal-preflight
review:
  required: true
  verdict: PASS
approval:
  required_before_patch: true
  token: APPROVE_GOAL_PREFLIGHT_SKILL_UPGRADE_PATCH
tags:
  - goal-preflight
  - skill-governance
  - global-skill
  - proposal
---

# Goal Preflight Skill Upgrade Proposal

## Purpose

Propose a narrow, review-gated upgrade to the global `goal-preflight` skill using evidence from this harness.

This proposal does not authorize or perform mutation of `C:\Users\jimmy0302\.codex\skills\goal-preflight`. It defines the patch scope that should go to independent review before any global file is edited.

## Baseline

Target files:

- `C:\Users\jimmy0302\.codex\skills\goal-preflight\SKILL.md`
- `C:\Users\jimmy0302\.codex\skills\goal-preflight\references\goal-contract-template.md`
- `C:\Users\jimmy0302\.codex\skills\goal-preflight\references\plan-template.md`
- `C:\Users\jimmy0302\.codex\skills\goal-preflight\references\evidence-template.md`
- `C:\Users\jimmy0302\.codex\skills\goal-preflight\references\acceptance-modules.md`
- `C:\Users\jimmy0302\.codex\skills\goal-preflight\references\ai-company-os-routing.md`

Current `SKILL.md` SHA-256:

```text
88911283B9EA37B28A39C6B677115203437F7CA097C75597B48294A7C65B06BA
```

Current reference hashes:

```text
goal-contract-template.md: 1FE444C02A54B3FB73DE393A045B5AB9A5FAEE3D4A4B59C2C1AE5FDFB239147E
plan-template.md:          811BFF3C8804AFD59C2E8AEBAF6DC8DE0BCC02DD037B2236E6ACE761239EB832
evidence-template.md:      CD06903A0A40B5CBA5E448831A85E51BB0C89E22495F6600F5E23F8962D9FBB6
acceptance-modules.md:     86805846372132BDF9E3E01F8D1AB2D9647F3B9200F743689E96221C493F52BD
ai-company-os-routing.md:  4CA3695B6DBC0E5C92F33E79649C6697F34DED941C33BEA50C9D9E46A5AD8415
```

## Proposed Changes

### 1. Clarify Trigger Policy

Patch `SKILL.md` so explicit trigger means explicit intent, not exact keywords.

Proposed behavior:

- Use when the user explicitly asks to define, clarify, contract, scope, hand off, set acceptance criteria, or prepare durable execution state before execution.
- Exact phrases like `Goal Contract` or `preflight` are sufficient but not required.
- Do not trigger for ordinary work merely because it is long or complex.

Reason:

- The source reference identified a small ambiguity between exact-keyword trigger and natural-language requests to clarify broad goals.

### 2. Standardize Machine Status Values

Patch lifecycle/status prose to say machine-readable values must always be lowercase snake_case.

Proposed behavior:

- Frontmatter values: `draft`, `review_pending`, `ready`, `in_progress`, `blocked`, `completed`, `cancelled`.
- Human labels may be capitalized only in prose.

Reason:

- The harness reconciler and JSON Schema rely on stable lowercase status values.

### 3. Add No-Write Fallback

Patch file output rules with a clear fallback for unavailable filesystem access.

Proposed behavior:

- If writing is unavailable, return the contract in chat.
- Mark it `unsaved_draft`.
- Include the intended path.
- Do not claim durable state exists until the file is actually written.

Reason:

- This prevents false durable-state claims when the active workspace or target path is not writable.

### 4. Tighten Reference Load Policy

Patch load policy to explicitly avoid browsing reference files merely to see options.

Proposed behavior:

- Load reference files only when the selected output path clearly requires that template, checklist, or local routing convention.
- Reference content cannot imply tool, reviewer, model, or role availability.

Reason:

- This keeps the skill light and matches the reference-split guidance captured in this repo.

### 5. Add Size Classification Examples

Patch size classification with short examples.

Proposed examples:

- `small`: write five acceptance criteria for a narrow task.
- `standard`: create a bounded execution contract for one feature.
- `goal-grade`: change global skill routing, memory governance, release policy, cross-repo migration, or durable workflow behavior.

Reason:

- The current distinction is sound but can be easier for future agents to apply consistently.

### 6. Add State Index Compatibility Note

Patch goal metadata/lifecycle guidance to mention that goal files may be reconciled into a derived STATE index.

Proposed behavior:

- Goal Contract / PLAN / EVIDENCE files remain authoritative.
- A central STATE index, if present, is derived and should be repaired from source files when inconsistent.
- Do not scan unregistered roots.
- Do not mutate source goal files during read-only reconcile.

Reason:

- This harness now has a tested read-only reconciler, JSON Schema validation, and generated STATE output.

## Non-Goals

- Do not change RTK, hooks, `AGENTS.md`, memory governance, routing rules, model/provider config, or watcher services.
- Do not start or install a long-running watcher.
- Do not move existing global skill backup files.
- Do not rewrite the skill architecture wholesale.
- Do not add this harness as a runtime dependency of `goal-preflight`.

## Backup And Rollback

Before patching, create timestamped backups for every edited global file.

Minimum backup targets:

- `C:\Users\jimmy0302\.codex\skills\goal-preflight\SKILL.md`
- Any reference file edited by the approved patch.

Rollback:

- Restore the timestamped backup files.
- Re-run hash checks and skill frontmatter parse checks.
- Re-run local harness validation if state-index instructions changed.

## Verification Plan

Before patch:

1. Confirm baseline hashes still match this proposal.
2. Run independent review on this proposal.
3. Wait for explicit human approval token: `APPROVE_GOAL_PREFLIGHT_SKILL_UPGRADE_PATCH`.

After approved patch:

1. Verify edited Markdown files are UTF-8 readable.
2. Verify `goal-preflight/SKILL.md` frontmatter still parses.
3. Verify reference links named in load policy exist.
4. Confirm no RTK, hooks, routing, memory, provider, or config files changed.
5. Run this harness:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pytest
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry/REGISTRY.json --out outputs
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry/REGISTRY.json --state outputs/STATE.json
```

## Reviewer Gate

Reviewer is required before global mutation.

Reviewer should check:

- Whether proposed changes are narrow enough.
- Whether trigger language still prevents over-triggering.
- Whether file fallback avoids false durable-state claims.
- Whether status values align with schema/reconciler.
- Whether state-index notes preserve source-of-truth boundaries.
- Whether backup, rollback, and verification are sufficient.

Reviewer verdict must be one of:

- `PASS`
- `FAIL`
- `NEEDS_EVIDENCE`

Current verdict: `PASS`

Reviewer: `codex_harness_master` / Pasteur (`019f3a8e-ed40-7481-801a-011986faf755`)

Reviewer finding:

- No blocking findings.
- Low severity: the proposal lists the full `goal-preflight` package as target files rather than the exact final edited subset. Patch step must report exact edited files before applying.

## Approval Boundary

The next gate is independent review of this proposal.
Independent review has passed.

Even after review passes, patching global files requires this exact approval token:

```text
APPROVE_GOAL_PREFLIGHT_SKILL_UPGRADE_PATCH
```

Approval is scoped only to `goal-preflight` files explicitly listed in this proposal. It does not approve RTK, hooks, routing, memory governance, provider/model config, or watcher changes.
