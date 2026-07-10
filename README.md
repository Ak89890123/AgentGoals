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

- `goals/completed/codex-skill-optimization/CONTRACT.md`
- `goals/completed/codex-skill-optimization/PLAN.md`
- `goals/completed/codex-skill-optimization/EVIDENCE.md`

The first bounded subgoal is the central Goal State Index:

1. Define the central STATE and REGISTRY schemas.
2. Create fixtures that mimic repo-local and global goal roots.
3. Implement a read-only reconcile command that rebuilds STATE from frontmatter.
4. Only after reconcile is reliable, evaluate file-change based maintenance.

The global `goal-preflight` skill patch has already passed proposal, independent review, explicit approval, patch, and verification. The read-only lifecycle harness has also passed production-readiness review for `production_read_only` operator use.

The current production model is read-only and federated: each repo generates its own derived STATE, and the reviewed central global `.codex` registry aggregates registered repo STATE outputs. This is the current operator model, not a writer, watcher, or background automation approval.

STATE version 2 adds deterministic scheduling. Goal Contracts may declare `scheduling.priority` and `scheduling.depends_on`; repo-local and global STATE derive canonical Goal keys, dependency status, queue positions, `next_goal`, and `next_planned_goal`. Dependencies always take precedence over priority.

The global registry patch is complete at `C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json`. Additional global `.codex` writes still require a separate proposal, independent review, explicit approval, patch, and verification.

Multi-repo onboarding is available as an explicit, dry-run-first command. It writes only inside the supplied repository after `--apply`, emits a global-registration proposal instead of applying it, and can verify an already-registered repo in a derived global aggregate. See `docs/onboarding.md`.

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

## Goal Queue

Query an existing derived STATE without modifying source files:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.queue --state outputs\STATE.json
```

Query the current global queue directly from registered repo STATE files without writing aggregate output:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.queue `
  --registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --json
```

Check or apply onboarding for one explicit repository:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.onboard --repo C:\devhome\legacy-repo --json
.\.venv\Scripts\python -m goal_lifecycle.onboard --repo C:\devhome\legacy-repo --apply --json
```

Source scheduling metadata belongs in Contract frontmatter:

```yaml
scheduling:
  priority: 80
  depends_on:
    - another-goal
    - another-repo/cross-repo-goal
```

Priority ranges from `0` through `100`; higher values run first among dependency-safe peers. A bare dependency resolves within the same registered root. `queue_position` is always derived and must not be written into a Contract.

## Deterministic Run

Run the local read-only pipeline with one command:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.run --registry registry/REGISTRY.json --out outputs
```

Add the reviewed global registry to continue through global aggregation and validation:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.run `
  --registry registry/REGISTRY.json `
  --out outputs `
  --global-registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --global-out outputs\global `
  --json
```

The command runs four deterministic stages: `reconcile`, `validate_local`, `aggregate`, and `validate_global`. Global stages are marked `skipped` when no global registry is supplied. Exit codes are:

- `0`: all configured stages passed with no lifecycle issues;
- `1`: an operational or schema-validation stage failed;
- `2`: configured stages completed, but generated STATE contains lifecycle issues.

Use `--json` for a versioned compact summary containing stage status, output paths, entry counts, issue counts, and failure or skip details.

The orchestrator rejects `--out` and configured global output paths under the user's global `.codex` directory.

## Session Handoff

Validate a fresh onboarding report and matching global STATE into compact close/resume context:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.session_handoff `
  --report outputs\ONBOARDING.json `
  --state outputs\global\STATE.json
```

Exit code `0` returns a versioned fast-path focus with lifecycle, review, evidence, health, source-path, and exact-gate fields. Exit code `2` returns a named fallback reason and preserves the existing read-only repository scan. The caller must still confirm source Contract frontmatter and inspect Git state. See `docs/session-handoff.md`.

## Non-goals

- Do not make additional global `.codex` edits without a new proposal, independent review, explicit approval, patch, and verification.
- Do not add long-running watchers as the first implementation step.
- Do not treat STATE as the source of truth.
- Do not scan the whole disk for goals.

## Key Files

- `HANDOFF.md`: conversation handoff and settled decisions.
- `goals/completed/codex-skill-optimization/CONTRACT.md`: umbrella contract for the full CODEX Skill optimization effort.
- `goals/completed/codex-skill-optimization/PLAN.md`: umbrella execution plan.
- `goals/completed/codex-skill-optimization/EVIDENCE.md`: umbrella verification/evidence log.
- `goals/completed/goal-state-index/CONTRACT.md`: completed project contract.
- `goals/completed/goal-state-index/PLAN.md`: completed execution plan.
- `goals/completed/goal-state-index/EVIDENCE.md`: completed verification/evidence log.
- `goals/completed/production-state-location/`: production STATE topology decision and global registry patch evidence.
- `docs/design.md`: system design notes.
- `docs/usage.md`: operator flow and safe-use boundaries.
- `docs/session-handoff.md`: deterministic session close/resume protocol and fallback rules.
- `docs/production-readiness.md`: read-only production review packet.
- `docs/production-state-topology.md`: federated repo-local STATE and global registry topology.
- `goals/completed/deterministic-lifecycle-orchestration/`: completed implementation goal for the deterministic single-command operator flow.
- `goals/completed/global-goal-queue-scheduling/`: completed STATE v2 scheduling model and deterministic local/global Goal queue.
- `docs/proposals/global-goal-registry.md`: proposed global `.codex` registry creation gate.
- `docs/global-registry-schema-notes.md`: schema notes for federated aggregation registry entries.
- `schemas/global-registry.schema.json`: executable schema for global registry entries.
- `docs/references/`: reference inputs for future skill and lifecycle design.
- `docs/proposals/`: gated change proposals for future global skill work.
- `schemas/`: draft schema notes for STATE and REGISTRY.
- `fixtures/`: sample goal roots for tests.
