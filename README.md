# Goal Life Cycle

This project prototypes a centralized Goal State Index for Goal Contract, Plan, and Evidence files.

The central idea:

- Goal Contract / PLAN / EVIDENCE files remain the source of truth.
- A centralized STATE is a derived index, similar in spirit to CBM or CodeGraph indexes.
- Repo-local goals can live under each repo's `goals/active/` and `goals/completed/`.
- The global index records known goal roots and summarizes open, blocked, review-pending, and completed work.

## Current Scope

Build a small read-only harness for Goal Contract lifecycle tracking and use it to gate skill-workflow changes.

The umbrella effort is tracked at:

- `goals/active/codex-skill-optimization/CONTRACT.md`
- `goals/active/codex-skill-optimization/PLAN.md`
- `goals/active/codex-skill-optimization/EVIDENCE.md`

The first bounded subgoal is the central Goal State Index:

1. Define the central STATE and REGISTRY schemas.
2. Create fixtures that mimic repo-local and global goal roots.
3. Implement a read-only reconcile command that rebuilds STATE from frontmatter.
4. Only after reconcile is reliable, evaluate file-change based maintenance.

The global `goal-preflight` skill patch has already passed proposal, independent review, explicit approval, patch, and verification. The read-only lifecycle harness has also passed production-readiness review for `production_read_only` operator use.

The current production model is read-only and federated: each repo generates its own derived STATE, and the reviewed central global `.codex` registry aggregates registered repo STATE outputs. This is the current operator model, not a writer, watcher, or background automation approval.

The global registry patch is complete at `C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json`. Additional global `.codex` writes still require a separate proposal, independent review, explicit approval, patch, and verification.

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

## Reconcile

Run the read-only reconciler:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry/REGISTRY.json --out outputs
```

The command scans only registered roots, reads Goal Contract / PLAN / EVIDENCE frontmatter, and writes derived `outputs/STATE.json` and `outputs/STATE.md`.

Validate registry and STATE JSON:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry/REGISTRY.json --state outputs/STATE.json
```

## Global Aggregate

Run the read-only global aggregator against the reviewed global registry:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.aggregate --registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json --out outputs\global
.\.venv\Scripts\python -m goal_lifecycle.validate --state outputs\global\STATE.json
```

The aggregator reads only registered absolute `state_path` files and writes only the requested output directory. Missing or malformed repo STATE files become aggregate issues. Repo-local relative entry paths are rebased against the registered `repo_root` and must remain under the registered `goal_root`.

## Non-goals

- Do not make additional global `.codex` edits without a new proposal, independent review, explicit approval, patch, and verification.
- Do not add long-running watchers as the first implementation step.
- Do not treat STATE as the source of truth.
- Do not scan the whole disk for goals.

## Key Files

- `HANDOFF.md`: conversation handoff and settled decisions.
- `goals/active/codex-skill-optimization/CONTRACT.md`: umbrella contract for the full CODEX Skill optimization effort.
- `goals/active/codex-skill-optimization/PLAN.md`: umbrella execution plan.
- `goals/active/codex-skill-optimization/EVIDENCE.md`: umbrella verification/evidence log.
- `goals/completed/goal-state-index/CONTRACT.md`: completed project contract.
- `goals/completed/goal-state-index/PLAN.md`: completed execution plan.
- `goals/completed/goal-state-index/EVIDENCE.md`: completed verification/evidence log.
- `goals/completed/production-state-location/`: production STATE topology decision and global registry patch evidence.
- `docs/design.md`: system design notes.
- `docs/usage.md`: operator flow and safe-use boundaries.
- `docs/production-readiness.md`: read-only production review packet.
- `docs/production-state-topology.md`: federated repo-local STATE and global registry topology.
- `docs/proposals/global-goal-registry.md`: proposed global `.codex` registry creation gate.
- `docs/global-registry-schema-notes.md`: schema notes for federated aggregation registry entries.
- `schemas/global-registry.schema.json`: executable schema for global registry entries.
- `docs/references/`: reference inputs for future skill and lifecycle design.
- `docs/proposals/`: gated change proposals for future global skill work.
- `schemas/`: draft schema notes for STATE and REGISTRY.
- `fixtures/`: sample goal roots for tests.
