# AgentGoals Legacy Name Audit

Date: 2026-07-13

## Scope

Current public source, canonical tests, package metadata, README/package docs, active operating docs, schemas, scripts, CI, dashboard copy, and staged `ag-*` Skills were searched for:

```text
Goal Lifecycle
Goal Control
goal_lifecycle
goal-lifecycle-toolkit
goal-lifecycle
aab-jixu
aaa-shougong
goal-preflight
goal-onboarding
```

## Allowed Remaining Classes

- `src/goal_lifecycle/`: bounded 0.x wrappers delegating to `agentgoals`.
- `goal-lifecycle` console entry point and CI smoke: bounded compatibility alias.
- `share/goal-lifecycle/schemas`: runtime fallback for old installations.
- `.goal-lifecycle`, `outputs/goal-lifecycle`, and global `.codex/goal-lifecycle`: stable operational data paths that are not silently migrated.
- Explicit migration/rollback documentation and `tests/test_agentgoals_migration.py`.
- Portable 0.1 compatibility fixtures and completed Goal/history artifacts.
- `docs/proposals/`: historical pre-rename decision records.

## Result

Ordinary behavioral tests import `agentgoals`; active repository commands in `AGENTS.md`, README, usage/onboarding docs, scripts, and apps use canonical `agentgoals`. Dashboard English and Traditional Chinese copy, executable, package directory, process name, and icon use AgentGoals. Four staged Skill directories, frontmatter names, manifests, cross-Skill references, and canonical CLI/module commands use the accepted `ag-*` namespace.

No unintended active old product or primary-command reference remained outside the classes above in the final scoped search.
