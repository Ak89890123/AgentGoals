from __future__ import annotations

import importlib.util
import json
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest


LAUNCHER = Path(
    "goals/active/portable-goal-onboarding-toolkit/skill-package/goal-onboarding/scripts/invoke_goal_lifecycle.py"
)
ABS_REPO = Path.cwd().resolve()


def load_launcher():
    spec = importlib.util.spec_from_file_location("portable_goal_onboarding_launcher", LAUNCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def launcher_test_dir() -> Iterator[Path]:
    path = Path(".tmp") / "portable-skill-test" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path.resolve()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_launcher_builds_dry_run_with_target_only() -> None:
    launcher = load_launcher()

    arguments = launcher.build_onboard_arguments(Path("C:/repo with spaces"), apply=False, global_registry=None)

    assert arguments == ["onboard", "--repo", str(Path("C:/repo with spaces")), "--json"]


def test_launcher_adds_apply_and_global_registry_only_when_supplied() -> None:
    launcher = load_launcher()

    arguments = launcher.build_onboard_arguments(
        Path("C:/repo"),
        apply=True,
        global_registry=Path("C:/config/REGISTRY.json"),
    )

    assert arguments == [
        "onboard",
        "--repo",
        str(Path("C:/repo")),
        "--apply",
        "--global-registry",
        str(Path("C:/config/REGISTRY.json")),
        "--json",
    ]


def test_launcher_missing_cli_returns_one_compact_remediation(capsys) -> None:
    launcher = load_launcher()

    exit_code = launcher.main(
        ["--repo", str(ABS_REPO)],
        env={},
        which=lambda _: None,
        module_origin=None,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "action_required"
    assert payload["failure_code"] == "cli_not_found"
    assert payload["metrics"] == {"launcher_invocations": 1, "cli_process_invocations": 0}
    assert payload["remediation"] == {
        "action": "provide_release_coordinates",
        "argv": ["OWNER", "REPO", "TAG"],
    }


def test_launcher_rejects_relative_target_without_running_cli(capsys) -> None:
    launcher = load_launcher()

    exit_code = launcher.main(["--repo", "relative/repo"], env={}, which=lambda _: None, module_origin=None)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["failure_code"] == "target_not_absolute"


def test_launcher_runs_cli_without_shell_and_forwards_exit(monkeypatch) -> None:
    launcher = load_launcher()
    with launcher_test_dir() as temp_dir:
        binary = temp_dir / "goal-lifecycle.exe"
        binary.write_text("placeholder", encoding="utf-8")
        binary.chmod(0o755)
        observed = {}

        class Completed:
            returncode = 2
            stdout = '{"version":1,"outcome":"registration_required"}\n'
            stderr = ""

        def fake_run(argv, **kwargs):
            observed["argv"] = argv
            observed.update(kwargs)
            return Completed()

        monkeypatch.setattr(launcher.subprocess, "run", fake_run)

        exit_code = launcher.main(
            ["--repo", str(ABS_REPO)],
            env={"GOAL_LIFECYCLE_BIN": str(binary.resolve())},
            which=lambda _: None,
            module_origin=None,
        )

    assert exit_code == 2
    assert observed["argv"] == [
        str(binary.resolve()),
        "--launcher-schema",
        "1",
        "--toolkit-major",
        "0",
        "onboard",
        "--repo",
        str(ABS_REPO),
        "--json",
    ]
    assert observed["shell"] is False
    assert observed["capture_output"] is True


def test_launcher_override_rejects_shell_command_string(capsys) -> None:
    launcher = load_launcher()

    exit_code = launcher.main(
        ["--repo", str(ABS_REPO)],
        env={"GOAL_LIFECYCLE_BIN": "python -m goal_lifecycle"},
        which=lambda _: None,
        module_origin=None,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["failure_code"] == "invalid_binary_override"


def test_launcher_rejects_windows_non_executable_file(capsys, monkeypatch) -> None:
    launcher = load_launcher()
    with launcher_test_dir() as temp_dir:
        document = temp_dir / "README.md"
        document.write_text("not executable", encoding="utf-8")
        monkeypatch.setattr(launcher.os, "name", "nt")
        exit_code = launcher.main(["--repo", str(ABS_REPO)], env={"GOAL_LIFECYCLE_BIN": str(document.resolve())}, which=lambda _: None, module_origin=None)
        payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["failure_code"] == "invalid_binary_override"


def test_launcher_rejects_incompatible_cli_output(capsys, monkeypatch) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "resolve_command", lambda **_: ["goal-lifecycle"])
    monkeypatch.setattr(launcher.subprocess, "run", lambda *_, **__: type("Completed", (), {"returncode": 2, "stdout": "", "stderr": "unknown option"})())

    exit_code = launcher.main(["--repo", str(ABS_REPO)], env={}, which=lambda _: None, module_origin=None)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["failure_code"] == "incompatible_cli"


def test_launcher_rejects_windows_batch_before_subprocess(capsys, monkeypatch) -> None:
    launcher = load_launcher()
    with launcher_test_dir() as temp_dir:
        batch = temp_dir / "goal-lifecycle.cmd"
        batch.write_text("@echo off", encoding="utf-8")
        monkeypatch.setattr(launcher.os, "name", "nt")
        called = False

        def fail_if_called(*args, **kwargs):
            nonlocal called
            called = True
            raise AssertionError("subprocess must not run")

        monkeypatch.setattr(launcher.subprocess, "run", fail_if_called)
        exit_code = launcher.main(["--repo", str(ABS_REPO)], env={"GOAL_LIFECYCLE_BIN": str(batch.resolve())}, which=lambda _: None, module_origin=None)
        payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["failure_code"] == "invalid_binary_override"
    assert called is False
