# Goal Life Cycle

This project prototypes a centralized Goal State Index for Goal Contract, Plan, and Evidence files.

The central idea:

- Goal Contract / PLAN / EVIDENCE files remain the source of truth.
- A centralized STATE is a derived index, similar in spirit to CBM or CodeGraph indexes.
- Repo-local goals can live under each repo's `goals/active/` and `goals/completed/`.
- The global index records known goal roots and summarizes open, blocked, review-pending, and completed work.

## Current Scope

Build a small harness before changing the global `goal-preflight` skill.

The umbrella effort is tracked at:

- `goals/active/codex-skill-optimization/CONTRACT.md`
- `goals/active/codex-skill-optimization/PLAN.md`
- `goals/active/codex-skill-optimization/EVIDENCE.md`

The first bounded subgoal is the central Goal State Index:

1. Define the central STATE and REGISTRY schemas.
2. Create fixtures that mimic repo-local and global goal roots.
3. Implement a read-only reconcile command that rebuilds STATE from frontmatter.
4. Only after reconcile is reliable, evaluate file-change based maintenance.

## Python Setup

Use a repo-local virtual environment:

```powershell
python -m venv .venv
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pytest
```

Runtime and test dependencies are intentionally small: `PyYAML` for frontmatter parsing and `pytest` for fixture-driven validation.
`.tmp/` is ignored and can be used as repo-local temp storage when the system temp directory is unavailable from the sandbox. Pytest is configured with `-s -p no:cacheprovider` to avoid tempfile-backed output capture and cache writes in this environment.

## Non-goals

- Do not edit `C:\Users\jimmy0302\.codex\skills\goal-preflight` yet.
- Do not add long-running watchers as the first implementation step.
- Do not treat STATE as the source of truth.
- Do not scan the whole disk for goals.

## Key Files

- `HANDOFF.md`: conversation handoff and settled decisions.
- `goals/active/codex-skill-optimization/CONTRACT.md`: umbrella contract for the full CODEX Skill optimization effort.
- `goals/active/codex-skill-optimization/PLAN.md`: umbrella execution plan.
- `goals/active/codex-skill-optimization/EVIDENCE.md`: umbrella verification/evidence log.
- `goals/active/goal-state-index/CONTRACT.md`: project contract.
- `goals/active/goal-state-index/PLAN.md`: execution plan.
- `goals/active/goal-state-index/EVIDENCE.md`: verification/evidence log.
- `docs/design.md`: system design notes.
- `docs/references/`: reference inputs for future skill and lifecycle design.
- `schemas/`: draft schema notes for STATE and REGISTRY.
- `fixtures/`: sample goal roots for tests.
