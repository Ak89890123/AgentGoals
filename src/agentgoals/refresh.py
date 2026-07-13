from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from agentgoals.aggregate import load_global_registry
from agentgoals.run import render_human, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically rebuild repository and global AgentGoals STATE."
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--global-registry", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.global_registry is None:
        print("agentgoals refresh requires --global-registry", file=sys.stderr)
        return 1

    try:
        repo, global_registry, local_out, global_out = resolve_refresh_paths(
            args.repo, args.global_registry
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"agentgoals refresh preflight failed: {exc}", file=sys.stderr)
        return 1

    summary = run_pipeline(
        registry_path=repo / "registry" / "REGISTRY.json",
        out_dir=local_out,
        global_registry_path=global_registry,
        global_out_dir=global_out,
        require_global=True,
    )
    if args.json_output:
        print(json.dumps(summary.to_dict(), ensure_ascii=False))
    else:
        print(render_human(summary))
    return summary.exit_code


def resolve_refresh_paths(repo_arg: Path, global_registry_arg: Path) -> tuple[Path, Path, Path, Path]:
    if not repo_arg.is_absolute():
        raise ValueError("--repo must be an absolute path")
    if not global_registry_arg.is_absolute():
        raise ValueError("--global-registry must be an absolute path")

    repo = repo_arg.resolve(strict=True)
    if not repo.is_dir():
        raise ValueError(f"--repo is not a directory: {repo}")
    global_registry = global_registry_arg.resolve(strict=True)
    if not global_registry.is_file():
        raise ValueError(f"--global-registry is not a file: {global_registry}")

    local_registry = (repo / "registry" / "REGISTRY.json").resolve(strict=True)
    ensure_within(local_registry, repo, "local registry")

    matches = [
        root for root in load_global_registry(global_registry)
        if root.active and root.repo_root.resolve() == repo
    ]
    if len(matches) != 1:
        raise ValueError(f"global registry must contain exactly one active root for {repo}; found {len(matches)}")
    state_path = matches[0].state_path.resolve(strict=False)
    ensure_within(state_path, repo, "registered state_path")
    if state_path.name != "STATE.json":
        raise ValueError("registered state_path must end in STATE.json")
    local_out = state_path.parent
    global_out = (repo / "outputs" / "global").resolve(strict=False)
    ensure_within(local_out, repo, "local output")
    ensure_within(global_out, repo, "global output")

    outputs_root = (repo / "outputs").resolve(strict=False)
    ensure_within(local_out, outputs_root, "registered local output")
    if local_out == global_out or is_within(local_out, global_out):
        raise ValueError("local and global output directories must not overlap")
    if is_within(global_registry, outputs_root):
        raise ValueError("--global-registry must not be inside the derived outputs directory")
    if is_within(global_registry, local_out) or is_within(global_registry, global_out):
        raise ValueError("--global-registry must not be inside a derived output directory")
    return repo, global_registry, local_out, global_out


def ensure_within(path: Path, root: Path, label: str) -> None:
    if not is_within(path, root):
        raise ValueError(f"{label} escapes --repo: {path}")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
