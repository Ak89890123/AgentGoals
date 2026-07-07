# Repository Instructions

## Project Structure & Module Organization

This repository is a harness for CODEX Skill lifecycle work, centered on Goal Contract, Plan, and Evidence files.

- `goals/active/codex-skill-optimization/` is the umbrella goal for the full CODEX Skill optimization effort.
- `goals/active/goal-state-index/` is the first bounded subgoal for central STATE / REGISTRY / reconciler design.
- `docs/design.md` describes the central Goal State Index architecture.
- `docs/references/` stores reference inputs for future skill and lifecycle design.
- `schemas/` contains draft STATE and REGISTRY schema notes.
- `fixtures/` is reserved for synthetic goal roots used by reconciler tests.
- `src/goal_lifecycle/` contains the read-only reconciler, validator, renderer, and global aggregator.
- `.omo/evidence/` contains independent review reports for aggregator readiness.

Goal Contract, PLAN, and EVIDENCE files are the authoritative source. A generated central STATE must be treated as a derived index or dashboard only.

## Development Commands

This repo uses Python 3.11 with a repo-local virtual environment.

Setup and validation:

- `python -m venv .venv`
- `$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP`
- `.\.venv\Scripts\python -m pip install -r requirements.txt`
- `.\.venv\Scripts\python -m pytest`
- `$env:PYTHONPATH=(Resolve-Path src).Path`
- `.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry/REGISTRY.json --out outputs`
- `.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry/REGISTRY.json --state outputs/STATE.json`
- `.\.venv\Scripts\python -m goal_lifecycle.aggregate --registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json --out outputs\global`
- `.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry/REGISTRY.json --state outputs\global\STATE.json`

Useful read-only checks:

- `rg --files`
- `git status --short`
- `Get-Content -LiteralPath <path> -Encoding UTF8`

## Coding Style & File Conventions

- Use UTF-8 for all Markdown, schema, fixture, and generated state files.
- Keep YAML frontmatter machine-readable; keep prose in the body.
- Use lowercase snake_case for machine status values such as `review_pending`, `in_progress`, and `completed`.
- Keep goal IDs stable and kebab-case.
- Do not duplicate frontmatter metadata in body sections.
- Prefer concise, file-backed guidance over generic process text.
- Put reusable Python code under `src/goal_lifecycle/` and tests under `tests/`.
- Generated `outputs/STATE.json`, `outputs/STATE.md`, and `outputs/global/STATE.*` are ignored because STATE is derived.

Directory-mode goals should use:

```text
goals/active/<subject>/
  CONTRACT.md
  PLAN.md
  EVIDENCE.md
```

## Testing Guidelines

The reconciler and global aggregator are read-only operators.

Run the current test suite with:

- `$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP`
- `.\.venv\Scripts\python -m pytest`

Pytest is configured with `-s -p no:cacheprovider` in `pyproject.toml` because tempfile-backed output capture and cache writes are unreliable in this sandbox.

Expected validation path:

1. Read a REGISTRY file.
2. Scan only registered active roots.
3. Parse Goal Contract / Plan / Evidence frontmatter.
4. Emit derived STATE outputs.
5. Flag mismatches such as missing files, parse errors, stale entries, evidence gaps, and status-folder mismatches.

Global aggregation validation path:

1. Read only the supplied global registry.
2. Require global `repo_root`, `goal_root`, and `state_path` to be absolute paths.
3. Require global `goal_root` and `state_path` to stay under `repo_root`.
4. Read only active registered `state_path` files.
5. Validate each repo-local STATE before merging.
6. Rebase repo-local relative STATE entry paths against registered `repo_root`.
7. Require aggregate entry source paths to stay under registered `goal_root`.
8. Emit derived global STATE outputs under the requested output directory.
9. Report missing, malformed, BOM-encoded, or out-of-scope repo STATE as aggregate issues without source mutation.

Fixtures should cover active draft, review pending, in progress, blocked, completed, status/folder mismatch, missing evidence, parse error cases, missing/malformed repo STATE, inactive global roots, relative path rejection, path escape rejection, UTF-8 BOM handling, and multi-root duplicate goal IDs.

## Commit & Review Guidelines

- Keep commits scoped to one lifecycle step, such as baseline docs, schema updates, fixture additions, or reconciler implementation.
- Before committing, run `git status --short` and inspect the staged diff.
- Do not claim readiness for global skill changes until reviewer evidence is recorded.
- The baseline commit is `4719cb5 Initialize goal lifecycle harness`.
- Current read-only global aggregator hardening is recorded through `e14a55f Record global aggregator hardening review`.

## Security & Configuration Tips

- Do not edit `C:\Users\jimmy0302\.codex\skills\goal-preflight` from this harness until there is a proposal, independent review, explicit approval, patch, and verification.
- Do not edit RTK, hooks, routing, memory stores, Codex config, or always-on workflow behavior without separate approval.
- Do not scan the whole disk for goals; scan only repo-local registered goal roots or global registered STATE paths.
- Do not start long-running watchers from Codex shell during the read-only lifecycle phase.
- Do not treat a registry entry as permission to mutate source goal files.
- Do not write under `C:\Users\jimmy0302\.codex` from this repo without proposal, independent review, explicit approval, patch, and verification. The existing global registry path is `C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json`.
