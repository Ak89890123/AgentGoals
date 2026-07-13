from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

from agentgoals.health import disabled_health
from agentgoals.io import atomic_write_text
from agentgoals.reconcile import StateEntry
from agentgoals.render import render_state_markdown
from agentgoals.scheduling import apply_scheduling, normalize_scheduling
from agentgoals.validate import SCHEMA_DIR, validate_state


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


def aggregate(
    global_registry_path: Path,
    out_dir: Path,
    operation_id: str | None = None,
) -> list[StateEntry]:
    entries, queue = aggregate_entries(global_registry_path)
    write_outputs(entries, out_dir, queue, operation_id=operation_id or uuid4().hex)
    return entries


def aggregate_entries(global_registry_path: Path) -> tuple[list[StateEntry], dict[str, Any]]:
    roots = load_global_registry(global_registry_path)
    entries: list[StateEntry] = []

    for root in roots:
        if not root.active:
            continue
        entries.extend(read_repo_state(root))

    queue = apply_scheduling(entries, strict_missing=True)
    entries.sort(key=lambda entry: (entry.scheduling["queue_position"] is None, entry.scheduling["queue_position"] or 0, entry.goal_key))
    return entries, queue


def load_global_registry(path: Path) -> list[GlobalRegistryRoot]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_instance(data, GLOBAL_REGISTRY_SCHEMA)
    roots = []
    for item in data.get("roots", []):
        repo_root = Path(item["repo_root"])
        goal_root = Path(item["goal_root"])
        state_path = Path(item["state_path"])
        require_absolute_path(repo_root, item["id"], "repo_root")
        require_absolute_path(goal_root, item["id"], "goal_root")
        require_absolute_path(state_path, item["id"], "state_path")
        ensure_within(goal_root, repo_root, item["id"], "goal_root", "repo_root")
        ensure_within(state_path, repo_root, item["id"], "state_path", "repo_root")
        roots.append(
            GlobalRegistryRoot(
                id=item["id"],
                label=item.get("label", item["id"]),
                repo_root=repo_root,
                goal_root=goal_root,
                state_path=state_path,
                scope=item.get("scope", "repo"),
                project=item.get("project", item["id"]),
                active=bool(item.get("active", True)),
            )
        )
    ids = [root.id for root in roots]
    if len(ids) != len(set(ids)):
        raise ValueError("Global registry contains duplicate root IDs")
    repo_roots = [str(root.repo_root.resolve()).casefold() for root in roots]
    if len(repo_roots) != len(set(repo_roots)):
        raise ValueError("Global registry contains duplicate repository paths")
    return roots


def read_repo_state(root: GlobalRegistryRoot) -> list[StateEntry]:
    if not root.state_path.exists():
        return [aggregate_issue_entry(root, "missing", f"Registered STATE not found: {root.state_path}", ["missing"])]

    try:
        validate_state(root.state_path)
        text = root.state_path.read_text(encoding="utf-8-sig")
        payload = json.loads(text)
        return [entry_from_payload(item, root) for item in payload.get("entries", [])]
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


def entry_from_payload(item: dict[str, Any], root: GlobalRegistryRoot) -> StateEntry:
    goal_root = normalize_entry_path(item["goal_root"], root)
    ensure_within(goal_root, root.goal_root, item["id"], "goal_root", "registered goal_root")
    contract_path = normalize_optional_entry_path(item["contract_path"], root)
    if contract_path:
        ensure_within(contract_path, root.goal_root, item["id"], "contract_path", "registered goal_root")
    plan_path = normalize_optional_entry_path(item["plan_path"], root)
    if plan_path:
        ensure_within(plan_path, root.goal_root, item["id"], "plan_path", "registered goal_root")
    evidence_path = normalize_optional_entry_path(item["evidence_path"], root)
    if evidence_path:
        ensure_within(evidence_path, root.goal_root, item["id"], "evidence_path", "registered goal_root")

    source_root_id = item["root_id"]
    scheduling = dict(item["scheduling"])
    scheduling["depends_on"] = [
        rebase_dependency(dependency, source_root_id, root.id)
        for dependency in scheduling["depends_on"]
    ]

    return StateEntry(
        id=item["id"],
        title=item["title"],
        status=item["status"],
        project=item["project"],
        root_id=root.id,
        goal_key=f"{root.id}/{item['id']}",
        goal_root=str(goal_root),
        contract_path=str(contract_path) if contract_path else "",
        plan_path=str(plan_path) if plan_path else None,
        evidence_path=str(evidence_path) if evidence_path else None,
        owner=item["owner"],
        updated=item["updated"],
        completed=item["completed"],
        review=item["review"],
        evidence=item["evidence"],
        health=item.get("health", disabled_health()),
        scheduling=scheduling,
        next_action=item["next_action"],
        blocked_reason=item["blocked_reason"],
        source_hash=item["source_hash"],
        last_seen=item["last_seen"],
        issues=list(item["issues"]),
    )


def require_absolute_path(path: Path, root_id: str, field_name: str) -> None:
    if not path.is_absolute():
        raise ValueError(f"roots[{root_id}].{field_name} must be an absolute path: {path}")


def normalize_entry_path(value: str, root: GlobalRegistryRoot) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root.repo_root / path


def normalize_optional_entry_path(value: str | None, root: GlobalRegistryRoot) -> Path | None:
    if not value:
        return None
    return normalize_entry_path(value, root)


def rebase_dependency(dependency: str, source_root_id: str, global_root_id: str) -> str:
    prefix = f"{source_root_id}/"
    if dependency.startswith(prefix):
        return f"{global_root_id}/{dependency[len(prefix):]}"
    return dependency


def ensure_within(path: Path, base: Path, root_id: str, field_name: str, base_name: str) -> None:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"{root_id}.{field_name} is outside {base_name}: {path}") from exc


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
        root_id=root.id,
        goal_key=f"{root.id}/{root.id}",
        goal_root=str(root.goal_root),
        contract_path="",
        plan_path=None,
        evidence_path=None,
        owner=None,
        updated=None,
        completed=None,
        review={"required": False, "verdict": None},
        evidence={"status": None},
        health=disabled_health(),
        scheduling=normalize_scheduling(None, root.id)[0],
        next_action=None,
        blocked_reason=reason,
        source_hash=source_hash,
        last_seen=now_iso(),
        issues=issues,
    )


def write_outputs(
    entries: list[StateEntry],
    out_dir: Path,
    queue: dict[str, Any],
    *,
    operation_id: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "operation_id": operation_id,
        "generated_at": now_iso(),
        "queue": queue,
        "entries": [asdict(entry) for entry in entries],
    }
    atomic_write_text(
        out_dir / "STATE.json",
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    atomic_write_text(out_dir / "STATE.md", render_state_markdown(entries))


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
        return hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
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
