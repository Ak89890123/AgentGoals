from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable

from agentgoals.validate import validate_state


OPEN_STATUSES = {"draft", "review_pending", "ready", "in_progress", "blocked"}
RUNNABLE_SCHEDULING = {"runnable", "in_progress"}
BLOCKED_SCHEDULING = {"blocked", "dependency_blocked"}
SOURCE_FIELDS = {"contract_path", "plan_path", "evidence_path"}


class DashboardError(ValueError):
    """An actionable error safe to display in the desktop application."""


@dataclass(frozen=True)
class DashboardFilters:
    query: str = ""
    status: str = "all"
    project: str = "all"
    owner: str = "all"
    root_id: str = "all"
    health: str = "all"


@dataclass(frozen=True)
class DashboardSummary:
    total: int
    open: int
    runnable: int
    blocked: int
    review_pending: int
    stale: int
    completed: int
    invalid: int


@dataclass(frozen=True)
class DashboardOptions:
    statuses: tuple[str, ...]
    projects: tuple[str, ...]
    owners: tuple[str, ...]
    roots: tuple[str, ...]
    health: tuple[str, ...]


@dataclass(frozen=True)
class DashboardEntry:
    id: str
    title: str
    status: str
    project: str
    root_id: str
    goal_key: str
    goal_root: str
    contract_path: str
    plan_path: str | None
    evidence_path: str | None
    owner: str | None
    updated: str | None
    completed: str | None
    review_required: bool
    review_verdict: str | None
    evidence_status: str | None
    health_status: str
    health_findings: tuple[str, ...]
    scheduling_status: str
    queue_position: int | None
    priority: int
    unmet_dependencies: tuple[str, ...]
    issues: tuple[str, ...]
    blocked_reason: str | None
    next_action: str | None
    search_blob: str

    @property
    def display_owner(self) -> str:
        return self.owner or "Unassigned"

    @property
    def issue_label(self) -> str:
        return ", ".join(self.issues) if self.issues else "Clear"

    @property
    def health_label(self) -> str:
        if self.health_findings:
            return f"{self.health_status}: {', '.join(self.health_findings)}"
        return self.health_status

    def with_path(self, field_name: str, value: str | None) -> DashboardEntry:
        if field_name not in SOURCE_FIELDS:
            raise DashboardError(f"Unsupported source field: {field_name}")
        return replace(self, **{field_name: value})


@dataclass(frozen=True)
class RepositoryGroup:
    root_id: str
    entries: tuple[DashboardEntry, ...]
    total: int
    open: int
    runnable: int
    blocked: int


@dataclass(frozen=True)
class DashboardModel:
    generated_at: str
    next_goal: str | None
    next_planned_goal: str | None
    summary: DashboardSummary
    options: DashboardOptions
    entries: tuple[DashboardEntry, ...]


def load_dashboard(path: Path) -> DashboardModel:
    state_path = path.resolve()
    if not state_path.is_file():
        raise DashboardError(f"Goal STATE not found: {state_path}")
    try:
        validate_state(state_path)
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
        return build_dashboard(payload)
    except DashboardError:
        raise
    except Exception as exc:
        raise DashboardError(f"Invalid Goal STATE at {state_path}: {exc}") from exc


def build_dashboard(payload: dict[str, Any]) -> DashboardModel:
    if payload.get("version") != 2 or not isinstance(payload.get("entries"), list):
        raise DashboardError("Invalid Goal STATE payload: expected version 2 with entries")

    entries = tuple(sorted((_entry_from_payload(item) for item in payload["entries"]), key=_entry_sort_key))
    queue = payload.get("queue", {})
    summary = DashboardSummary(
        total=len(entries),
        open=sum(entry.status in OPEN_STATUSES for entry in entries),
        runnable=sum(entry.scheduling_status in RUNNABLE_SCHEDULING for entry in entries),
        blocked=sum(
            entry.status == "blocked" or entry.scheduling_status in BLOCKED_SCHEDULING for entry in entries
        ),
        review_pending=sum(
            entry.status == "review_pending"
            or "review_pending" in entry.issues
            or (entry.review_required and entry.review_verdict == "pending")
            for entry in entries
        ),
        stale=sum("health_stale" in entry.issues or "health_stale" in entry.health_findings for entry in entries),
        completed=sum(entry.status == "completed" for entry in entries),
        invalid=int(queue.get("invalid_count", 0)),
    )
    options = DashboardOptions(
        statuses=_sorted_unique(entry.status for entry in entries),
        projects=_sorted_unique(entry.project for entry in entries),
        owners=_sorted_unique(entry.display_owner for entry in entries),
        roots=_sorted_unique(entry.root_id for entry in entries),
        health=_sorted_unique(entry.health_status for entry in entries),
    )
    return DashboardModel(
        generated_at=str(payload.get("generated_at", "")),
        next_goal=_optional_string(queue.get("next_goal")),
        next_planned_goal=_optional_string(queue.get("next_planned_goal")),
        summary=summary,
        options=options,
        entries=entries,
    )


def filter_dashboard_entries(
    entries: Iterable[DashboardEntry], filters: DashboardFilters
) -> list[DashboardEntry]:
    query = filters.query.strip().casefold()
    result = []
    for entry in entries:
        if query and query not in entry.search_blob:
            continue
        if filters.status != "all" and entry.status != filters.status:
            continue
        if filters.project != "all" and entry.project != filters.project:
            continue
        if filters.owner != "all" and entry.display_owner != filters.owner:
            continue
        if filters.root_id != "all" and entry.root_id != filters.root_id:
            continue
        if filters.health != "all" and entry.health_status != filters.health:
            continue
        result.append(entry)
    return result


