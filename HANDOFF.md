# Handoff: Goal Life Cycle / Central Goal State Index

Date: 2026-07-07

## Conversation Summary

The user explored whether `goal-preflight` should have a central state index similar to CBM or CodeGraph.

Settled points:

- A centralized STATE is useful.
- The STATE should be a derived index/dashboard, not the canonical truth.
- Goal Contract, PLAN, and EVIDENCE frontmatter remain source of truth.
- Repo-local work can still keep files in `<repo>/goals/active/` and `<repo>/goals/completed/`.
- A global index can live separately and point to known goal roots.
- A registry should avoid scanning the entire machine.
- Reconcile-first is safer than watcher-first.
- File-change maintenance can come later as an incremental accelerator.

## Proposed Architecture

```text
<repo>/goals/
  active/
  completed/

central index project / runtime state:
  STATE.json
  STATE.md
  REGISTRY.json
```

`REGISTRY.json` lists known goal roots. The reconciler scans only those roots.

## Index Semantics

STATE entries should include:

- `id`
- `title`
- `status`
- `project`
- `goal_root`
- `contract_path`
- `owner`
- `updated`
- `review.required`
- `review.verdict`
- `evidence.status`
- `next_action`
- `blocked_reason`
- `source_hash`
- `last_seen`
- detected issues such as `missing`, `stale`, or `status_folder_mismatch`

## Execution Recommendation

Start with a read-only reconciler:

1. Read registry.
2. Scan each registered `active/` and `completed/` tree.
3. Parse YAML frontmatter.
4. Emit centralized `STATE.json`.
5. Render `STATE.md`.
6. Flag mismatches and stale entries.

After that passes fixture tests, add file-change based incremental maintenance with debounce and reconcile fallback.

## Governance Boundary

This project is a harness/prototype. It does not authorize edits to global skills, hooks, RTK, Codex config, memory stores, or watcher services.

Before changing `goal-preflight` or global workflow behavior, use the review-first gate:

1. proposal
2. independent review
3. explicit approval
4. patch
5. verification

## 2026-07-11 Session Wrap-Up

### Done

- Delivered the lightweight Windows Goal Control desktop dashboard and packaged it under `dist/goal-dashboard/GoalControl/`.
- Changed the primary information hierarchy to Repository → queue-ordered Goals instead of one flat global Goal list.
- Added an in-app language setting with Traditional Chinese as the default and English as the alternate locale.
- Created a Windows desktop shortcut named `Goal Control.lnk` that targets the packaged executable.
- Verified the final implementation with 138 passing tests and a successful 29.6 MB packaged build.

### Commits

- `354c624 Build lightweight Goal Control desktop dashboard`
- `f258029 Group Goal dashboard by repository`
- `b3bf9d1 Add Traditional Chinese dashboard locale`

### Current State

- Branch: `master`
- Main worktree: `C:\devhome\goal life cycle`
- Product work is committed; generated packages and visual QA captures remain ignored.
- `outputs/ONBOARDING.json` plus `outputs/global/STATE.json` currently produce the session-handoff fallback `resume_unsupported`; do not mutate lifecycle sources merely to repair the fast path.

### Next

- Refresh the explicit onboarding report and matching validated aggregate only through the normal lifecycle workflow when resuming Goal work.
- Re-evaluate the canonical next Goal from fresh STATE before starting implementation; the stale fallback currently names `multi-repo-goal-onboarding`, which is already completed in source.

## 2026-07-13 Session Wrap-Up

### Done

- Completed `agentgoals-product-rename`: Contract, PLAN, and EVIDENCE are marked completed/PASS.
- Ran `agentgoals complete` successfully: the Goal moved from `goals/active/` to `goals/completed/` and refresh ran exactly once.
- Verified derived STATE: 18 total Goals, 4 open, 14 completed; local and global validation passed.
- Installed AgentGoals `0.2.1` and aligned Codex Skill UI display names to `AG Contract`, `AG Onboarding`, `AG Continue`, and `AG End`; legacy Skills remain preserved.

### Commits

- `9732555 Complete AgentGoals product rename goal` (local completion migration; not yet pushed)
- `c4da014 Align Codex Skill display names` (pushed)
- `f71dde2 Add deterministic completion refresh transaction` (pushed)

### Current State

- Branch: `main`
- Worktree: clean.
- Dashboard STATE operation: `eae0b206c84c49179d7d1bf2b163f5f3`, generated `2026-07-13T05:18:59+00:00`.
- Refresh reports six issues belonging to the four remaining open Goals; they do not invalidate the completed rename Goal.
- `session_handoff` returned fallback `no_valid_candidate` / `resume_unsupported`; no source mutation was made to repair the handoff fast path.

### Next

- If remote synchronization is desired, explicitly authorize pushing `9732555` from `C:\devhome\goal life cycle`.
- Next planned lifecycle work is governed by fresh STATE queue output; the four remaining open Goals still have evidence/review gates.

### Memory Triage

- AgentMemory: skipped; no new cross-project preference or durable global routing rule was created.
- Link: skipped; this is a repo-local completion handoff and no Link integration was available.
- Obsidian Skill Wiki: skipped; no human-readable cross-project concept warranted a vault note.
- Synto: skipped; no raw knowledge extraction operation was authorized or needed.
- Handoff-only: completion commit, refresh issue summary, fallback reason, and explicit next push gate.
