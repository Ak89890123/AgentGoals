from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from goal_lifecycle.frontmatter import parse_frontmatter
from goal_lifecycle.render import render_state_markdown


OPEN_STATUSES = {"draft", "review_pending", "ready", "in_progress", "blocked"}
DONE_STATUSES = {"completed", "cancelled"}


@dataclass(frozen=True)
class RegistryRoot:
    id: str
    label: str
    goal_root: Path
    scope: str
    project: str
    active: bool


@dataclass
class StateEntry:
    id: str
    title: str
    status: str
    project: str
    goal_root: str
    contract_path: str
    plan_path: str | None
    evidence_path: str | None
    owner: str | None
    updated: str | None
    completed: str | None
    review: dict[str, Any]
    evidence: dict[str, Any]
    next_action: str | None
    blocked_reason: str | None
    source_hash: str
    last_seen: str
    issues: list[str] = field(default_factory=list)


def load_registry(path: Path) -> list[RegistryRoot]:
    data = json.loads(path.read_text(encoding="utf-8"))
    roots = []
    base_dir = path.parent.parent
    for item in data.get("roots", []):
        raw_goal_root = Path(item["goal_root"])
        goal_root = raw_goal_root if raw_goal_root.is_absolute() else base_dir / raw_goal_root
        roots.append(
            RegistryRoot(
                id=item["id"],
                label=item.get("label", item["id"]),
                goal_root=goal_root,
                scope=item.get("scope", "repo"),
                project=item.get("project", item["id"]),
                active=bool(item.get("active", True)),
            )
        )
    return roots


def reconcile(registry_path: Path, out_dir: Path) -> list[StateEntry]:
    entries: list[StateEntry] = []
    for root in load_registry(registry_path):
        if not root.active:
            continue
        entries.extend(scan_goal_root(root))

    entries.sort(key=lambda entry: (entry.status, entry.project, entry.id))
    write_outputs(entries, out_dir)
    return entries


def scan_goal_root(root: RegistryRoot) -> list[StateEntry]:
    if not root.goal_root.exists():
        return [
            StateEntry(
                id=root.id,
                title=root.label,
                status="missing",
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
                blocked_reason=f"Registered goal root not found: {root.goal_root}",
                source_hash="",
                last_seen=now_iso(),
                issues=["missing"],
            )
        ]

    entries: list[StateEntry] = []
    for folder_name in ("active", "completed"):
        folder = root.goal_root / folder_name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.md")):
            entry = parse_contract_candidate(path, folder_name, root)
            if entry is not None:
                entries.append(entry)
    return entries


def parse_contract_candidate(path: Path, folder_name: str, root: RegistryRoot) -> StateEntry | None:
    try:
        text = path.read_text(encoding="utf-8")
        document = parse_frontmatter(text)
    except Exception as exc:
        return parse_error_entry(path, folder_name, root, exc)

    if document.metadata.get("type") != "goal-contract":
        return None

    goal_dir = path.parent if path.name.upper() == "CONTRACT.MD" else path.parent
    plan_path = goal_dir / "PLAN.md"
    evidence_path = goal_dir / "EVIDENCE.md"
    plan_metadata = read_optional_metadata(plan_path)
    evidence_metadata = read_optional_metadata(evidence_path)

    status = str(document.metadata.get("status") or "draft")
    issues = detect_issues(folder_name, status, plan_path, evidence_path, document.metadata, evidence_metadata)

    review = normalize_review(document.metadata.get("review"))
    evidence = {"status": evidence_metadata.get("status") if evidence_metadata else None}

    return StateEntry(
        id=str(document.metadata.get("id") or path.stem),
        title=str(document.metadata.get("title") or path.stem),
        status=status,
        project=str(document.metadata.get("project") or root.project),
        goal_root=str(root.goal_root),
        contract_path=str(path),
        plan_path=str(plan_path) if plan_path.exists() else None,
        evidence_path=str(evidence_path) if evidence_path.exists() else None,
        owner=document.metadata.get("owner"),
        updated=string_or_none(document.metadata.get("updated")),
        completed=string_or_none(document.metadata.get("completed")),
        review=review,
        evidence=evidence,
        next_action=None,
        blocked_reason=None,
        source_hash=sha256_text(text),
        last_seen=now_iso(),
        issues=issues,
    )


def read_optional_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    document = parse_frontmatter(path.read_text(encoding="utf-8"))
    return document.metadata


def detect_issues(
    folder_name: str,
    status: str,
    plan_path: Path,
    evidence_path: Path,
    contract_metadata: dict[str, Any],
    evidence_metadata: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    if folder_name == "active" and status in DONE_STATUSES:
        issues.append("status_folder_mismatch")
    if folder_name == "completed" and status in OPEN_STATUSES:
        issues.append("status_folder_mismatch")
    if contract_metadata.get("file_mode") == "directory" and not plan_path.exists():
        issues.append("missing_plan")
    if contract_metadata.get("file_mode") == "directory" and not evidence_path.exists():
        issues.append("missing_evidence")
    if evidence_metadata.get("status") in {"pending", "partial"}:
        issues.append("evidence_incomplete")

    review = normalize_review(contract_metadata.get("review"))
    if review.get("required") and review.get("verdict") in {None, "pending", "NEEDS_EVIDENCE"}:
        issues.append("review_pending")

    return issues


def parse_error_entry(path: Path, folder_name: str, root: RegistryRoot, exc: Exception) -> StateEntry:
    return StateEntry(
        id=path.stem,
        title=path.name,
        status="parse_error",
        project=root.project,
        goal_root=str(root.goal_root),
        contract_path=str(path),
        plan_path=None,
        evidence_path=None,
        owner=None,
        updated=None,
        completed=None,
        review={"required": False, "verdict": None},
        evidence={"status": None},
        next_action=None,
        blocked_reason=f"{type(exc).__name__}: {exc}",
        source_hash="",
        last_seen=now_iso(),
        issues=["parse_error"],
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


def normalize_review(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "required": bool(value.get("required", False)),
            "verdict": value.get("verdict"),
        }
    return {"required": False, "verdict": None}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value:
        return None
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile Goal Contract state from registered roots.")
    parser.add_argument("--registry", type=Path, default=Path("registry/REGISTRY.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    reconcile(args.registry, args.out)


if __name__ == "__main__":
    main()
