from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def resolve_schema_dir(runtime_root: Path | None = None) -> Path:
    roots = []
    if runtime_root is not None:
        roots.append(runtime_root)
    else:
        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            roots.append(Path(bundled_root))
        roots.append(Path(__file__).resolve().parents[2])
    for root in roots:
        candidate = (root / "schemas").resolve()
        if (candidate / "goal-state.schema.json").is_file():
            return candidate
    return (roots[-1] / "schemas").resolve()


SCHEMA_DIR = resolve_schema_dir()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_json_file(instance_path: Path, schema_path: Path) -> None:
    instance = load_json(instance_path)
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise ValueError("\n".join(messages))


def validate_registry(path: Path) -> None:
    validate_json_file(path, SCHEMA_DIR / "goal-registry.schema.json")


def validate_state(path: Path) -> None:
    validate_json_file(path, SCHEMA_DIR / "goal-state.schema.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Goal Lifecycle JSON files.")
    parser.add_argument("--registry", type=Path, default=Path("registry/REGISTRY.json"))
    parser.add_argument("--state", type=Path, default=Path("outputs/STATE.json"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_registry(args.registry)
    validate_state(args.state)


if __name__ == "__main__":
    main()
