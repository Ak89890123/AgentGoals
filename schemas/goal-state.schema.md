# Goal State Schema

STATE is a derived index. Source files remain authoritative.

Machine-readable schema: `schemas/goal-state.schema.json`.

## State Version

STATE version 2 adds a deterministic queue summary and scheduling fields.

```yaml
version: 2
generated_at: ISO-8601 datetime
queue:
  next_goal: <root-id>/<goal-id> | null
  next_planned_goal: <root-id>/<goal-id> | null
  open_count: integer
  runnable_count: integer
  invalid_count: integer
```

## Entry Fields

```yaml
id: string
title: string
status: draft | review_pending | ready | in_progress | blocked | completed | cancelled | missing | parse_error
project: string
root_id: string
goal_key: <root-id>/<goal-id>
goal_root: string
contract_path: string
plan_path: string | null
evidence_path: string | null
owner: string
updated: YYYY-MM-DD
completed: YYYY-MM-DD | null
review:
  required: boolean
  verdict: pending | PASS | FAIL | NEEDS_EVIDENCE
evidence:
  status: pending | partial | complete | null
scheduling:
  priority: 0..100
  depends_on: [<root-id>/<goal-id>]
  status: not_ready | runnable | in_progress | blocked | dependency_blocked | done | invalid
  queue_position: integer | null
  unmet_dependencies: [<root-id>/<goal-id>]
next_action: string | null
blocked_reason: string | null
source_hash: string
last_seen: ISO-8601 datetime
issues:
  - missing
  - missing_plan
  - missing_evidence
  - stale
  - status_folder_mismatch
  - parse_error
  - review_pending
  - evidence_incomplete
  - invalid_scheduling
  - dependency_missing
  - dependency_cycle
  - duplicate_goal_key
```

## Views

- Open goals: draft, review_pending, ready, in_progress, blocked.
- Waiting review: review.required true and verdict pending/NEEDS_EVIDENCE.
- Blocked: status blocked or blocked_reason present.
- Evidence incomplete: evidence.status pending/partial.
- Completed: completed/cancelled and under completed folder.
- Queue order: dependency-safe topological order, then lifecycle readiness, priority descending, and canonical Goal key.
- `next_goal`: first runnable or already in-progress Goal.
- `next_planned_goal`: first open Goal even when it still needs acceptance or review.
- Contract `scheduling.priority` and `scheduling.depends_on` are source metadata; queue positions are always derived.
