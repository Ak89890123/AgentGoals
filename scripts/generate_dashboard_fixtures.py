from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "fixtures" / "dashboard"


def entry(
    goal_id: str,
    *,
    status: str,
    scheduling_status: str,
    queue_position: int | None,
    issues: list[str] | None = None,
    blocked_reason: str | None = None,
    health_status: str = "healthy",
) -> dict[str, object]:
    health_findings: list[dict[str, object]] = []
    if health_status == "issues":
        health_findings.append(
            {
                "code": "health_stale",
                "rule": "active_goal_stale",
                "severity": "warning",
                "field": "updated",
                "date": "2026-05-01",
                "age_days": 71,
                "threshold_days": 30,
            }
        )
    goal_root = f"C:/dashboard-fixtures/goals/{goal_id}"
    return {
        "id": goal_id,
        "title": goal_id.replace("-", " ").title(),
        "status": status,
        "project": "Dashboard Fixtures",
        "root_id": "fixture-repo",
        "goal_key": f"fixture-repo/{goal_id}",
        "goal_root": goal_root,
        "contract_path": f"{goal_root}/CONTRACT.md",
        "plan_path": f"{goal_root}/PLAN.md",
        "evidence_path": f"{goal_root}/EVIDENCE.md",
        "owner": "qa",
        "updated": "2026-07-11",
        "completed": "2026-07-11" if status == "completed" else None,
        "review": {"required": status == "review_pending", "verdict": "PASS" if status == "completed" else "pending"},
        "evidence": {"status": "complete" if status == "completed" else "pending"},
        "health": {
            "policy_version": 1,
            "status": health_status,
            "evaluated_on": "2026-07-11",
            "last_activity": "2026-05-01" if health_status == "issues" else "2026-07-11",
            "findings": health_findings,
        },
        "scheduling": {
            "priority": 50,
            "depends_on": [],
            "status": scheduling_status,
            "queue_position": queue_position,
            "unmet_dependencies": [],
        },
        "next_action": None,
        "blocked_reason": blocked_reason,
        "source_hash": "fixture",
        "last_seen": "2026-07-11T00:00:00+00:00",
        "issues": issues or [],
    }


def state(name: str, entries: list[dict[str, object]], next_goal: str | None, next_planned: str | None) -> None:
    open_count = sum(item["status"] not in {"completed", "cancelled"} for item in entries)
    runnable_count = sum(item["scheduling"]["status"] in {"runnable", "in_progress"} for item in entries)  # type: ignore[index]
    payload = {
        "version": 2,
        "generated_at": "2026-07-11T00:00:00+00:00",
        "queue": {
            "next_goal": next_goal,
            "next_planned_goal": next_planned,
            "open_count": open_count,
            "runnable_count": runnable_count,
            "invalid_count": 0,
        },
        "entries": entries,
    }
    (OUT_DIR / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean = [
        entry("ready-goal", status="ready", scheduling_status="runnable", queue_position=1),
        entry("completed-goal", status="completed", scheduling_status="done", queue_position=None),
    ]
    blocked = [
        entry(
            "blocked-goal",
            status="blocked",
            scheduling_status="blocked",
            queue_position=1,
            blocked_reason="Waiting for explicit approval",
        )
    ]
    stale = [
        entry(
            "stale-goal",
            status="in_progress",
            scheduling_status="in_progress",
            queue_position=1,
            issues=["health_stale"],
            health_status="issues",
        )
    ]
    state("clean-state.json", clean, "fixture-repo/ready-goal", "fixture-repo/ready-goal")
    state("blocked-state.json", blocked, None, "fixture-repo/blocked-goal")
    state("stale-state.json", stale, "fixture-repo/stale-goal", "fixture-repo/stale-goal")
    state("empty-state.json", [], None, None)


if __name__ == "__main__":
    main()
