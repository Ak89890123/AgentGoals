# Proposal: Goal Preflight Artifact Tooling Integration

Status: **proposal only — no global Skill patch is authorized by this file.**

## Purpose

Keep semantic decisions with Goal Preflight while making file materialization
deterministic. The model may state a complete artifact decision; the program
then validates it, previews the exact files and hashes, and writes only after a
separate explicit apply confirmation.

## Baseline and Scope

- Proposed global file: `C:\Users\jimmy0302\.codex\skills\goal-preflight\SKILL.md`
- Baseline SHA-256 (2026-07-11):
  `F8256FDE7511CAC2481BC27181C19EBAC84CF67960064CE23AE5A7F8E40FCE83`
- Proposed repo-local tool: `python -m goal_lifecycle.artifact_tool`
- Proposed schema: `schemas/artifact-decision.schema.json`

No reference, routing, hook, configuration, memory, or global Skill file is
changed by the prototype.

## Decision Boundary

Goal Preflight retains these semantic decisions:

- classify `small`, `standard`, or `goal_grade`;
- define goal id, title, owner, project, date, review requirement, scope, and
  acceptance criteria;
- decide whether a durable artifact is appropriate;
- obtain any required review and user authorization.

The program is limited to these mechanical decisions:

- validate a versioned JSON decision against the schema;
- enforce the fixed size/layout/write mapping;
- preview fixed paths and SHA-256 hashes without writes;
- create the known template files under an explicit repository-contained root;
- reject traversal, schema errors, incompatible layouts, and existing targets;
- validate generated frontmatter/headings and optionally emit a hash-only audit
  record.

It must never infer a Goal's scope, approval, review result, semantic status,
or future routing.

## Exact Future Skill Patch

After the **File Output Rules** section, add this new subsection without
altering any other rule:

```md
### Deterministic Artifact Tool (when available)

For an already accepted file-output decision, prefer the repository-local
`goal_lifecycle.artifact_tool` over model-authored Goal scaffolding when the
tool and its versioned schema are available. Supply a complete decision JSON
that declares `size`, `layout`, `file_write`, and the required Goal metadata.
For this tool's machine-readable `size`, translate the Skill's human-facing
`goal-grade` label to the schema enum `goal_grade`; `small` and `standard` are
unchanged. No other classification translation is permitted.

Run the tool without `--apply` first. Report its target paths and hashes, and
do not claim durable files exist after a preview. Run `--apply` only after the
user explicitly re-authorizes the exact repository-contained artifact root
after seeing that preview, and
the required review gate has passed. Use `--audit` only with that authorized
apply: it records a pending hash-only SQLite receipt before materialization,
then finalizes it after validation.

If the tool is unavailable or rejects the decision, do not bypass its safety
rules. Return an unsaved draft or ask for corrected scope/authorization.
```

The patch has one insertion, changes no default classification, and does not
make tool use mandatory when the repository command is unavailable.

## Invocation Protocol

1. Prepare a JSON decision that conforms to
   `schemas/artifact-decision.schema.json`.
2. Preview first (this is zero-write):

   ```powershell
   python -m goal_lifecycle.artifact_tool \
     --repo-root <absolute-repository-root> \
     --artifact-root <repository-contained-output-root> \
     --decision <decision.json>
   ```

3. Present the returned path/hash receipt. Obtain a new explicit authorization
   for the exact `<artifact-root>` after this preview; earlier authorization
   does not authorize apply.
4. Only then apply and, if an audit record is needed, add `--apply --audit`.
   The audit operation creates a `pending` receipt before materialization and
   finalizes it as `applied` only after validation succeeds.
   The repo-local receipt store is
   `<repo>/.goal-lifecycle/artifact-audit.sqlite`.
5. Validate the resulting files through the lifecycle parser/reconciler before
   treating them as durable Goal state.

The tool preserves the accepted Skill decision rather than changing defaults:
`small` is normally `none`/no-write but may be an explicit single-file output;
`standard` is single-file; `goal_grade` may retain the Skill's single-file
default or use directory mode when that decision was accepted. Any unsupported
combination is rejected rather than coerced. The JSON Schema itself
conditionally enforces these `size` / `layout` / `file_write` combinations.

## Safety, Audit, and Recovery

- All artifact and audit paths are resolved and required to remain within the
  supplied repository root before each publication phase. This is not an
  interprocess access-control mechanism: a same-privilege process actively
  replacing directories or the audit database between checks requires an
  isolated or locked workspace.
- The apply path rejects any existing target before writing.
- A single-file scaffold is completed in a sibling staging file, then published
  through a no-clobber hard-link operation; a target created after preflight is
  left untouched and reported as a conflict.
- A directory scaffold is fully built in a sibling staging directory. Its final
  directory is then reserved without replacement and files are linked from the
  stage; on a link failure, only tool-owned links are removed and any remaining
  directory is reported as a conflict for manual recovery.
- The audit receipt uses a repo-local SQLite transaction and contains receipt
  id, Goal id, mode, status, timestamps, file count, error class, repo-relative
  paths, actions, and SHA-256 values — never a generated Goal body or free-form
  input. It begins as `pending`, then is finalized as
  `applied` or `failed`; an interrupted finalization remains visible as pending.
- Legacy JSONL receipts are imported only through an explicit, idempotent command
  and the original JSONL is never deleted automatically. Idempotency is by
  exact legacy-line fingerprint, so two distinct historical lines remain two
  distinct records even if their visible fields happen to match.
- An interrupted finalization remains `pending`. Recovery is never automatic:
  an operator lists the receipt, independently selects a hash-only result
  payload, and explicitly finalizes it; the tool rereads every listed file and
  refuses finalization on any SHA-256 mismatch.
- SQLite uses a bounded busy timeout and translates database failures to an
  actionable tool error. It does not silently retry or repair corruption; an
  operator may retry the explicit command after resolving a lock or restore a
  known-good database backup.
- No automatic deletion or rollback is allowed. For an explicitly authorized
  fixture run, recovery is manual removal of the exact files listed in the
  audit receipt. Source Goal files require a separate deletion authorization.

## Required Gate Before This Proposal Becomes a Patch

1. Independent security/reliability reviewer checks path containment,
   explicit-apply semantics, conflict behavior, audit privacy, staged
   publication/recovery, and
   the exact one-section diff above.
2. Reviewer records `PASS`, `FAIL`, or `NEEDS_EVIDENCE` in the Goal evidence.
3. User explicitly approves this exact global file and insertion scope.
4. Backup the global Skill, apply the exact patch, run focused regression,
   compare the post-patch SHA-256, and record rollback instructions.

Until all four conditions are met, this document is an inactive integration
proposal; the existing global `goal-preflight` Skill remains authoritative.
