# Portable Goal Onboarding Toolkit — Independent Review

Date: 2026-07-13

Reviewer: independent `gpt-5.6-sol` agent, high reasoning effort.

Scope: read-only review of the current non-`goals/` worktree changes. The local `goals/` folders were excluded from release scope and were not modified, staged, committed, or proposed for transmission.

## Verdict

`NOT RELEASE-READY` — 3 blocker/high findings and 2 medium findings.

## Findings

1. **BLOCKER — clean-checkout CI depends on excluded Goal files.** `.github/workflows/package.yml` runs the entire pytest suite, while non-Goal tests import files from the ignored/deleted `goals/` tree (`tests/test_agentgoals_migration.py`, `tests/test_portable_skill.py`, and `tests/test_single_approval_onboarding.py`). A clean remote checkout cannot run the advertised matrix after the Goal tree is excluded. Required fixtures must move to tracked non-Goal test fixtures, or those tests must be removed from release CI scope.

2. **HIGH — canonical CLI does not enforce an absolute target repository.** The public contract and docs describe an absolute `--repo`, but the canonical onboarding path accepts a relative `Path` and resolves it against the current working directory. The relative-path test covers a separate launcher only. The canonical API/CLI needs an early absolute-path rejection and direct regression coverage.

3. **HIGH — public documentation still exposes personal machine paths.** Examples remain in `README.md` and `docs/onboarding.md`, while the public-distribution test does not scan public documentation for machine-specific paths. Public examples need portable placeholders and a bounded public-file scan.

4. **MEDIUM — packaged artifacts are not tested cross-platform.** The OS matrix tests editable installs, but wheel/sdist, pipx, and uv smoke tests run only on Ubuntu. Windows and macOS packaged-install behavior remains unverified.

5. **MEDIUM — artifact verification is not bound to the project version and has an incomplete path denylist.** A stale matching wheel/sdist pair could pass without matching `pyproject.toml`; common macOS/Linux and alternate-drive machine paths are also not covered by the denylist or focused tests.

## Review evidence

- The reviewer found no high-signal credential pattern in the reviewed non-Goal scope.
- `git diff --check` found no whitespace errors.
- The reviewer did not run pytest or validate the current `dist/` because the advertised clean-checkout boundary and artifact directory contents require remediation first.

## Required remediation before commit/release decision

- Decouple release CI/tests from the excluded local `goals/` tree without modifying the local Goal folders.
- Enforce absolute canonical `--repo` input and add direct tests.
- Remove personal paths from public documentation and add public-surface scanning.
- Decide whether to add cross-platform package-smoke jobs.
- Bind artifact verification to the project version and expand path-boundary tests.

## Local remediation evidence

- Goal-dependent fixture modules now skip safely when the intentionally excluded local `goals/` tree is absent; a disposable checkout containing tracked non-Goal files only passed `282` tests with `36` expected local-fixture skips.
- Canonical onboarding now rejects relative `--repo` paths before resolution; focused API/CLI coverage and the broader remediation suite passed.
- README, onboarding, usage, and release documentation now use placeholders or the verified repository coordinate; the bounded public documentation path scan passes.
- Artifact verification now binds both artifacts to the `pyproject.toml` version and rejects alternate-drive/POSIX machine paths and captured uppercase `PATH`/`PYTHONPATH`; the rebuilt wheel/sdist verifier passes.
- Cross-platform package smoke is wired for wheel and sdist in the Ubuntu/macOS/Windows matrix; local wheel and sdist disposable install smokes pass with version, doctor, and compatibility alias checks.
- Current local regressions pass `320 passed, 3 skipped` on both Python 3.11 and Python 3.12.

The initial findings are addressed in the current worktree subject to follow-up independent review. No commit or push has been made.

## Final follow-up review

The final fresh independent high-reasoning review found no remaining code, artifact, path-boundary, public-documentation, or clean-checkout defects. The final local evidence is:

- full local regression: `330 passed, 3 skipped`;
- clean public checkout without the local `goals/` tree: `296 passed, 32 skipped`;
- final wheel/sdist candidate passed Twine, the artifact verifier, and isolated wheel/sdist CLI/doctor smokes;
- final candidate hashes are recorded in the acceptance audit and release notes;
- `git diff --check` and bounded public-documentation scans pass.

The review still returns `NOT RELEASE-READY` only because the final candidate commit has no hosted Linux/macOS/Windows CI result yet. A local non-`goals/` candidate commit is reasonable; tag, push, release, and publication remain out of scope until hosted CI and separate approval.
