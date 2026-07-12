from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from goal_lifecycle import __version__
from goal_lifecycle.validate import SCHEMA_DIR


SUPPORTED_PYTHON = (3, 11)


def redact_origin(path: Path) -> str:
    resolved = path.expanduser().resolve()
    home = Path.home().resolve()
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return str(resolved)
    return str(Path("<home>") / relative)


def build_doctor_result(
    *,
    route: str,
    origin: Path,
    python_version: tuple[int, int, int],
    toolkit_version: str,
    schemas_available: bool,
) -> tuple[dict, int]:
    base = {
        "version": 1,
        "route": route,
        "toolkit_version": toolkit_version,
        "python_version": ".".join(str(part) for part in python_version),
        "origin": redact_origin(origin),
    }
    if python_version[:2] < SUPPORTED_PYTHON:
        return (
            {
                **base,
                "status": "action_required",
                "failure_code": "unsupported_python",
                "remediation": {
                    "action": "provide_release_coordinates",
                    "argv": ["OWNER", "REPO", "TAG", "PYTHON>=3.11"],
                },
            },
            2,
        )
    if not schemas_available:
        return (
            {
                **base,
                "status": "invalid",
                "failure_code": "schemas_missing",
                "remediation": {
                    "action": "provide_release_coordinates",
                    "argv": ["OWNER", "REPO", "TAG"],
                },
            },
            1,
        )
    return ({**base, "status": "ready", "failure_code": None, "remediation": None}, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose the portable Goal Lifecycle CLI installation.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def render_human(payload: dict) -> str:
    line = f"status={payload['status']} route={payload['route']} version={payload['toolkit_version']}"
    if payload["failure_code"]:
        line += f" failure={payload['failure_code']}"
    return line


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    version_info = sys.version_info
    payload, exit_code = build_doctor_result(
        route="console_script",
        origin=Path(sys.argv[0]),
        python_version=(version_info.major, version_info.minor, version_info.micro),
        toolkit_version=__version__,
        schemas_available=(SCHEMA_DIR / "doctor-result.schema.json").is_file()
        and (SCHEMA_DIR / "goal-state.schema.json").is_file(),
    )
    print(json.dumps(payload, ensure_ascii=False) if args.json_output else render_human(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
