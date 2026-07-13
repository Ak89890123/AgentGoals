from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from agentgoals.aggregate import aggregate_entries
from agentgoals.validate import load_json, validate_state


def query_state(path: Path) -> dict[str, Any]:
    validate_state(path)
    payload = load_json(path)
    return queue_payload(payload["queue"], payload["entries"])


def query_registry(path: Path) -> dict[str, Any]:
    entries, queue = aggregate_entries(path)
    return queue_payload(queue, [asdict(entry) for entry in entries])


def queue_payload(queue: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        (entry for entry in entries if entry["scheduling"]["queue_position"] is not None),
        key=lambda entry: (entry["scheduling"]["queue_position"], entry["goal_key"]),
    )
    invalid = sorted(
        (entry for entry in entries if entry["scheduling"]["status"] == "invalid"),
        key=lambda entry: entry["goal_key"],
    )
    return {
        "version": 1,
        "queue": queue,
        "entries": [
            {
                "goal_key": entry["goal_key"],
                "title": entry["title"],
                "project": entry["project"],
                "lifecycle_status": entry["status"],
                "scheduling_status": entry["scheduling"]["status"],
                "priority": entry["scheduling"]["priority"],
                "queue_position": entry["scheduling"]["queue_position"],
                "depends_on": entry["scheduling"]["depends_on"],
                "unmet_dependencies": entry["scheduling"]["unmet_dependencies"],
                "contract_path": entry["contract_path"],
            }
            for entry in ordered
        ],
        "invalid_entries": [
            {
                "goal_key": entry["goal_key"],
                "issues": entry["issues"],
                "contract_path": entry["contract_path"],
            }
            for entry in invalid
        ],
    }


def render_human(payload: dict[str, Any]) -> str:
    queue = payload["queue"]
    lines = [
        f"next_goal={queue['next_goal'] or 'none'}",
        f"next_planned_goal={queue['next_planned_goal'] or 'none'}",
        f"open={queue['open_count']} runnable={queue['runnable_count']} invalid={queue['invalid_count']}",
    ]
    for entry in payload["entries"]:
        unmet = ",".join(entry["unmet_dependencies"]) or "none"
        lines.append(
            f"{entry['queue_position']}. {entry['goal_key']} "
            f"status={entry['scheduling_status']} priority={entry['priority']} unmet={unmet}"
        )
    for entry in payload["invalid_entries"]:
        lines.append(f"invalid {entry['goal_key']} issues={','.join(entry['issues'])}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the deterministic Goal queue without modifying source files.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path)
    source.add_argument("--registry", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    payload = query_state(args.state) if args.state else query_registry(args.registry)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(render_human(payload))


if __name__ == "__main__":
    main()
