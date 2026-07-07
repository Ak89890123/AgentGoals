# Goal Registry Schema

REGISTRY lists known goal roots. It avoids broad filesystem scans.

Machine-readable schema: `schemas/goal-registry.schema.json`.

```yaml
version: 1
updated: YYYY-MM-DD
roots:
  - id: repo-or-global-id
    label: Human readable label
    goal_root: C:\path\to\repo\goals
    scope: repo | global | harness
    project: project-name
    active: true
    added: YYYY-MM-DD
    last_seen: ISO-8601 datetime | null
```

## Rules

- Scan only active registered roots.
- Missing roots should be reported, not silently removed.
- Root removal should require explicit user action.
- Registry does not grant permission to mutate source files.
