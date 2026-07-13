from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from agentgoals.resolver import ResolutionError, resolve_command, run_resolved


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")
    path.chmod(0o755)
    return path.resolve()


@contextmanager
def resolver_test_dir() -> Iterator[Path]:
    path = Path(".tmp") / "resolver-test-data" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path.resolve()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_absolute_binary_override_has_highest_priority() -> None:
    with resolver_test_dir() as temp_dir:
        binary = make_executable(temp_dir / "bin with spaces" / "agentgoals.exe")

        resolved = resolve_command(
            env={"AGENTGOALS_BIN": str(binary)},
            which=lambda _: None,
            module_origin=None,
        )

        assert resolved.route == "override"
        assert resolved.argv == (str(binary),)


@pytest.mark.parametrize("value", ["agentgoals", "python -m agentgoals", "C:/missing/tool.exe"])
def test_binary_override_rejects_non_absolute_or_non_file_values(value) -> None:
    with pytest.raises(ResolutionError, match="AGENTGOALS_BIN"):
        resolve_command(env={"AGENTGOALS_BIN": value}, which=lambda _: None, module_origin=None)


def test_path_executable_is_default_user_route() -> None:
    with resolver_test_dir() as temp_dir:
        binary = make_executable(temp_dir / ("agentgoals.exe" if os.name == "nt" else "agentgoals"))

        resolved = resolve_command(env={}, which=lambda _: str(binary), module_origin=None)

        assert resolved.route == "path"
        assert resolved.argv == (str(binary),)


def test_developer_home_requires_matching_venv_and_module() -> None:
    with resolver_test_dir() as temp_dir:
        home = temp_dir / "toolkit"
        interpreter = make_executable(home / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        module = home / "src" / "agentgoals" / "__init__.py"
        module.parent.mkdir(parents=True)
        module.write_text('__version__ = "0.1.0"', encoding="utf-8")

        resolved = resolve_command(
            env={"AGENTGOALS_HOME": str(home.resolve())},
            which=lambda _: None,
            module_origin=None,
        )

        assert resolved.route == "developer_home"
        assert resolved.argv == (str(interpreter), "-m", "agentgoals.cli")


def test_current_interpreter_module_is_last_fallback() -> None:
    with resolver_test_dir() as temp_dir:
        module = temp_dir / "site-packages" / "agentgoals" / "__init__.py"
        module.parent.mkdir(parents=True)
        module.write_text('__version__ = "0.1.0"', encoding="utf-8")

        resolved = resolve_command(env={}, which=lambda _: None, module_origin=module.resolve())

        assert resolved.route == "module"
        assert resolved.argv[1:] == ("-m", "agentgoals.cli")


def test_missing_tool_returns_one_install_remediation() -> None:
    with pytest.raises(ResolutionError) as captured:
        resolve_command(env={}, which=lambda _: None, module_origin=None)

    assert captured.value.failure_code == "cli_not_found"
    assert captured.value.remediation == {
        "action": "provide_release_coordinates",
        "argv": ["OWNER", "REPO", "TAG"],
    }


def test_resolved_command_runs_without_shell(monkeypatch) -> None:
    with resolver_test_dir() as temp_dir:
        binary = make_executable(temp_dir / ("agentgoals.exe" if os.name == "nt" else "agentgoals"))
        resolved = resolve_command(env={}, which=lambda _: str(binary), module_origin=None)
        observed = {}

        def fake_run(argv, **kwargs):
            observed["argv"] = argv
            observed.update(kwargs)
            return "completed"

        monkeypatch.setattr("agentgoals.resolver.subprocess.run", fake_run)

        result = run_resolved(resolved, ["doctor", "--json"])

        assert result == "completed"
        assert observed["argv"] == [str(binary), "doctor", "--json"]
        assert observed["shell"] is False
