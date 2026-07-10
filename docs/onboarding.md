# Multi-Repo Goal Onboarding

## Purpose

The onboarding command prepares one explicitly supplied Git repository for the federated Goal Lifecycle model. It can create conservative repo-local lifecycle scaffolding, generate and validate local derived STATE, emit a global-registry proposal, and verify visibility in a caller-selected derived global aggregate when the repository is already registered.

It does not detect conversational intent, scan for repositories, edit global `.codex`, create Goals, or install a watcher, hook, daemon, or scheduled task.

## Invocation Decision Table

| Situation | Invocation | Writes | Result |
| --- | --- | --- | --- |
| Ordinary chat | None | None | No onboarding action |
| User or caller requests an onboarding check | Run without `--apply` | None | Eligibility, conflicts, planned scaffold, and notice that a proposal will follow validated apply |
| User explicitly authorizes this repository | Run once with `--apply` | Repo-local scaffold and derived outputs only | Local STATE and `ONBOARDING.json` |
| Repository is already globally registered | Add `--global-registry` | Repo-local derived local/global outputs only | Verified canonical Goal visibility |
| Repository is not globally registered | Optional `--global-registry` | No global-registry write | `registration_required` plus a machine-readable proposal |

`--apply` is scoped to one invocation and the canonical path passed through `--repo`. A previous dry-run or approval for another path is not consent.

## Commands

Set `PYTHONPATH` to this harness's `src` directory before running the module.

Dry-run, which performs no writes:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.onboard `
  --repo C:\devhome\legacy-repo `
  --json
```

Apply repo-local onboarding:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.onboard `
  --repo C:\devhome\legacy-repo `
  --apply `
  --json
```

Verify an already-registered repository in a derived global aggregate:

```powershell
.\.venv\Scripts\python -m goal_lifecycle.onboard `
  --repo C:\devhome\legacy-repo `
  --apply `
  --global-registry C:\Users\jimmy0302\.codex\goal-lifecycle\REGISTRY.json `
  --json
```

The registered `state_path` must equal `<repo>/outputs/goal-lifecycle/STATE.json` unless `--out` is explicitly set to the registered location. A mismatch fails before any repo-local write.

## Repo-Local Scaffold

The default layout is:

```text
<repo>/
  goals/
    active/
    completed/
  registry/
    REGISTRY.json
  outputs/
    goal-lifecycle/
      STATE.json
      STATE.md
      ONBOARDING.json
      global/
        STATE.json
        STATE.md
```

The command does not create a Goal Contract. It preserves pre-existing Goal source files and records their before/after SHA-256 hashes. A valid partial repo registry is extended without replacing other roots. Invalid, duplicate, escaping, or colliding paths fail closed.

Dry-run never emits an actionable global registration proposal because no local STATE has been generated and validated. When registration is required, it reports the planned action `emit_global_registration_proposal_after_validation`; the machine-readable proposal appears only in the apply result after local validation.

The command touches only its exact derived-output targets. Existing target STATE or onboarding-report files must pass their schemas before replacement; invalid target collisions fail closed. Unrelated sibling output files are preserved and do not block onboarding. Output paths that overlap Goal sources, the repo registry, or local/global STATE authority boundaries are rejected.

## Result Contract

`ONBOARDING.json` validates against `schemas/onboarding-result.schema.json`. Each stage retains `passed`, `issues`, `failed`, or `skipped`. The overall outcomes are:

| Outcome | Exit | Meaning |
| --- | ---: | --- |
| `dry_run_ready` | 0 | Read-only preflight passed |
| `visibility_verified` | 0 | Local pipeline and derived global visibility passed |
| `registration_required` | 2 | Local onboarding passed; proposal requires separate approval |
| `global_issues` | 2 | Visibility passed but lifecycle issues remain |
| `conflict` | 1 | Eligibility, registry, path, or collision preflight failed |
| `local_failed` | 1 | Repo-local scaffold, reconcile, or validation failed |
| `global_failed` | 1 | Derived aggregate, global validation, or visibility verification failed |

The proposal is data only. Applying it to the global `.codex` registry remains a separate proposal, independent review, explicit approval, patch, and verification action.

## Recovery And Rollback Review

Deferred rollback is deliberately non-destructive. A report stored in the target repository can be edited, so its hashes and `created` flags cannot prove that a canonical registry or STATE file was actually created by that run. The rollback command therefore validates and classifies candidates but never deletes files or directories.

```powershell
.\.venv\Scripts\python -m goal_lifecycle.onboard `
  --rollback-report C:\devhome\legacy-repo\outputs\goal-lifecycle\ONBOARDING.json `
  --json
```

The command returns `rollback_review_required` with exit `2`, an empty `deleted` list, and retained reasons. Recovery uses deterministic `--apply` rerun, which repairs derived outputs without rewriting Goal sources. If cleanup is still desired, the operator must inspect the report and explicitly handle one file at a time; recursive deletion is never used.

STATE JSON and Markdown files are replaced atomically one file at a time. The complete multi-file run is not a single filesystem transaction: if a later stage fails, valid earlier derived files may remain. The report records those artifacts, and a repeated `--apply` deterministically repairs derived outputs without rewriting Goal sources.

## LLM-Efficiency Boundary

After explicit invocation, repository detection, scaffold planning, reconciliation, validation, aggregation, scheduling, report generation, and visibility verification are deterministic Python operations and make zero semantic-model calls.

The report exposes a compact `resume` object containing only the current queue facts needed to identify the next Goal. The acceptance benchmark compares the UTF-8 byte size of this object with the Contract/Plan/Evidence context for the same fixed resume scenario. Completion requires:

- at least 50% fewer LLM-visible UTF-8 context bytes;
- zero semantic-model calls inside the pipeline;
- no increase beyond one bounded pipeline invocation.

Conversational intent detection is not part of this command. A future global Skill, RTK, AGENTS, hook, or session integration requires a separate reviewed change.
