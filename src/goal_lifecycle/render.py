from __future__ import annotations

from collections import Counter
from typing import Protocol


class StateLike(Protocol):
    id: str
    title: str
    status: str
    project: str
    review: dict
    evidence: dict
    issues: list[str]


def render_state_markdown(entries: list[StateLike]) -> str:
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
                f"- Status: `{entry.status}`",
                f"- Review: `{review_verdict}`",
                f"- Evidence: `{evidence_status}`",
                f"- Issues: {issues}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
