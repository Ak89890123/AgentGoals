# Goal Session Handoff Protocol

This protocol connects explicit AgentGoals outputs to session close and resume workflows without making derived STATE authoritative.

## Authority Order

1. Goal Contract, PLAN, and EVIDENCE source files.
2. Validated onboarding report and STATE as compact derived indexes.
3. Git worktree state for committed and uncommitted work.
4. Targeted Link or AgentMemory context when an active interface exists.
5. Broader repository scan only after a named fast-path failure.

The protocol never converts a clean worktree, passing tests, or derived status into permission to accept, complete, move, or rewrite a Goal.

## Fast Path

For an explicitly onboarded repository:

1. Assess an explicit report/STATE pair first when supplied, then only the two allowlisted repository-local pairs.
2. Validate the report against `schemas/onboarding-result.schema.json` and STATE against the Goal STATE schema.
3. Reject reports older than the selected freshness window using validated generation metadata, never filename or filesystem mtime.
4. Require registered global visibility, resume version 1, and zero invalid queue entries.
5. Require every compact queue field to match validated STATE.
6. Bind report `target_repo` and resume `focus_root_id` to the selected STATE entry. Repo-local onboarding IDs and global registry IDs may differ, so the global focus ID travels in the compact resume. Require matching canonical identity and keep the matching STATE, Goal root, Contract, PLAN, and EVIDENCE paths inside the target repository.
7. Select `next_goal`, falling back to `next_planned_goal`, and return only its lifecycle, review, evidence, health, issue, path, and gate fields.
8. Read the selected source Contract frontmatter before acting. Read PLAN or EVIDENCE only when the next gate needs them.
9. Inspect Git state separately. Derived lifecycle data does not classify WIP or authorize a commit.

The bounded command is:

```powershell
python -m agentgoals.session_handoff `
  --repo <absolute-repository>
```

Exit code `0` means the compact fast path is valid. Exit code `2` means the caller must use the existing read-only fallback and report `fallback_reason`.

## Gate Mapping

| Lifecycle status | Review state | Gate |
|---|---|---|
| `draft` | any | `accept_contract` |
| `review_pending` | any | `obtain_review` |
| `ready` | any | `start_execution` |
| `in_progress` | required and not `PASS` | `continue_before_review_gate` |
| `in_progress` | otherwise | `continue_execution` |
| `blocked` | any | `resolve_blocker` |

Unknown statuses produce `inspect_lifecycle_state`.

## Fallback Decision Table

| Reason | Meaning | Required behavior |
|---|---|---|
| `report_missing` | No explicit onboarding report | Run the existing repository/worktree scan |
| `report_malformed` | Report is unreadable or schema-invalid | Report the error; do not trust partial fields |
| `report_stale` | Report exceeds the freshness window | Refresh only through an explicitly invoked bounded pipeline, otherwise scan |
| `report_from_future` | Report generation metadata is later than the assessment clock | Reject the report and inspect clock or producer integrity |
| `repository_unregistered` | Repo is not globally registered | Use local source and Git context; do not imply global visibility |
| `visibility_unverified` | Global presence was not verified | Use local source and surface the missing verification |
| `resume_unsupported` | Resume version or source is unsupported | Preserve the existing scan |
| `invalid_queue` | Queue contains invalid Goals | Surface invalid Goal paths before selecting work |
| `state_missing` / `state_malformed` | Matching STATE is unavailable or invalid | Preserve source files and scan them directly |
| `state_contradiction` | Report and STATE disagree | Stop using the fast path and report both sources |
| `state_fingerprint_mismatch` | Valid STATE bytes differ from the report-bound SHA-256 | Reject the pair and continue deterministic candidate selection |
| `no_valid_candidate` | Every explicit or allowlisted pair failed | Return the recorded attempts and use the read-only fallback |
| `identity_mismatch` | Report, STATE, root, or source paths do not identify the same in-repo Goal | Reject the compact selection and preserve the local scan |
| `tool_unavailable` | Module, interpreter, PYTHONPATH, or bounded command could not start | Name the launch failure and continue with the existing read-only scan |
| `report_contradiction` | Outcome, registration, top-level visibility, resume visibility, or resume source disagree | Reject the report before trusting its queue fields |

Unavailable Link, AgentMemory, CodeGraph, or Codebase Memory interfaces are context gaps, not fast-path failures. The workflow continues with source and Git evidence.

## `END` Responsibilities

- Inspect Git and distinguish finished work, WIP, generated noise, and unclear files.
- When the fast path is valid, confirm the selected Contract, PLAN, and EVIDENCE before describing lifecycle state or gates.
- Record completed work, evidence, WIP, current Goal, exact gate, and next planned Goal in the handoff.
- Preserve commit consent, memory triage, Second Brain gates, Skill Intake requirements, and no-push behavior.
- Never mutate Goal status or move Goal files solely from derived output.

## `ag-continue` Responsibilities

- Attempt the bounded fast path before broad README, docs, memory, or worktree scans.
- Read only the selected source artifacts needed for the current gate.
- Always inspect Git worktree status even when lifecycle context is valid.
- Name the fallback reason before using the existing read-only scan.
- Report which durable context interfaces were available or absent.

## Evaluation

`fixtures/session_handoff/cases.json` is the versioned behavior dataset. `tests/test_session_handoff.py` covers deterministic candidate selection, gate selection, fast-path focus, missing/malformed/stale/unregistered reports, fingerprint mismatch, invalid queues, contradictory STATE, and empty queues. The onboarding regression keeps compact resume context bounded, with zero semantic-model calls and one bounded pipeline invocation.
