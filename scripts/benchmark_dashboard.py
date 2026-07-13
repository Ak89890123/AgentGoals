from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from agentgoals.dashboard import DashboardFilters, build_dashboard, filter_dashboard_entries


def make_entry(index: int) -> dict[str, object]:
    root_id = f"repo-{index % 6}"
    goal_id = f"goal-{index:04d}"
    return {
        "id": goal_id,
        "title": f"Synthetic Goal {index:04d}",
        "status": "draft",
        "project": f"Project {index % 12}",
        "root_id": root_id,
        "goal_key": f"{root_id}/{goal_id}",
        "goal_root": f"C:/synthetic/{root_id}/goals",
        "contract_path": f"C:/synthetic/{root_id}/goals/{goal_id}/CONTRACT.md",
        "plan_path": f"C:/synthetic/{root_id}/goals/{goal_id}/PLAN.md",
        "evidence_path": f"C:/synthetic/{root_id}/goals/{goal_id}/EVIDENCE.md",
        "owner": f"owner-{index % 8}",
        "updated": "2026-07-11",
        "completed": None,
        "review": {"required": False, "verdict": "pending"},
        "evidence": {"status": "pending"},
        "health": {
            "policy_version": 1,
            "status": "healthy",
            "evaluated_on": "2026-07-11",
            "last_activity": "2026-07-11",
            "findings": [],
        },
        "scheduling": {
            "priority": 50,
            "depends_on": [],
            "status": "not_ready",
            "queue_position": index + 1,
            "unmet_dependencies": [],
        },
        "next_action": None,
        "blocked_reason": None,
        "source_hash": "synthetic",
        "last_seen": "2026-07-11T00:00:00+00:00",
        "issues": [],
    }


def benchmark(entry_count: int, iterations: int, budget_ms: float) -> dict[str, object]:
    payload = {
        "version": 2,
        "generated_at": "2026-07-11T00:00:00+00:00",
        "queue": {
            "next_goal": None,
            "next_planned_goal": "repo-0/goal-0000" if entry_count else None,
            "open_count": entry_count,
            "runnable_count": 0,
            "invalid_count": 0,
        },
        "entries": [make_entry(index) for index in range(entry_count)],
    }
    samples = []
    result_count = 0
    for _ in range(iterations):
        started = time.perf_counter()
        model = build_dashboard(payload)
        result_count = len(
            filter_dashboard_entries(
                model.entries,
                DashboardFilters(query="goal-09", project="Project 9"),
            )
        )
        samples.append((time.perf_counter() - started) * 1000)
    ordered = sorted(samples)
    p95 = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
    return {
        "entries": entry_count,
        "filtered_entries": result_count,
        "iterations": iterations,
        "min_ms": round(min(samples), 3),
        "mean_ms": round(sum(samples) / len(samples), 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(max(samples), 3),
        "budget_ms": budget_ms,
        "passed": max(samples) <= budget_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Goal Dashboard view-model build and filtering.")
    parser.add_argument("--entries", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--budget-ms", type=float, default=500)
    args = parser.parse_args()
    result = benchmark(args.entries, args.iterations, args.budget_ms)
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
