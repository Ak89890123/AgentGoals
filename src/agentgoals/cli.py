from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from agentgoals import __version__
from agentgoals import doctor, onboard

LAUNCHER_SCHEMA_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentgoals", description="Portable goal lifecycle management for AI coding agents.")
    parser.add_argument("--version", action="version", version=f"agentgoals {__version__}")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("onboard", add_help=False, help="Safely onboard one explicit repository.")
    commands.add_parser("doctor", add_help=False, help="Diagnose toolkit availability and compatibility.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["--launcher-schema"]:
        if len(arguments) < 4 or arguments[1] != str(LAUNCHER_SCHEMA_VERSION) or arguments[2] != "--toolkit-major":
            return 1
        if arguments[3] != __version__.split(".", 1)[0]:
            return 1
        arguments = arguments[4:]
    if not arguments:
        build_parser().print_help()
        return 0
    if arguments[0] == "onboard":
        return onboard.main(arguments[1:])
    if arguments[0] == "doctor":
        return doctor.main(arguments[1:])
    try:
        build_parser().parse_args(arguments)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
