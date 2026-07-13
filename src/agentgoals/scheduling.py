from __future__ import annotations

import heapq
from collections.abc import Iterable, Sequence
from typing import Any, Protocol


DEFAULT_PRIORITY = 50
DONE_STATUSES = {"completed", "cancelled"}
INVALID_STATUSES = {"missing", "parse_error"}
DYNAMIC_SCHEDULING_ISSUES = {"dependency_missing", "dependency_cycle", "duplicate_goal_key"}


class SchedulableEntry(Protocol):
    id: str
    status: str
    root_id: str
    goal_key: str
    scheduling: dict[str, Any]
    issues: list[str]


def normalize_scheduling(value: Any, root_id: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if value is None:
        source: dict[str, Any] = {}
    elif isinstance(value, dict):
        source = value
    else:
        source = {}
        errors.append("invalid_scheduling")

    priority = source.get("priority", DEFAULT_PRIORITY)
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
        priority = DEFAULT_PRIORITY
        errors.append("invalid_scheduling")

    raw_dependencies = source.get("depends_on", [])
    dependencies: list[str] = []
    if not isinstance(raw_dependencies, list):
        errors.append("invalid_scheduling")
    else:
        for raw_dependency in raw_dependencies:
            if not isinstance(raw_dependency, str) or not raw_dependency.strip():
                errors.append("invalid_scheduling")
                continue
            dependency = raw_dependency.strip().replace("\\", "/")
            if "/" not in dependency:
                dependency = f"{root_id}/{dependency}"
            if dependency.count("/") != 1 or dependency.startswith("/") or dependency.endswith("/"):
                errors.append("invalid_scheduling")
                continue
            if dependency not in dependencies:
                dependencies.append(dependency)

    return (
        {
            "priority": priority,
            "depends_on": dependencies,
            "status": "not_ready",
            "queue_position": None,
            "unmet_dependencies": [],
        },
        list(dict.fromkeys(errors)),
    )


def apply_scheduling(entries: Sequence[SchedulableEntry], *, strict_missing: bool) -> dict[str, Any]:
    by_key = {entry.goal_key: entry for entry in entries}
    for entry in entries:
        entry.issues[:] = [issue for issue in entry.issues if issue not in DYNAMIC_SCHEDULING_ISSUES]
        entry.scheduling["queue_position"] = None
        entry.scheduling["unmet_dependencies"] = []

    invalid_entries = {
        entry.goal_key
        for entry in entries
        if "invalid_scheduling" in entry.issues or entry.status in INVALID_STATUSES
    }

    goal_key_counts: dict[str, int] = {}
    for entry in entries:
        goal_key_counts[entry.goal_key] = goal_key_counts.get(entry.goal_key, 0) + 1
    for entry in entries:
        if goal_key_counts[entry.goal_key] > 1:
            append_issue(entry, "duplicate_goal_key")
            invalid_entries.add(entry.goal_key)

    for entry in entries:
        for dependency in entry.scheduling["depends_on"]:
            if dependency in by_key:
                continue
            dependency_root = dependency.split("/", 1)[0]
            if strict_missing or dependency_root == entry.root_id:
                append_issue(entry, "dependency_missing")
                invalid_entries.add(entry.goal_key)

    cycle_entries = find_cycle_entries(entries, by_key)
    for goal_key in cycle_entries:
        append_issue(by_key[goal_key], "dependency_cycle")
        invalid_entries.add(goal_key)

    for entry in entries:
        dependencies = entry.scheduling["depends_on"]
        unmet = [
            dependency
            for dependency in dependencies
            if dependency not in by_key
            or dependency in invalid_entries
            or by_key[dependency].status not in DONE_STATUSES
        ]
        entry.scheduling["unmet_dependencies"] = unmet
        entry.scheduling["status"] = scheduling_status(entry, invalid_entries, unmet)

    ordered = topological_queue(entries, by_key)
    for position, entry in enumerate(ordered, start=1):
        entry.scheduling["queue_position"] = position

    runnable = [entry for entry in ordered if entry.scheduling["status"] in {"in_progress", "runnable"}]
    return {
        "next_goal": runnable[0].goal_key if runnable else None,
        "next_planned_goal": ordered[0].goal_key if ordered else None,
        "open_count": len(ordered),
        "runnable_count": len(runnable),
        "invalid_count": sum(entry.scheduling["status"] == "invalid" for entry in entries),
    }


def scheduling_status(entry: SchedulableEntry, invalid_entries: set[str], unmet: list[str]) -> str:
    if entry.goal_key in invalid_entries or entry.status in INVALID_STATUSES:
        return "invalid"
    if entry.status in DONE_STATUSES:
        return "done"
    if unmet:
        return "dependency_blocked"
    if "review_pending" in entry.issues:
        return "not_ready"
    if entry.status == "in_progress":
        return "in_progress"
    if entry.status == "ready":
        return "runnable"
    if entry.status == "blocked":
        return "blocked"
    return "not_ready"


def topological_queue(
    entries: Sequence[SchedulableEntry],
    by_key: dict[str, SchedulableEntry],
) -> list[SchedulableEntry]:
    queueable = {
        entry.goal_key: entry
        for entry in entries
        if entry.status not in DONE_STATUSES | INVALID_STATUSES and entry.scheduling["status"] != "invalid"
    }
    indegree = {goal_key: 0 for goal_key in queueable}
    dependents: dict[str, list[str]] = {goal_key: [] for goal_key in queueable}

    for entry in queueable.values():
        for dependency in entry.scheduling["depends_on"]:
            dependency_entry = by_key.get(dependency)
            if dependency_entry is None or dependency_entry.status in DONE_STATUSES or dependency not in queueable:
                continue
            indegree[entry.goal_key] += 1
            dependents[dependency].append(entry.goal_key)

    heap: list[tuple[tuple[int, int, str], str]] = []
    for goal_key, degree in indegree.items():
        if degree == 0:
            heapq.heappush(heap, (queue_sort_key(queueable[goal_key]), goal_key))

    ordered: list[SchedulableEntry] = []
    seen: set[str] = set()
    while heap:
        _, goal_key = heapq.heappop(heap)
        if goal_key in seen:
            continue
        seen.add(goal_key)
        ordered.append(queueable[goal_key])
        for dependent in dependents[goal_key]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(heap, (queue_sort_key(queueable[dependent]), dependent))

    for entry in sorted(
        (entry for goal_key, entry in queueable.items() if goal_key not in seen),
        key=queue_sort_key,
    ):
        ordered.append(entry)
    return ordered


def queue_sort_key(entry: SchedulableEntry) -> tuple[int, int, str]:
    status_rank = {
        "in_progress": 0,
        "ready": 1,
        "draft": 2,
        "review_pending": 3,
        "blocked": 4,
    }.get(entry.status, 5)
    return (status_rank, -int(entry.scheduling["priority"]), entry.goal_key)


def find_cycle_entries(
    entries: Iterable[SchedulableEntry],
    by_key: dict[str, SchedulableEntry],
) -> set[str]:
    colors: dict[str, int] = {}
    stack: list[str] = []
    stack_positions: dict[str, int] = {}
    cycle_entries: set[str] = set()

    def visit(goal_key: str) -> None:
        colors[goal_key] = 1
        stack_positions[goal_key] = len(stack)
        stack.append(goal_key)
        for dependency in by_key[goal_key].scheduling["depends_on"]:
            if dependency not in by_key:
                continue
            color = colors.get(dependency, 0)
            if color == 0:
                visit(dependency)
            elif color == 1:
                cycle_entries.update(stack[stack_positions[dependency] :])
        stack.pop()
        stack_positions.pop(goal_key, None)
        colors[goal_key] = 2

    for entry in entries:
        if colors.get(entry.goal_key, 0) == 0:
            visit(entry.goal_key)
    return cycle_entries


def append_issue(entry: SchedulableEntry, issue: str) -> None:
    if issue not in entry.issues:
        entry.issues.append(issue)
