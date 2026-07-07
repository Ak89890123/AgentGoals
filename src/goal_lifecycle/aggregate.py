from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from goal_lifecycle.reconcile import StateEntry
from goal_lifecycle.render import render_state_markdown
from goal_lifecycle.validate import SCHEMA_DIR, validate_state


GLOBAL_REGISTRY_SCHEMA = SCHEMA_DIR / "global-registry.schema.json"


@dataclass(frozen=True)
class GlobalRegistryRoot:
    id: str
    label: str
    repo_root: Path
    goal_root: Path
    state_path: Path
    scope: str
    project: str
    active: bool


def aggregate(global_registry_path: Path, out_dir: Path) -> list[StateEntry]:
    roots = load_global_registry(global_registry_path)
    entries: list[StateEntry] = []

    for root in roots:
        if not root.active:
            continue
        entries.extend(read_repo_state(root))

    entries.sort(key=lambda entry: (entry.status, entry.project, entry.id))
    write_outputs(entries, out_dir)
    return entries


def load_global_registry(path: Path) -> list[GlobalRegistryRoot]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_instance(data, GLOBAL_REGISTRY_SCHEMA)
    roots = []
    for item in data.get("roots", []):
        roots.append(
            GlobalRegistryRoot(
                id=item["id"],
                label=item.get("label", item["id"]),
                repo_root=Path(item["repo_root"]),
                goal_root=Path(item["goal_root"]),
                state_path=Path(item["state_path"]),
                scope=item.get("scope", "repo"),
                project=item.get("project", item["id"]),
                active=bool(item.get("active", True)),
            )
        )
    return roots


def read_repo_state(root: GlobalRegistryRoot) -> list[StateEntry]:
    if not root.state_path.exists():
        return [aggregate_issue_entry(root, "missing", f"Registered STATE not found: {root.state_path}", ["missing"])]

    try:
        validate_state(root.state_path)
        text = root.state_path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except Exception as exc:
        return [
            aggregate_issue_entry(
                root,
                "parse_error",
                f"{type(exc).__name__}: {exc}",
                ["parse_error"],
                source_hash=hash_file_if_readable(root.state_path),
            )
        ]

    return [entry_from_payload(item) for item in payload.get("entries", [])]


def entry_from_payload(item: dict[str, Any]) -> StateEntry:
    return StateEntry(
        id=item["id"],
        title=item["title"],
        status=item["status"],
        project=item["project"],
        goal_root=item["goal_root"],
        contract_path=item["contract_path"],
        plan_path=item["plan_path"],
        evidence_path=item["evidence_path"],
        owner=item["owner"],
        updated=item["updated"],
        completed=item["completed"],
        review=item["review"],
        evidence=item["evidence"],
        next_action=item["next_action"],
        blocked_reason=item["blocked_reason"],
        source_hash=item["source_hash"],
        last_seen=item["last_seen"],
        issues=list(item["issues"]),
    )


def aggregate_issue_entry(
    root: GlobalRegistryRoot,
    status: str,
    reason: str,
    issues: list[str],
    source_hash: str = "",
) -> StateEntry:
    return StateEntry(
        id=root.id,
        title=root.label,
        status=status,
        project=root.project,
        goal_root=str(root.goal_root),
        contract_path="",
        plan_path=None,
        evidence_path=None,
        owner=None,
        updated=None,
        completed=None,
        review={"required": False, "verdict": None},
        evidence={"status": None},
        next_action=None,
        blocked_reason=reason,
        source_hash=source_hash,
        last_seen=now_iso(),
        issues=issues,
    )


def write_outputs(entries: list[StateEntry], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": now_iso(),
        "entries": [asdict(entry) for entry in entries],
    }
    (out_dir / "STATE.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "STATE.md").write_text(render_state_markdown(entries), encoding="utf-8")


def validate_instance(instance: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise ValueError("\n".join(messages))


def hash_file_if_readable(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    except Exception:
        return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate repo-local Goal STATE files from a global registry.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    aggregate(args.registry, args.out)


if __name__ == "__main__":
    main()
