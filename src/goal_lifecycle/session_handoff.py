from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from goal_lifecycle.validate import SCHEMA_DIR, load_json, validate_json_file, validate_state


ONBOARDING_SCHEMA = SCHEMA_DIR / "onboarding-result.schema.json"
QUEUE_FIELDS = (
    "next_goal",
    "next_planned_goal",
    "open_count",
    "runnable_count",
    "invalid_count",
)


def gate_for_status(status: str, review_required: bool, review_verdict: str | None) -> str:
    if status == "draft":
        return "accept_contract"
    if status == "review_pending":
        return "obtain_review"
    if status == "ready":
        return "start_execution"
    if status == "in_progress":
        if review_required and review_verdict != "PASS":
            return "continue_before_review_gate"
        return "continue_execution"
    if status == "blocked":
        return "resolve_blocker"
    return "inspect_lifecycle_state"


def assess_session_handoff(
    report_path: Path,
    state_path: Path,
    *,
    max_age: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> dict[str, Any]:
    if not report_path.exists():
        return fallback("report_missing")

    try:
        report = load_json(report_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback("report_malformed")

    raw_resume = report.get("resume")
    if isinstance(raw_resume, dict) and raw_resume and raw_resume.get("version") != 1:
        return fallback("resume_unsupported", raw_resume)
    if (report.get("visibility_verified") is True or report.get("outcome") in {"visibility_verified", "global_issues"}) and (
        report.get("registered") is not True
        or report.get("outcome") not in {"visibility_verified", "global_issues"}
        or not isinstance(raw_resume, dict)
        or raw_resume.get("visibility_verified") is not True
        or raw_resume.get("source") != "global"
    ):
        return fallback("report_contradiction", raw_resume if isinstance(raw_resume, dict) else None)
    try:
        validate_json_file(report_path, ONBOARDING_SCHEMA)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback("report_malformed", raw_resume if isinstance(raw_resume, dict) else None)

    current_time = now or datetime.now(timezone.utc)
    modified = datetime.fromtimestamp(report_path.stat().st_mtime, timezone.utc)
    if current_time - modified > max_age:
        return fallback("report_stale", report.get("resume"))
    if not report.get("registered"):
        return fallback("repository_unregistered", report.get("resume"))
    if not report.get("visibility_verified"):
        return fallback("visibility_unverified", report.get("resume"))

    resume = report.get("resume", {})
    if resume.get("version") != 1 or resume.get("source") != "global":
        return fallback("resume_unsupported", resume)
    if resume.get("invalid_count", 0) > 0:
        return fallback("invalid_queue", resume)
    if not state_path.exists():
        return fallback("state_missing", resume)

    target_repo = Path(str(report.get("target_repo", ""))).resolve()
    if not target_repo.is_dir() or not is_within(state_path.resolve(), target_repo):
        return fallback("identity_mismatch", resume)

    try:
        validate_state(state_path)
        state = load_json(state_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback("state_malformed", resume)

    queue = state.get("queue", {})
    if any(resume.get(field) != queue.get(field) for field in QUEUE_FIELDS):
        return fallback("state_contradiction", resume)

    focus_key = resume.get("next_goal") or resume.get("next_planned_goal")
    focus = None
    if focus_key is not None:
        entry = next((item for item in state.get("entries", []) if item.get("goal_key") == focus_key), None)
        if entry is None:
            return fallback("state_contradiction", resume)
        goal_root = Path(str(entry.get("goal_root", "")))
        source_paths = [entry.get("contract_path"), entry.get("plan_path"), entry.get("evidence_path")]
        if (
            entry.get("root_id") != resume.get("focus_root_id")
            or not str(entry.get("goal_key", "")).startswith(f"{resume.get('focus_root_id')}/")
            or not goal_root.is_absolute()
            or not is_within(goal_root.resolve(), target_repo)
            or any(
                not Path(str(source_path)).is_absolute()
                or not is_within(Path(str(source_path)).resolve(), goal_root.resolve())
                for source_path in source_paths
                if source_path is not None
            )
        ):
            return fallback("identity_mismatch", resume)
        review = entry.get("review", {})
        evidence = entry.get("evidence", {})
        health = entry.get("health", {})
        focus = {
            "goal_key": entry["goal_key"],
            "status": entry["status"],
            "gate": gate_for_status(
                entry["status"],
                bool(review.get("required")),
                review.get("verdict"),
            ),
            "contract_path": entry.get("contract_path"),
            "plan_path": entry.get("plan_path"),
            "evidence_path": entry.get("evidence_path"),
            "evidence_status": evidence.get("status"),
            "review_required": bool(review.get("required")),
            "review_verdict": review.get("verdict"),
            "health_status": health.get("status"),
            "issues": entry.get("issues", []),
        }

    return {
        "version": 1,
        "mode": "fast_path",
        "fallback_reason": None,
        "resume": resume,
        "focus": focus,
    }


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def fallback(reason: str, resume: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "version": 1,
        "mode": "fallback",
        "fallback_reason": reason,
        "resume": resume or {},
        "focus": None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate compact Goal Lifecycle session handoff context without modifying source files."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--max-age-hours", type=float, default=24.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = assess_session_handoff(
        args.report,
        args.state,
        max_age=timedelta(hours=args.max_age_hours),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["mode"] == "fast_path" else 2


if __name__ == "__main__":
    raise SystemExit(main())
