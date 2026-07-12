from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INSTALL_REMEDIATION = {
    "action": "provide_release_coordinates",
    "argv": ["OWNER", "REPO", "TAG"],
}


class ResolutionError(ValueError):
    def __init__(self, message: str, failure_code: str, remediation: dict[str, Any]) -> None:
        super().__init__(message)
        self.failure_code = failure_code
        self.remediation = remediation


@dataclass(frozen=True)
class ResolvedCommand:
    route: str
    argv: tuple[str, ...]
    origin: str


def is_executable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return path.suffix.lower() in {".exe", ".com"}
    return os.access(path, os.X_OK)


def resolve_command(
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    module_origin: Path | None | object = ...,
) -> ResolvedCommand:
    values = os.environ if env is None else env
    override = values.get("GOAL_LIFECYCLE_BIN")
    if override:
        binary = Path(override).expanduser()
        if not binary.is_absolute() or not is_executable_file(binary):
            raise ResolutionError(
                "GOAL_LIFECYCLE_BIN must be one absolute executable file path.",
                "invalid_binary_override",
                INSTALL_REMEDIATION,
            )
        resolved = binary.resolve()
        return ResolvedCommand("override", (str(resolved),), str(resolved))

    discovered = which("goal-lifecycle")
    if discovered:
        binary = Path(discovered)
        if binary.is_absolute() and is_executable_file(binary):
            resolved = binary.resolve()
            return ResolvedCommand("path", (str(resolved),), str(resolved))

    developer_home = values.get("GOAL_LIFECYCLE_HOME")
    if developer_home:
        home = Path(developer_home).expanduser()
        if not home.is_absolute() or not home.is_dir():
            raise ResolutionError(
                "GOAL_LIFECYCLE_HOME must be one absolute toolkit directory.",
                "invalid_home_override",
                INSTALL_REMEDIATION,
            )
        interpreter = home / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        module = home / "src" / "goal_lifecycle" / "__init__.py"
        if not is_executable_file(interpreter) or not module.is_file():
            raise ResolutionError(
                "GOAL_LIFECYCLE_HOME is missing its validated interpreter or module.",
                "invalid_home_override",
                INSTALL_REMEDIATION,
            )
        return ResolvedCommand(
            "developer_home",
            (str(interpreter.resolve()), "-m", "goal_lifecycle.cli"),
            str(module.resolve()),
        )

    origin = detect_module_origin() if module_origin is ... else module_origin
    if isinstance(origin, Path) and origin.is_absolute() and origin.is_file():
        return ResolvedCommand(
            "module",
            (sys.executable, "-m", "goal_lifecycle.cli"),
            str(origin.resolve()),
        )

    raise ResolutionError(
        "Goal Lifecycle CLI is unavailable.",
        "cli_not_found",
        INSTALL_REMEDIATION,
    )


def detect_module_origin() -> Path | None:
    spec = importlib.util.find_spec("goal_lifecycle")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).resolve()


def run_resolved(resolved: ResolvedCommand, arguments: Sequence[str]):
    return subprocess.run(
        [*resolved.argv, *arguments],
        shell=False,
        check=False,
        text=True,
    )
