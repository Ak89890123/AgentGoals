# Goal State Schema Draft

STATE is a derived index. Source files remain authoritative.

## Entry Fields

```yaml
id: string
title: string
status: draft | review_pending | ready | in_progress | blocked | completed | cancelled
project: string
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
```

## Views

- Open goals: draft, review_pending, ready, in_progress, blocked.
- Waiting review: review.required true and verdict pending/NEEDS_EVIDENCE.
- Blocked: status blocked or blocked_reason present.
- Evidence incomplete: evidence.status pending/partial.
- Completed: completed/cancelled and under completed folder.
