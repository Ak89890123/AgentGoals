from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol


class StateLike(Protocol):
    id: str
    title: str
    status: str
    project: str
    goal_key: str
    review: dict
    evidence: dict
    scheduling: dict
    issues: list[str]


def render_state_markdown(entries: Sequence[StateLike]) -> str:
    counts = Counter(entry.status for entry in entries)
    lines = [
        "# Goal State",
        "",
        "STATE is a derived index. Source Goal Contract, PLAN, and EVIDENCE files remain authoritative.",
        "",
        "## Summary",
        "",
    ]
    if counts:
        for status, count in sorted(counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- No goals found.")

    ordered = sorted(
        (entry for entry in entries if entry.scheduling.get("queue_position") is not None),
        key=lambda entry: (entry.scheduling["queue_position"], entry.goal_key),
    )
    if ordered:
        lines.extend(["", "## Queue", ""])
        for entry in ordered:
            scheduling = entry.scheduling
            unmet = ", ".join(f"`{item}`" for item in scheduling["unmet_dependencies"]) or "none"
            lines.append(
                f"{scheduling['queue_position']}. `{entry.goal_key}` - "
                f"`{scheduling['status']}`, priority `{scheduling['priority']}`, unmet: {unmet}"
            )

    append_issue_group(lines, "Waiting Review", entries, "review_pending")
    append_issue_group(lines, "Evidence Incomplete", entries, "evidence_incomplete")
    append_issue_group(lines, "Stale Entries", entries, "stale")
    append_issue_group(lines, "Folder Mismatches", entries, "status_folder_mismatch")
    append_issue_group(lines, "Parse Errors", entries, "parse_error")

    lines.extend(["", "## Entries", ""])
    for entry in entries:
        issues = ", ".join(f"`{issue}`" for issue in entry.issues) if entry.issues else "none"
        review_verdict = entry.review.get("verdict")
        evidence_status = entry.evidence.get("status")
        lines.extend(
            [
                f"### {entry.title}",
                "",
                f"- ID: `{entry.id}`",
                f"- Project: `{entry.project}`",
                f"- Goal key: `{entry.goal_key}`",
                f"- Status: `{entry.status}`",
                f"- Scheduling: `{entry.scheduling['status']}`",
                f"- Priority: `{entry.scheduling['priority']}`",
                f"- Queue position: `{entry.scheduling['queue_position']}`",
                f"- Review: `{review_verdict}`",
                f"- Evidence: `{evidence_status}`",
                f"- Issues: {issues}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def append_issue_group(lines: list[str], title: str, entries: Sequence[StateLike], issue: str) -> None:
    matching = [entry for entry in entries if issue in entry.issues]
    if not matching:
        return
    lines.extend(["", f"## {title}", ""])
    for entry in matching:
        lines.append(f"- `{entry.id}`: {entry.title}")
