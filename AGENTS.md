# Repository Instructions

## Project Structure & Module Organization

This repository is a harness for CODEX Skill lifecycle work, centered on Goal Contract, Plan, and Evidence files.

- `goals/active/codex-skill-optimization/` is the umbrella goal for the full CODEX Skill optimization effort.
- `goals/active/goal-state-index/` is the first bounded subgoal for central STATE / REGISTRY / reconciler design.
- `docs/design.md` describes the central Goal State Index architecture.
- `docs/references/` stores reference inputs for future skill and lifecycle design.
- `schemas/` contains draft STATE and REGISTRY schema notes.
- `fixtures/` is reserved for synthetic goal roots used by reconciler tests.

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
- Generated `outputs/STATE.json` and `outputs/STATE.md` are ignored because STATE is derived.

Directory-mode goals should use:

```text
goals/active/<subject>/
  CONTRACT.md
  PLAN.md
  EVIDENCE.md
```

## Testing Guidelines

The reconciler should be developed read-only first.

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

Fixtures should cover active draft, review pending, in progress, blocked, completed, status/folder mismatch, missing evidence, and parse error cases.

## Commit & Review Guidelines

- Keep commits scoped to one lifecycle step, such as baseline docs, schema updates, fixture additions, or reconciler implementation.
- Before committing, run `git status --short` and inspect the staged diff.
- Do not claim readiness for global skill changes until reviewer evidence is recorded.
- The baseline commit is `4719cb5 Initialize goal lifecycle harness`.

## Security & Configuration Tips

- Do not edit `C:\Users\jimmy0302\.codex\skills\goal-preflight` from this harness until there is a proposal, independent review, explicit approval, patch, and verification.
- Do not edit RTK, hooks, routing, memory stores, Codex config, or always-on workflow behavior without separate approval.
- Do not scan the whole disk for goals; scan only registered goal roots.
- Do not start long-running watchers from Codex shell during the initial reconciler phase.
- Do not treat a registry entry as permission to mutate source goal files.
