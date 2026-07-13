# AgentGoals Rename Runtime Evidence

Date: 2026-07-13
Platform: Windows, CPython 3.11.15

## Automated Tests

Command:

```powershell
.\.venv\Scripts\python -m pytest
```

Final observed result after canonical tests, legacy wrappers, manifests, and dashboard icon/brand fixes:

```text
250 passed, 2 skipped in 14.32s
```

The skipped cases are environment-dependent symbolic-link tests.

## Clean Wheel Install

An isolated uv venv installed `dist/agentgoals-0.2.0-py3-none-any.whl` with declared dependencies.

Observed:

```text
agentgoals --version                  -> agentgoals 0.2.0
agentgoals doctor --json              -> status ready, toolkit_version 0.2.0
goal-lifecycle --version              -> agentgoals 0.2.0
import agentgoals, goal_lifecycle     -> 0.2.0 / 0.2.0
```

## Onboarding Manual QA

A new explicit Git repository under `.tmp` was passed without `--apply`:

```text
outcome: dry_run_ready
exit_code: 0
message: Dry-run completed without writes.
git status --short: empty
```

An invalid absolute repository path returned structured `conflict`, exit 1. A repository containing a stale incompatible canonical report also failed closed with structured schema details and no apply.

## Install Lifecycle

Baseline 0.1.0 was built from immutable Git `HEAD` before the working-tree rename. The isolated replacement sequence was:

1. Install `goal-lifecycle-toolkit 0.1.0`; observe `goal-lifecycle 0.1.0`.
2. Uninstall 0.1.0; install `agentgoals 0.2.0`.
3. Observe both console scripts report `agentgoals 0.2.0`.
4. Uninstall 0.2.0; both console scripts are absent.
5. Reinstall 0.1.0; observe `goal-lifecycle 0.1.0` and no `agentgoals.exe`.

The existing global `C:\Users\jimmy0302\.local\bin\goal-lifecycle.exe` remained version 0.1.0 throughout.

## Legacy Module Regression

Failing-first evidence before per-module wrappers:

```text
python -m goal_lifecycle.cli --version      -> exit 1, loader mismatch
python -m goal_lifecycle.onboard --help     -> exit 1, loader mismatch
```

After wrappers:

```text
tests/test_agentgoals_migration.py::test_legacy_submodule_invocations_delegate_to_canonical_implementation -> passed
python -m goal_lifecycle.cli --version      -> exit 0
python -m goal_lifecycle.onboard --help     -> exit 0
python -m goal_lifecycle.reconcile --help   -> exit 0
```

## Windows Desktop Package

Final command after AgentGoals executable and icon rename:

```powershell
.\scripts\build_dashboard.ps1 -OutputDir .tmp\agentgoals-dashboard-final
```

Observed:

```text
Executable: .tmp\agentgoals-dashboard-final\AgentGoals\AgentGoals.exe
InstalledSizeMB: 30.35
PackageSmokeEntries: 18
```

## Final Package Hash Gate

The final wheel/sdist build completed after legacy wrapper and dashboard fixes:

```text
wheel SHA-256: 1C142F9A8F67BE903CE1F3D2C799595B668D2515F3046810C68DC086FEECE1E6
sdist SHA-256: 4C848A17A94694147613F6F643B6BD554C5EB3C7C3E35F6C946B5AEB909EB4F2
twine check: PASSED / PASSED
wheel machine paths: none
sdist machine paths: none
bundled .venv paths: none
```

The exact wheel clean-install smoke passed for canonical CLI, doctor, legacy executable/module, onboarding dry-run, and uninstall.

Hosted Linux/macOS CI, trademark clearance, repository ownership confirmation, release coordinates, push, tag, and publication remain separate gates.