def group_dashboard_entries(entries: Iterable[DashboardEntry]) -> list[RepositoryGroup]:
    """Group a queue-ordered result set by repository, preserving first appearance."""
    grouped: dict[str, list[DashboardEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.root_id, []).append(entry)
    return [
        RepositoryGroup(
            root_id=root_id,
            entries=tuple(repo_entries),
            total=len(repo_entries),
            open=sum(entry.status in OPEN_STATUSES for entry in repo_entries),
            runnable=sum(entry.scheduling_status in RUNNABLE_SCHEDULING for entry in repo_entries),
            blocked=sum(
                entry.status == "blocked" or entry.scheduling_status in BLOCKED_SCHEDULING
                for entry in repo_entries
            ),
        )
        for root_id, repo_entries in grouped.items()
    ]


def resolve_entry_path(entry: DashboardEntry, field_name: str) -> Path:
    if field_name not in SOURCE_FIELDS:
        raise DashboardError(f"Unsupported source field: {field_name}")
    raw_path = getattr(entry, field_name)
    if not raw_path:
        raise DashboardError(f"{field_name} is unavailable for {entry.goal_key}")
    path = Path(raw_path)
    root = Path(entry.goal_root)
    if not path.is_absolute():
        raise DashboardError(f"{field_name} must be absolute: {path}")
    if not root.is_absolute():
        raise DashboardError(f"goal_root must be absolute: {root}")
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise DashboardError(f"{field_name} is outside registered goal root: {resolved_path}") from exc
    if not resolved_path.is_file():
        raise DashboardError(f"{field_name} does not exist: {resolved_path}")
    return resolved_path


class DashboardSession:
    def __init__(self, state_path: Path, opener: Callable[[Path], object] | None = None) -> None:
        self.state_path = state_path.resolve()
        self._opener = opener or _open_with_system
        self.model: DashboardModel | None = None

    def refresh(self) -> DashboardModel:
        self.model = load_dashboard(self.state_path)
        return self.model

    def open_source(self, goal_key: str, field_name: str) -> Path:
        if self.model is None:
            raise DashboardError("Refresh the dashboard before opening a source file")
        entry = next((item for item in self.model.entries if item.goal_key == goal_key), None)
        if entry is None:
            raise DashboardError(f"Goal is no longer present: {goal_key}")
        path = resolve_entry_path(entry, field_name)
        self._opener(path)
        return path


def _entry_from_payload(item: dict[str, Any]) -> DashboardEntry:
    review = item.get("review") or {}
    evidence = item.get("evidence") or {}
    health = item.get("health") or {}
    scheduling = item.get("scheduling") or {}
    findings = tuple(
        str(finding.get("code", "unknown"))
        for finding in health.get("findings", [])
        if isinstance(finding, dict)
    )
    issues = tuple(str(issue) for issue in item.get("issues", []))
    owner = _optional_string(item.get("owner"))
    search_parts = [
        item.get("id"),
        item.get("title"),
        item.get("project"),
        item.get("root_id"),
        item.get("goal_key"),
        owner or "Unassigned",
        item.get("status"),
        scheduling.get("status"),
        health.get("status"),
        item.get("blocked_reason"),
        item.get("next_action"),
        *issues,
        *findings,
    ]
    return DashboardEntry(
        id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        status=str(item.get("status", "")),
        project=str(item.get("project", "")),
        root_id=str(item.get("root_id", "")),
        goal_key=str(item.get("goal_key", "")),
        goal_root=str(item.get("goal_root", "")),
        contract_path=str(item.get("contract_path", "")),
        plan_path=_optional_string(item.get("plan_path")),
        evidence_path=_optional_string(item.get("evidence_path")),
        owner=owner,
        updated=_optional_string(item.get("updated")),
        completed=_optional_string(item.get("completed")),
        review_required=bool(review.get("required", False)),
        review_verdict=_optional_string(review.get("verdict")),
        evidence_status=_optional_string(evidence.get("status")),
        health_status=str(health.get("status", "disabled")),
        health_findings=findings,
        scheduling_status=str(scheduling.get("status", "invalid")),
        queue_position=scheduling.get("queue_position"),
        priority=int(scheduling.get("priority", 0)),
        unmet_dependencies=tuple(str(value) for value in scheduling.get("unmet_dependencies", [])),
        issues=issues,
        blocked_reason=_optional_string(item.get("blocked_reason")),
        next_action=_optional_string(item.get("next_action")),
        search_blob=" ".join(str(value) for value in search_parts if value is not None).casefold(),
    )


def _entry_sort_key(entry: DashboardEntry) -> tuple[int, int, str]:
    completed_rank = 1 if entry.status in {"completed", "cancelled"} else 0
    return completed_rank, entry.queue_position or 1_000_000, entry.goal_key


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _open_with_system(path: Path) -> object:
    if os.name != "nt" or not hasattr(os, "startfile"):
        raise DashboardError("System file opening is available only on Windows in this release")
    return os.startfile(path)  # type: ignore[attr-defined, no-any-return]
