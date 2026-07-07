# Production Readiness Review

## Current Verdict

Status: `production_read_only`

The harness passed independent production-readiness review as a read-only operator tool. It is not approved as an automatic writer, watcher, or global state service.

## Scope Under Review

Included:

- `registry/REGISTRY.json` as the allowlist of scanned goal roots.
- `src/goal_lifecycle/reconcile.py` as a read-only STATE generator.
- `src/goal_lifecycle/validate.py` as the JSON Schema validation gate.
- `outputs/STATE.json` and `outputs/STATE.md` as ignored generated artifacts.
- `docs/usage.md` as operator guidance.

Excluded:

- Automatic mutation of goal files.
- Global `.codex` skill/config changes.
- Watchers, daemons, scheduled tasks, or hooks.
- Whole-disk goal discovery.
- Cross-repo production rollout.

## Readiness Criteria

- Registry scanning is allowlist-only.
- Reconcile is read-only against source goal files.
- Generated STATE is clearly documented as derived.
- Validation fails on malformed registry or STATE JSON.
- Fixture coverage includes normal and failure paths.
- Operator instructions define safe usage and escalation boundaries.
- Evidence records commands, results, and residual risk.

## Review Checklist

- Confirm `REGISTRY.json` cannot imply write permission.
- Confirm reconcile only writes under the requested output directory.
- Confirm parse errors are reported instead of silently dropped.
- Confirm missing plan/evidence files are visible in generated STATE.
- Confirm status/folder mismatch is visible.
- Confirm generated STATE does not become canonical truth.
- Confirm README and usage docs do not promise watcher behavior.
- Confirm global skill edits still require proposal, review, approval, patch, and verification.

## Manual QA Gate

Run:

```powershell
$env:TEMP=(Resolve-Path .tmp).Path; $env:TMP=$env:TEMP
.\.venv\Scripts\python -m pytest
$env:PYTHONPATH=(Resolve-Path src).Path
.\.venv\Scripts\python -m goal_lifecycle.reconcile --registry registry\REGISTRY.json --out outputs
.\.venv\Scripts\python -m goal_lifecycle.validate --registry registry\REGISTRY.json --state outputs\STATE.json
```

Pass condition:

- tests pass;
- reconcile exits 0;
- validation exits 0;
- generated STATE lists registered goals and actionable issues;
- no source goal files are modified by reconcile or validation.

## Promotion Decision

Promoted to `production_read_only` after independent reviewer `Beauvoir` returned `PASS_WITH_NOTES` with no blocking findings.

Do not promote to writer or watcher mode from this review. Those need separate goals and separate approval gates.
