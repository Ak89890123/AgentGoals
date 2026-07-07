# Global Registry Schema Notes

## Purpose

The global registry is the allowlist for federated STATE aggregation.

It is separate from repo-local `registry/REGISTRY.json` because global aggregation needs to know where each repo-local STATE output lives.

## Required Fields

Each global registry entry should include:

- `id`: stable kebab-case repo id;
- `label`: display label;
- `repo_root`: absolute repo root path;
- `goal_root`: absolute goal root path;
- `state_path`: absolute repo-local `STATE.json` path;
- `scope`: `repo`, `global`, or `harness`;
- `project`: project label;
- `active`: whether aggregation should read this entry;
- `added`: date added;
- `last_seen`: timestamp from the last successful aggregation, or null.

## Validation Rules

- `id` must remain stable and kebab-case.
- `repo_root`, `goal_root`, and `state_path` must be absolute paths; no whole-disk discovery.
- `goal_root` and `state_path` must remain under `repo_root`.
- inactive entries should remain in the registry but must not be read by aggregation.
- missing, malformed, or path-scope-invalid `state_path` content should produce an aggregate issue, not a source mutation.
- the registry does not grant permission to edit repo-local files.

## Open Implementation Choice

The existing repo-local registry schema can either:

1. stay separate from a new global registry schema; or
2. be extended with optional `repo_root` and `state_path` fields.

Decision: use a separate global schema first, because repo-local reconcile does not need `state_path`.

Executable schema:

- `schemas/global-registry.schema.json`
