from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agentgoals.frontmatter import parse_frontmatter
from agentgoals.refresh import ensure_within, main as refresh_main, resolve_refresh_paths

GOAL_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move one validated completed goal and refresh derived STATE exactly once."
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--global-registry", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def complete_goal(
    repo_arg: Path,
    goal_id: str,
    global_registry: Path,
    *,
    refresher: Callable[[Sequence[str]], int] = refresh_main,
    preflight: Callable[[Path, Path], object] = resolve_refresh_paths,
) -> dict[str, Any]:
    if not repo_arg.is_absolute():
        raise ValueError("--repo must be an absolute path")
    if not global_registry.is_absolute():
        raise ValueError("--global-registry must be an absolute path")
    if not GOAL_ID.fullmatch(goal_id):
        raise ValueError("--goal-id must be stable kebab-case")

    repo = repo_arg.resolve(strict=True)
    preflight(repo, global_registry)
    source = repo / "goals" / "active" / goal_id
    destination = repo / "goals" / "completed" / goal_id
    if not source.is_dir():
        raise ValueError(f"active goal directory not found: {source}")
    if destination.exists():
        raise ValueError(f"completed goal destination already exists: {destination}")
    ensure_within(source.resolve(strict=True), repo, "active goal")
    goals_root = (repo / "goals").resolve(strict=True)
    ensure_within(goals_root, repo, "goals root")
    validate_completion(source, goal_id)

    destination.parent.mkdir(parents=True, exist_ok=True)
    completed_root = destination.parent.resolve(strict=True)
    ensure_within(completed_root, goals_root, "completed goal root")
    source.rename(destination)
    refresh_args = ["--repo", str(repo), "--global-registry", str(global_registry), "--json"]
    refresh_stdout = io.StringIO()
    with contextlib.redirect_stdout(refresh_stdout):
        refresh_exit = refresher(refresh_args)
    refresh_text = refresh_stdout.getvalue().strip()
    try:
        refresh_result = json.loads(refresh_text) if refresh_text else None
    except json.JSONDecodeError:
        refresh_result = {"raw_output": refresh_text}
    return {
        "version": 1,
        "outcome": "completed" if refresh_exit == 0 else "completed_state_refresh_issues",
        "exit_code": refresh_exit,
        "goal_id": goal_id,
        "source": str(source),
        "destination": str(destination),
        "moved": True,
        "refresh_invocations": 1,
        "refresh_exit_code": refresh_exit,
        "refresh_result": refresh_result,
    }


def validate_completion(goal_dir: Path, goal_id: str) -> None:
    required = {
        "CONTRACT.md": ("id", goal_id),
        "PLAN.md": ("goal_id", goal_id),
        "EVIDENCE.md": ("goal_id", goal_id),
    }
    metadata: dict[str, dict[str, Any]] = {}
    for name, identity in required.items():
        path = goal_dir / name
        if not path.is_file():
            raise ValueError(f"completion requires {path}")
        document = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        metadata[name] = document.metadata
        if document.metadata.get(identity[0]) != identity[1]:
            raise ValueError(f"{name} {identity[0]} must equal {goal_id}")

    if metadata["CONTRACT.md"].get("status") != "completed":
        raise ValueError("CONTRACT.md status must be completed")
    if not metadata["CONTRACT.md"].get("completed"):
        raise ValueError("CONTRACT.md completed date is required")
    if metadata["PLAN.md"].get("status") != "completed":
        raise ValueError("PLAN.md status must be completed")
    if metadata["EVIDENCE.md"].get("status") != "complete":
        raise ValueError("EVIDENCE.md status must be complete")
    review = metadata["CONTRACT.md"].get("review") or {}
    if review.get("required") and review.get("verdict") != "PASS":
        raise ValueError("required Contract review verdict must be PASS")
    evidence_review = metadata["EVIDENCE.md"].get("review") or {}
    if review.get("required") and evidence_review.get("verdict") != "PASS":
        raise ValueError("required Evidence review verdict must be PASS")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = complete_goal(args.repo, args.goal_id, args.global_registry)
    except (OSError, ValueError) as exc:
        print(f"agentgoals complete failed: {exc}", file=sys.stderr)
        return 1
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Completed {result['goal_id']}; refresh exit {result['refresh_exit_code']}")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
