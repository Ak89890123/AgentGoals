# AgentGoals 0.2 Migration

AgentGoals 0.2 renames the distribution, import package, primary executable, product copy, and product-owned Skills. Goal IDs, Goal Contract, PLAN, EVIDENCE, registry identity, and existing output data are not rewritten.

## Names

| 0.1 | 0.2 canonical | Compatibility through 0.x |
| --- | --- | --- |
| `goal-lifecycle-toolkit` | `agentgoals` | No package-manager alias; replace explicitly |
| `goal_lifecycle` | `agentgoals` | Import alias retained |
| `goal-lifecycle` | `agentgoals` | Executable delegates to `agentgoals.cli:main` |
| `goal-preflight` | `ag-contract` | Old global Skill remains separate until approved migration |
| `goal-onboarding` | `ag-onboarding` | Old global Skill remains as a compatibility version |
| `aab-jixu` | `ag-continue` | Old global Skill remains until approved migration |
| `aaa-shougong` | `ag-end` | Old global Skill remains until approved migration |

Legacy executable and import aliases are scheduled for removal no earlier than 1.0.0 and 2026-10-01.

## Upgrade From 0.1

The distribution name changed, so installing `agentgoals` does not automatically replace `goal-lifecycle-toolkit`. Do not keep both distributions installed in the same environment because both own the compatibility package and executable.

```powershell
uv tool uninstall goal-lifecycle-toolkit
uv tool install "agentgoals @ git+https://github.com/<OWNER>/AgentGoals.git@v0.2.0"
agentgoals --version
agentgoals doctor --json
goal-lifecycle --version
```

For pipx, use the same replacement order:

```powershell
pipx uninstall goal-lifecycle-toolkit
pipx install "agentgoals @ git+https://github.com/<OWNER>/AgentGoals.git@v0.2.0"
```

## Uninstall

```powershell
uv tool uninstall agentgoals
# or
pipx uninstall agentgoals
```

Both `agentgoals` and its temporary `goal-lifecycle` executable alias are removed with the distribution.

## Rollback To 0.1

Keep the reviewed 0.1.0 release coordinate or wheel before upgrading. Roll back by reversing the replacement:

```powershell
uv tool uninstall agentgoals
uv tool install "goal-lifecycle-toolkit @ git+https://github.com/<OWNER>/<OLD-REPO>.git@v0.1.0"
goal-lifecycle --version
```

Expected rollback output is `goal-lifecycle 0.1.0`. No Goal source file or registry migration is required.

## Skill Migration

Install new `ag-*` directories only from independently reviewed exact files and only with explicit global-write approval. Keep old directories during the compatibility window unless their forwarding aliases and rollback have separately passed review. Never rename unrelated Skills containing generic words such as goal, continue, or end.

## Release Gate

GitHub push, tag creation, PyPI publication, global CLI replacement, and remaining global Skill installations each require separate approval. Trademark review and Linux/macOS CI must pass before public release readiness is claimed.
