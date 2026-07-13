# Portable Goal Onboarding Toolkit — Acceptance Audit

Status: repo-local self-audit. This is not an independent reviewer verdict and does not authorize release, global Skill replacement, or publication.

Date: 2026-07-13

## Requirement matrix

| Requirement | Current evidence | Verdict |
| --- | --- | --- |
| Canonical `agentgoals` CLI plus bounded `goal-lifecycle` compatibility alias | Current wheel metadata, source-checkout editable install, console-script and legacy-module smokes | PASS |
| Wheel/sdist are reproducible enough for candidate review and expose correct metadata/entry points | `scripts/verify_package_artifacts.py`, Twine checks, current hashes recorded in the active EVIDENCE | PASS |
| Published artifacts exclude machine paths, secrets, bundled venvs, tests, and operator README | Artifact verifier scans content and member names; current wheel/sdist pass | PASS |
| Explicit target-only dry-run/apply behavior and LLM-efficiency boundary | Disposable Git targets return `dry_run_ready`/`registration_required`; metrics prove `0`/`1` pipeline invocation and `0` semantic calls | PASS |
| Public `ag-onboarding` candidate is portable and baseline-bound | Candidate and manifest hashes match the Skill-boundary Goal; bounded scan finds no personal path or mandatory private integration | PASS, pending its owning Goal's final review |
| Source checkout, wheel, pipx, uv, upgrade, uninstall, downgrade, and rollback paths | Current editable install, wheel, pipx, uv, and isolated 0.1.0 ↔ 0.2.1 migration/rollback smokes pass | PASS locally |
| Current repository regression across supported Python versions | Final Python 3.11 run: `330 passed, 3 skipped`; an earlier Python 3.12 editable-install run passed `320 passed, 3 skipped`; all runs used only a runner-side pytest temporary-directory mode workaround for this Windows sandbox's `0o700` ACL behavior | PASS locally; hosted matrix still pending |
| Independent current-worktree review and remediation | Initial findings were remediated; final fresh independent high review found no code or artifact defects. Final local evidence is `296 passed, 32 skipped` in a clean checkout without `goals/`, `330 passed, 3 skipped` locally, final Twine/verifier/wheel/sdist smokes, and bounded public-doc scans | PASS locally; hosted CI still pending |
| Windows plus Linux/macOS CLI/package matrix | GitHub Actions run `29225791420` for historical commit `c4da014` passed package smoke and all Ubuntu/macOS/Windows Python 3.11/3.12 jobs; current branch/worktree changed afterward | PENDING hosted run for the current candidate |
| Pinned GitHub installation coordinate | README and release notes now name the verified public repository `Ak89890123/AgentGoals`; GitHub confirms default branch `main`, local `HEAD` is 16 commits ahead of `origin/main`, and read-only remote tag query returns no tag refs. Administration permission exists, but no push/tag/release was performed without the separate human gate | PENDING tag/release decision |
| Independent security/path, packaging/release, and Skill-governance review of current worktree | Final fresh independent high review found no remaining code/artifact/path/public-boundary defect; it held release readiness only for the missing hosted matrix result | PASS locally; hosted CI still pending |
| Durable Goal artifacts remain deliverable | Active Goal files exist in the working tree, but the pre-existing staged diff deletes the tracked `goals/` tree and `.gitignore` ignores `/goals/`; this audit did not alter staging | PENDING owner resolution |

## Current candidate hashes

| Artifact | SHA-256 |
| --- | --- |
| `agentgoals-0.2.1-py3-none-any.whl` | `1fc6de1d0e0e147ba2305fb092f4974632229a6cf4dd1b20b53a3eaefa40aaec` |
| `agentgoals-0.2.1.tar.gz` | `97e8863572785163c01673305487f856ee1bf18290dfcb6e86773e39b4952cc3` |
| `ag-onboarding/SKILL.md` | `1EB1716C5945907E3B8A7D091B3FA0F368A12BCE0AF52A6792E8690D70C8D6AD` |

The artifact hashes above refer to the exact-one-pair candidate directory `.tmp/review-remediation-dist-final-20260713`; ignored or stale local `dist/` contents are not release evidence.

## Completion rule

The Goal must remain active until every `PENDING` row has authoritative evidence or an explicit separate approval. In particular, local green tests do not substitute for hosted cross-platform CI, a release tag, or resolving the pre-existing Goal-tree staging state.
