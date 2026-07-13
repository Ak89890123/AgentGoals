# AgentGoals Multi-Repo Onboarding

## Purpose

The onboarding command prepares one explicitly supplied Git repository for the federated AgentGoals model. It can create conservative repo-local lifecycle scaffolding, generate and validate local derived STATE, verify visibility in a caller-selected derived global aggregate, and—only with an explicit `--register` authorization—publish one exact global-registry entry after candidate validation.

It does not detect conversational intent, scan for repositories, edit global `.codex`, create Goals, or install a watcher, hook, daemon, or scheduled task.

## Invocation Decision Table

| Situation | Invocation | Writes | Result |
| --- | --- | --- | --- |
| Ordinary chat | None | None | No onboarding action |
| User or caller requests an onboarding check | Run without `--apply` | None | Eligibility, exact write set, proposed entry, and registration condition |
| User explicitly authorizes this repository | Run once with `--apply` | Repo-local scaffold and derived outputs only | Local STATE and `ONBOARDING.json` |
| Repository is already globally registered | Add `--global-registry` | Repo-local derived local/global outputs only | Verified canonical Goal visibility |
| Repository is not globally registered, legacy flow | `--apply --global-registry` | Repo-local outputs only | `registration_required` plus a machine-readable proposal |
| Repository is not globally registered, one-approval flow | `--apply --register --global-registry <absolute-file>` | Repo-local outputs and one guarded global-registry replacement | `visibility_verified` or `global_issues`; no second registration approval |

`--apply` is scoped to one invocation and the canonical path passed through `--repo`. A previous dry-run or approval for another path is not consent.

## Commands

Confirm that the portable executable and its packaged schemas are available:

```powershell
agentgoals doctor --json
```

Normal use requires only an absolute target repository path. It does not require
the user or LLM to know where the toolkit source checkout lives.

Dry-run, which performs no writes:

```powershell
agentgoals onboard `
  --repo <absolute-repository> `
  --json
```

Apply repo-local onboarding:

```powershell
agentgoals onboard `
  --repo <absolute-repository> `
  --apply `
  --json
```

Verify an already-registered repository in a derived global aggregate:

```powershell
agentgoals onboard `
  --repo <absolute-repository> `
  --apply `
  --global-registry <absolute-global-registry> `
  --json
```

For a new repository that should become globally visible, review the first command's exact `registration` object, including `registration.plan_sha256`, then authorize the displayed repository, registry, proposed entry, and write set once before running the second command:

```powershell
agentgoals onboard `
  --repo <absolute-repository> `
  --global-registry <absolute-global-registry> `
  --json

agentgoals onboard `
  --repo <absolute-repository> `
  --apply `
  --register `
  --registration-plan-sha256 <registration.plan_sha256> `
  --global-registry <absolute-global-registry> `
  --json
```

`--register` is rejected unless it is paired with `--apply`, the exact `registration.plan_sha256` from the dry-run, and an absolute global registry path. The candidate registry, local STATE, aggregate, global validation, and canonical visibility are checked before publication. A stale or concurrently changed registry is never overwritten. The guarded writer uses a stable same-directory `.REGISTRY.json.agentgoals.lock` anchor, which is included in the disclosed write set.

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

Dry-run does not write or accept registration. Its `registration` object identifies the canonical global registry, before hash, proposed entry, exact planned write set, and the condition that publication requires local and global validation. The legacy apply path still returns `registration_required`; the authorized path uses `--register` to publish the candidate after those checks.

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
| `recovery_required` | 1 | A post-commit boundary detected a third-party change; manual recovery is required |

Without `--register`, the proposal remains data only and the global registry is unchanged. With `--register`, the one exact authorization covers the displayed target-bound write set; no separate registration approval is requested. Global Skill installation, global `.codex` changes outside the supplied registry, and release remain separate gates.

## Developer Checkout Fallback

Contributors working directly in this repository can exercise the same root CLI
without installing the tool. This is a development fallback, not an onboarding
requirement for users or LLMs:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m agentgoals onboard `
  --repo <absolute-repository> `
  --json
```

## Recovery And Rollback Review

Deferred rollback is deliberately non-destructive. A report stored in the target repository can be edited, so its hashes and `created` flags cannot prove that a canonical registry or STATE file was actually created by that run. The rollback command therefore validates and classifies candidates but never deletes files or directories.

```powershell
agentgoals onboard `
  --rollback-report <absolute-repository>\outputs\ONBOARDING.json `
  --json
```

The command returns `rollback_review_required` with exit `2`, an empty `deleted` list, and retained reasons. Recovery uses deterministic `--apply` rerun, which repairs derived outputs without rewriting Goal sources. If cleanup is still desired, the operator must inspect the report and explicitly handle one file at a time; recursive deletion is never used.

STATE JSON and Markdown files are replaced atomically one file at a time. The complete multi-file run is not a single filesystem transaction: if a later stage fails, valid earlier derived files may remain. The global registry itself is guarded by its preflight hash and replaced as one file; after publication, a report-boundary failure may restore the exact before-bytes only when the registry still has the exact operation after-hash. Otherwise the result is `recovery_required` with before/after/current hashes and no overwrite.

## LLM-Efficiency Boundary

After explicit invocation, repository detection, scaffold planning, reconciliation, validation, aggregation, scheduling, report generation, and visibility verification are deterministic Python operations and make zero semantic-model calls.

The report exposes a compact `resume` object containing only the current queue facts needed to identify the next Goal. The acceptance benchmark compares the UTF-8 byte size of this object with the Contract/Plan/Evidence context for the same fixed resume scenario. Completion requires:

- at least 50% fewer LLM-visible UTF-8 context bytes;
- zero semantic-model calls inside the pipeline;
- no increase beyond one bounded pipeline invocation.

Conversational intent detection is not part of this command. A future global Skill, RTK, AGENTS, hook, or session integration requires a separate reviewed change.
