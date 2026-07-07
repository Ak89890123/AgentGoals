# Code Review: Read-Only Global State Aggregator Hardening

Review target: HEAD `219aeb7e96bf92741671abb5c152342508b38408` (`Harden global aggregator path validation`)

Prior review checked: `.omo/evidence/read-only-global-state-aggregator-code-review.md`

Scope reviewed:

- `src/goal_lifecycle/aggregate.py`
- `src/goal_lifecycle/validate.py`
- `schemas/global-registry.schema.json`
- `tests/test_aggregate.py`
- `README.md`
- `docs/production-state-topology.md`
- `docs/global-registry-schema-notes.md`
- `goals/active/codex-skill-optimization/EVIDENCE.md`
- `goals/completed/production-state-location/EVIDENCE.md`

Skill-perspective check:

- `omo:remove-ai-slops` was loaded and applied as an overfit/slop review pass over production and test changes.
- `omo:programming` and its Python reference were loaded and applied for Python maintainability, boundary parsing, typing, broad exception, and test-shape review.
- No deletion-only tests, tautological tests, implementation-constant-only tests, brittle prompt tests, unnecessary production extraction/parsing, untyped escape hatches, or needless abstractions were found.
- The broad `except Exception` in repo STATE aggregation remains acceptable for this goal because malformed or out-of-scope repo STATE is an explicit trust-boundary behavior that must become a `parse_error` aggregate issue.

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

1. Test coverage does not explicitly exercise `goal_root` outside `repo_root`.

   Runtime enforcement is present for both fields (`src/goal_lifecycle/aggregate.py:58`, `src/goal_lifecycle/aggregate.py:59`), and the schema requires absolute-looking Windows paths for `repo_root`, `goal_root`, and `state_path` (`schemas/global-registry.schema.json:42`, `schemas/global-registry.schema.json:47`, `schemas/global-registry.schema.json:52`). The tests cover relative registry paths (`tests/test_aggregate.py:120`) and `state_path` outside `repo_root` (`tests/test_aggregate.py:131`), but not the symmetric `goal_root` outside `repo_root` case. This is not a blocker because the implementation path is shared and simple, but it is a small coverage gap in a security-relevant allowlist contract.

## Prior Review Notes

Addressed:

- Absolute global registry path enforcement: schema patterns added and runtime `Path.is_absolute()` checks are present (`schemas/global-registry.schema.json:42`, `schemas/global-registry.schema.json:47`, `schemas/global-registry.schema.json:52`, `src/goal_lifecycle/aggregate.py:52`, `src/goal_lifecycle/aggregate.py:57`, `src/goal_lifecycle/aggregate.py:131`).
- `goal_root` and `state_path` under `repo_root`: runtime containment checks are present before roots are accepted (`src/goal_lifecycle/aggregate.py:58`, `src/goal_lifecycle/aggregate.py:59`, `src/goal_lifecycle/aggregate.py:147`).
- Repo-local STATE relative path rebasing: relative entry paths are rebased against `repo_root`, then emitted as absolute paths (`src/goal_lifecycle/aggregate.py:96`, `src/goal_lifecycle/aggregate.py:117`, `src/goal_lifecycle/aggregate.py:136`, `tests/test_aggregate.py:141`).
- Registered `goal_root` scope checks: entry `goal_root`, `contract_path`, `plan_path`, and `evidence_path` are checked under the registered `goal_root` (`src/goal_lifecycle/aggregate.py:97`, `src/goal_lifecycle/aggregate.py:107`).
- Malformed or out-of-scope repo STATE becomes aggregate `parse_error`: `read_repo_state()` converts validation, JSON, and path-scope failures into one aggregate issue entry (`src/goal_lifecycle/aggregate.py:79`, `src/goal_lifecycle/aggregate.py:93`, `tests/test_aggregate.py:166`).
- BOM handling: global registry, repo STATE validation, repo STATE read, and hash fallback now use `utf-8-sig` where needed (`src/goal_lifecycle/aggregate.py:48`, `src/goal_lifecycle/aggregate.py:81`, `src/goal_lifecycle/aggregate.py:209`, `src/goal_lifecycle/validate.py:14`, `tests/test_aggregate.py:108`, `tests/test_aggregate.py:189`).
- Multi-root duplicate goal ids: tests verify both duplicate ids survive aggregation and remain path-disambiguated (`tests/test_aggregate.py:207`, `tests/test_aggregate.py:228`).
- No source goal mutation: production aggregation writes only the caller-selected output directory (`src/goal_lifecycle/aggregate.py:183`, `src/goal_lifecycle/aggregate.py:194`) and reads registered `state_path` files only (`src/goal_lifecycle/aggregate.py:75`, `src/goal_lifecycle/aggregate.py:83`).
- No broad disk scan: no `rglob`, `glob`, `os.walk`, or equivalent scan appears in the aggregator; it iterates only registry roots and reads only `root.state_path`.
- No global `.codex` mutation in this commit: `git diff-tree --no-commit-id --name-only -r HEAD` lists only repo-local files in the reviewed scope. Documentation and evidence mention the existing global registry path, but this commit does not modify files under `C:\Users\jimmy0302\.codex`.

## Verification

- Confirmed HEAD: `219aeb7e96bf92741671abb5c152342508b38408`.
- Confirmed worktree status was clean before writing this report.
- Inspected full patch for commit `219aeb7`.
- Inspected prior review artifact `.omo/evidence/read-only-global-state-aggregator-code-review.md`.
- Ran `.\.venv\Scripts\python -m pytest` with repo-local `TEMP`/`TMP`. Result: `28 passed in 0.79s`.
- Measured pure LOC for changed Python test/production files: `src/goal_lifecycle/aggregate.py` 190, `tests/test_aggregate.py` 176; both under the 250-line programming-skill ceiling.

## Residual Risks

- The global registry schema is intentionally Windows-path-specific. That matches this repo and operator environment, but it should be revisited before expecting non-Windows registry files.
- If a repo STATE has multiple entries and only one entry is out of scope, the aggregator reports the whole registered root as a single `parse_error` issue. That matches the current malformed-STATE treatment and is acceptable for this read-only dashboard phase.
- Writer, watcher, hook, routing, memory, and additional global `.codex` mutations remain out of scope.

## Verdict

codeQualityStatus: WATCH

recommendation: APPROVE

userVerdict: APPROVE_WITH_NOTES

reportPath: `.omo/evidence/read-only-global-state-aggregator-hardening-review.md`

blockers: None.
