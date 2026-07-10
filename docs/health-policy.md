# Goal Health Policy

Goal health is an optional, deterministic, read-only assessment. Goal Contract,
PLAN, and EVIDENCE remain authoritative; health findings never change source
status or block scheduling by themselves.

## Enable Policy Version 1

Add `health_policy` to the repo-local `registry/REGISTRY.json`:

```json
{
  "version": 1,
  "updated": "2026-07-10",
  "health_policy": {
    "version": 1,
    "enabled": true,
    "thresholds": {
      "in_progress": 10,
      "blocked": 14
    }
  },
  "roots": []
}
```

Omitted thresholds inherit the reviewed version-1 defaults. An absent policy or
`enabled: false` preserves legacy reconciliation, including legacy `stale` for a
Contract with no `updated` value. Unknown policy fields, versions, statuses, and
negative thresholds fail validation instead of being ignored.

## Version 1 Freshness Table

| Status | Default days | Stale severity |
| --- | ---: | --- |
| `draft` | 30 | `info` |
| `review_pending` | 7 | `warning` |
| `ready` | 14 | `warning` |
| `in_progress` | 14 | `warning` |
| `blocked` | 7 | `info` |

The evaluation date and all metadata dates are UTC calendar dates in strict
`YYYY-MM-DD` form. The last activity date is the latest valid, non-future
`updated` date from Contract, PLAN, or EVIDENCE. A Goal remains fresh through its
threshold day and becomes stale when `age_days > threshold_days`.

Use a fixed evaluation date for reproducible output:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.reconcile `
  --registry registry\REGISTRY.json `
  --out outputs `
  --evaluation-date 2026-07-20

.\.venv\Scripts\python -m goal_lifecycle.run `
  --registry registry\REGISTRY.json `
  --out outputs `
  --evaluation-date 2026-07-20 `
  --json
```

Without this option, the evaluator uses the current UTC date.

## Stable Health Issue Codes

- `health_stale`: an active Goal exceeded its status threshold.
- `health_date_missing`: a required structured date is absent.
- `health_date_invalid`: a supplied date is not strict `YYYY-MM-DD`.
- `health_date_future`: a supplied date is after the evaluation date.
- `health_date_order`: an activity or completion date precedes `created`.
- `health_completion_inconsistent`: an active Goal has a completion date.
- `health_evidence_incomplete`: a completed Goal lacks complete evidence.

Each STATE health finding records its stable code, precise rule, severity, field,
observed date, age, and threshold where applicable. Repeated codes can therefore
identify separate invalid fields without inventing field-specific issue strings.

## Safety and False-Positive Boundary

- PLAN and EVIDENCE activity prevents a stale warning when Contract metadata is
  older.
- Future dates are reported but excluded from last-activity calculation.
- `draft` and `blocked` aging is informational because inactivity may be
  intentional or externally constrained.
- Findings are reporting signals only. Notifications, source edits, automatic
  transitions, and scheduling blockers require a separate reviewed change.
