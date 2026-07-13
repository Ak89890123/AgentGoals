from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from agentgoals.handoff_gate import gate_for_status
from agentgoals.validate import SCHEMA_DIR, load_json, validate_json_file, validate_state


ONBOARDING_SCHEMA = SCHEMA_DIR / "onboarding-result.schema.json"
QUEUE_FIELDS = (
    "next_goal",
    "next_planned_goal",
    "open_count",
    "runnable_count",
    "invalid_count",
)
CANONICAL_PAIRS = (
    (Path("outputs/ONBOARDING.json"), Path("outputs/global/STATE.json")),
    (
        Path("outputs/goal-lifecycle/ONBOARDING.json"),
        Path("outputs/goal-lifecycle/global/STATE.json"),
    ),
)


def assess_session_handoff(
    report_path: Path,
    state_path: Path,
    *,
    max_age: timedelta = timedelta(hours=24),
    now: datetime | None = None,
    expected_repo: Path | None = None,
) -> dict[str, Any]:
    if expected_repo is not None:
        expected = expected_repo.resolve()
        if not is_within(report_path.resolve(), expected) or not is_within(state_path.resolve(), expected):
            return fallback("identity_mismatch")
    if not report_path.exists():
        return fallback("report_missing")

    try:
        report = load_json(report_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback("report_malformed")

    raw_resume = report.get("resume")
    if isinstance(raw_resume, dict) and raw_resume and (
        raw_resume.get("version") != 1
        or "generated_at" not in raw_resume
        or "state_sha256" not in raw_resume
    ):
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

    if not report.get("registered"):
        return fallback("repository_unregistered", report.get("resume"))
    if not report.get("visibility_verified"):
        return fallback("visibility_unverified", report.get("resume"))

    resume = report.get("resume", {})
    if resume.get("version") != 1 or resume.get("source") != "global":
        return fallback("resume_unsupported", resume)
    current_time = now or datetime.now(timezone.utc)
    try:
        generated_at = datetime.fromisoformat(str(resume["generated_at"]))
    except ValueError:
        return fallback("report_malformed", resume)
    if generated_at.tzinfo is None:
        return fallback("report_malformed", resume)
    if generated_at > current_time:
        return fallback("report_from_future", resume)
    if current_time - generated_at > max_age:
        return fallback("report_stale", resume)
    if resume.get("invalid_count", 0) > 0:
        return fallback("invalid_queue", resume)
    if not state_path.exists():
        return fallback("state_missing", resume)
    target_repo = Path(str(report.get("target_repo", ""))).resolve()
    expected = expected_repo.resolve() if expected_repo is not None else target_repo
    if (
        not target_repo.is_dir()
        or target_repo != expected
        or not is_within(report_path.resolve(), expected)
        or not is_within(state_path.resolve(), expected)
    ):
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

    try:
        state_sha256 = hashlib.sha256(state_path.read_bytes()).hexdigest()
    except OSError:
        return fallback("state_malformed", resume)
    if state_sha256 != resume["state_sha256"]:
        return fallback("state_fingerprint_mismatch", resume)

    return {
        "version": 1,
        "mode": "fast_path",
        "fallback_reason": None,
        "resume": resume,
        "focus": focus,
    }


def select_session_handoff(
    repo_path: Path,
    *,
    report_path: Path | None = None,
    state_path: Path | None = None,
    max_age: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> dict[str, Any]:
    repo = repo_path.resolve()
    candidates: list[tuple[Path, Path]] = []
    if report_path is not None and state_path is not None:
        candidates.append((report_path.resolve(), state_path.resolve()))
    candidates.extend((repo / report, repo / state) for report, state in CANONICAL_PAIRS)

    attempts: list[dict[str, Any]] = []
    seen: set[tuple[Path, Path]] = set()
    valid: list[tuple[datetime, Path, Path, dict[str, Any]]] = []
    for candidate_report, candidate_state in candidates:
        pair = (candidate_report.resolve(), candidate_state.resolve())
        if pair in seen:
            continue
        seen.add(pair)
        result = assess_session_handoff(
            pair[0],
            pair[1],
            max_age=max_age,
            now=now,
            expected_repo=repo,
        )
        attempts.append(
            {
                "report": str(pair[0]),
                "state": str(pair[1]),
                "fallback_reason": result["fallback_reason"],
            }
        )
        if result["mode"] == "fast_path" and report_path is not None and pair == candidates[0]:
            return {
                **result,
                "selected_report": str(pair[0]),
                "selected_state": str(pair[1]),
                "attempts": attempts,
            }
        if result["mode"] == "fast_path":
            generated_at = datetime.fromisoformat(result["resume"]["generated_at"])
            valid.append((generated_at, pair[0], pair[1], result))

    if valid:
        _, selected_report, selected_state, selected = max(valid, key=lambda item: item[0])
        return {
            **selected,
            "selected_report": str(selected_report),
            "selected_state": str(selected_state),
            "attempts": attempts,
        }

    return {
        **fallback("no_valid_candidate"),
        "selected_report": None,
        "selected_state": None,
        "attempts": attempts,
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
        description="Validate compact AgentGoals session handoff context without modifying source files."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--max-age-hours", type=float, default=24.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.report is None) != (args.state is None):
        build_parser().error("--report and --state must be supplied together")
    payload = select_session_handoff(
        args.repo,
        report_path=args.report,
        state_path=args.state,
        max_age=timedelta(hours=args.max_age_hours),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["mode"] == "fast_path" else 2


if __name__ == "__main__":
    raise SystemExit(main())
