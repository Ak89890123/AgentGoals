# AgentGoals 0.2.1 Release Candidate

Status: repo-local candidate only. This document does not authorize a push, tag, GitHub release, package-index publication, global CLI replacement, or Skill installation.

## Public surface

- Distribution: `agentgoals`
- Canonical executable: `agentgoals`
- Compatibility executable and import package: `goal-lifecycle` and `goal_lifecycle` during the 0.x window
- Python requirement: `>=3.11`
- Runtime dependencies: `PyYAML>=6.0`, `jsonschema>=4.0`

The public onboarding command accepts one explicit absolute repository path. Dry-run is the default; `--apply` remains target-bound and does not publish a global registry entry without separate registration authorization.

## Candidate artifacts

These are the locally verified candidate names and hashes:

| Artifact | SHA-256 |
| --- | --- |
| `agentgoals-0.2.1-py3-none-any.whl` | `1fc6de1d0e0e147ba2305fb092f4974632229a6cf4dd1b20b53a3eaefa40aaec` |
| `agentgoals-0.2.1.tar.gz` | `97e8863572785163c01673305487f856ee1bf18290dfcb6e86773e39b4952cc3` |

The current hashes refer to the exact-one-pair candidate directory `.tmp/review-remediation-dist-final-20260713`; ignored or stale local `dist/` contents are not release evidence.

The candidate passed Twine metadata checks and the repository artifact verifier. Archive inspection found no user-specific machine paths, bundled virtual-environment members, test tree, or operator README.

## Install after an approved immutable tag exists

Replace `<TAG>` only after release ownership, tag content, and hosted CI are independently verified:

```powershell
uv tool install "agentgoals @ git+https://github.com/Ak89890123/AgentGoals.git@<TAG>"
pipx install "agentgoals @ git+https://github.com/Ak89890123/AgentGoals.git@<TAG>"
agentgoals --version
agentgoals doctor --json
agentgoals onboard --repo <absolute-repository> --json
```

Do not install both the old `goal-lifecycle-toolkit` distribution and `agentgoals` in one environment. Use the documented uninstall/rollback sequence in `docs/migration-agentgoals.md`.

## Readiness gates

- Current local wheel, sdist, installer, doctor, onboarding, Skill, and full regression evidence is recorded in the repo-local acceptance audit and independent review records.
- A hosted GitHub Actions run is still required for the Linux/macOS/Windows matrix on the final candidate commit.
- Historical [run `29225791420`](https://github.com/Ak89890123/AgentGoals/actions/runs/29225791420) passed the full matrix for commit `c4da014`, but the current branch/worktree contains later changes and requires a fresh run.
- The final fresh independent high review found no code or artifact defects; hosted CI is still required for the final candidate commit.
- The configured GitHub remote currently has no tag refs; creating a tag, pushing, releasing, and publishing remain separate explicit approvals.
