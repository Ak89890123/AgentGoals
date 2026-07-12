# Fixtures

Use this directory for synthetic goal roots.

Suggested layout:

```text
fixtures/
  repo-a/goals/active/example-a-goal-contract.md
  repo-a/goals/completed/2026-07-07-example-completed-goal-contract.md
  global-codex/goals/active/example-global-goal-contract.md
```

Fixtures should cover:

- active draft
- review pending
- in progress
- blocked
- completed
- status/folder mismatch
- missing evidence
- parse error

`goal_skill_eval/v1/manifest.json` is a versioned bilingual behavior-evaluation
dataset for `goal-preflight`. Its observations template deliberately contains no
model results: fill it only with recorded runtime observations, then score it
with `python -m goal_lifecycle.skill_eval`.

`goal_artifact_tool/v1/` is a versioned, synthetic decision fixture set for the
deterministic Goal scaffold tool. It validates the no-write, single-file,
directory, and rejected-layout paths without introducing Goal-shaped source
files under a scanned `goals/` directory.
