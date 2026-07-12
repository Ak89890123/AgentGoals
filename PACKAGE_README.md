# Goal Lifecycle Toolkit

Portable, dry-run-first tooling for Goal Contract lifecycle onboarding.

```text
goal-lifecycle --version
goal-lifecycle doctor --json
goal-lifecycle onboard --repo <absolute-repository-path> --json
```

`--apply` permits repository-local writes for that exact target and invocation.
The toolkit never scans disks for repositories and never edits a global registry.
Install from an immutable reviewed GitHub tag with `uv tool` or `pipx`.
