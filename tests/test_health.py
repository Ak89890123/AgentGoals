from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from goal_lifecycle.aggregate import aggregate
from goal_lifecycle.onboard import onboard_repository
from goal_lifecycle.reconcile import reconcile
from goal_lifecycle.validate import validate_state
from tests.test_aggregate import global_root, write_global_registry
from tests.test_reconcile import make_workspace, write_goal, write_registry


DEFAULT_THRESHOLDS = {
    "draft": 30,
    "review_pending": 7,
    "ready": 14,
    "in_progress": 14,
    "blocked": 7,
}


def enable_health_policy(registry: Path, thresholds: dict[str, int] | None = None) -> None:
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["health_policy"] = {
        "version": 1,
        "enabled": True,
        "thresholds": thresholds or {},
    }
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def replace_metadata(path: Path, old: str, new: str) -> None:
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def goal_file(workspace: Path, folder: str, goal_id: str, filename: str) -> Path:
    return workspace / "goals" / folder / goal_id / filename


def finding(entry, code: str) -> dict:
    return next(item for item in entry.health["findings"] if item["code"] == code)


def test_unconfigured_policy_preserves_legacy_stale_behavior() -> None:
    workspace = make_workspace("health-disabled")
    write_goal(
        workspace,
        "active",
        "legacy",
        "in_progress",
        evidence_status="complete",
        review_verdict="PASS",
        updated=None,
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 8, 1))[0]

    assert entry.issues == ["stale"]
    assert entry.health == {
        "policy_version": None,
        "status": "disabled",
        "evaluated_on": None,
        "last_activity": None,
        "findings": [],
    }


@pytest.mark.parametrize(("status", "threshold"), DEFAULT_THRESHOLDS.items())
def test_active_status_is_fresh_on_threshold_and_stale_after_it(status: str, threshold: int) -> None:
    workspace = make_workspace(f"health-boundary-{status}")
    write_goal(workspace, "active", status, status, evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    before_threshold = reconcile(
        registry,
        workspace / "before-threshold",
        evaluation_date=date(2026, 7, 7) + timedelta(days=threshold - 1),
    )[0]
    on_threshold = reconcile(
        registry,
        workspace / "on-threshold",
        evaluation_date=date(2026, 7, 7) + timedelta(days=threshold),
    )[0]
    after_threshold = reconcile(
        registry,
        workspace / "after-threshold",
        evaluation_date=date(2026, 7, 8) + timedelta(days=threshold),
    )[0]

    assert "health_stale" not in before_threshold.issues
    assert "health_stale" not in on_threshold.issues
    assert on_threshold.health["status"] == "healthy"
    assert "health_stale" in after_threshold.issues
    stale = finding(after_threshold, "health_stale")
    assert stale["rule"] == f"freshness.{status}"
    assert stale["age_days"] == threshold + 1
    assert stale["threshold_days"] == threshold
    assert stale["date"] == "2026-07-07"


def test_latest_document_update_is_used_as_activity_date() -> None:
    workspace = make_workspace("health-latest-activity")
    write_goal(workspace, "active", "work", "in_progress", evidence_status="complete", review_verdict="PASS")
    replace_metadata(goal_file(workspace, "active", "work", "PLAN.md"), "updated: 2026-07-07", "updated: 2026-07-20")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 8, 1))[0]

    assert entry.health["last_activity"] == "2026-07-20"
    assert "health_stale" not in entry.issues


def test_threshold_override_is_applied() -> None:
    workspace = make_workspace("health-override")
    write_goal(workspace, "active", "work", "in_progress", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry, {"in_progress": 3})

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 11))[0]

    assert finding(entry, "health_stale")["threshold_days"] == 3


def test_missing_invalid_future_and_out_of_order_dates_have_distinct_codes() -> None:
    workspace = make_workspace("health-date-errors")
    write_goal(workspace, "active", "dates", "in_progress", evidence_status="complete", review_verdict="PASS")
    contract = goal_file(workspace, "active", "dates", "CONTRACT.md")
    replace_metadata(contract, "created: 2026-07-07", "created: 2026-07-10")
    replace_metadata(contract, "updated: 2026-07-07", "updated: 2026-07-09")
    plan = goal_file(workspace, "active", "dates", "PLAN.md")
    replace_metadata(plan, "updated: 2026-07-07", "updated: [not-a-date]")
    evidence = goal_file(workspace, "active", "dates", "EVIDENCE.md")
    replace_metadata(evidence, "updated: 2026-07-07", "updated: 2026-07-12")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 11))[0]

    assert {
        "health_date_invalid",
        "health_date_future",
        "health_date_order",
    }.issubset(entry.issues)
    assert finding(entry, "health_date_invalid")["rule"] == "dates.plan_updated_valid"
    assert finding(entry, "health_date_future")["rule"] == "dates.evidence_updated_not_future"
    assert finding(entry, "health_date_order")["rule"] == "dates.contract_updated_not_before_created"


def test_missing_required_updated_date_is_not_reported_as_legacy_stale_when_enabled() -> None:
    workspace = make_workspace("health-missing-date")
    write_goal(
        workspace,
        "active",
        "missing-updated",
        "blocked",
        evidence_status="complete",
        review_verdict="PASS",
        updated=None,
    )
    plan = goal_file(workspace, "active", "missing-updated", "PLAN.md")
    evidence = goal_file(workspace, "active", "missing-updated", "EVIDENCE.md")
    replace_metadata(plan, "updated: 2026-07-07\n", "")
    replace_metadata(evidence, "updated: 2026-07-07\n", "")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 20))[0]

    assert "stale" not in entry.issues
    assert "health_date_missing" in entry.issues
    assert "health_stale" not in entry.issues


def test_completed_goal_requires_completion_date_and_complete_evidence() -> None:
    workspace = make_workspace("health-completion")
    write_goal(workspace, "completed", "done", "completed", evidence_status="partial", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 20))[0]

    assert "health_date_missing" in entry.issues
    assert "health_evidence_incomplete" in entry.issues
    assert finding(entry, "health_date_missing")["rule"] == "dates.completed_present"


def test_active_goal_with_completion_date_is_inconsistent() -> None:
    workspace = make_workspace("health-active-completed")
    write_goal(workspace, "active", "active", "ready", evidence_status="complete", review_verdict="PASS")
    contract = goal_file(workspace, "active", "active", "CONTRACT.md")
    replace_metadata(contract, "completed:\n", "completed: 2026-07-08\n")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)

    entry = reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 20))[0]

    assert "health_completion_inconsistent" in entry.issues


def test_health_findings_validate_render_and_survive_global_aggregation() -> None:
    workspace = make_workspace("health-aggregate")
    write_goal(workspace, "active", "old", "blocked", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)
    local_out = workspace / "outputs"

    local_entry = reconcile(registry, local_out, evaluation_date=date(2026, 7, 20))[0]
    validate_state(local_out / "STATE.json")
    rendered = (local_out / "STATE.md").read_text(encoding="utf-8")

    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", local_out / "STATE.json")])
    global_entry = aggregate(global_registry, workspace / "global-out")[0]
    validate_state(workspace / "global-out" / "STATE.json")

    assert "## Health Issues" in rendered
    assert global_entry.health == local_entry.health


def test_registry_schema_rejects_unknown_health_threshold() -> None:
    workspace = make_workspace("health-invalid-config")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry, {"completed": 10})

    with pytest.raises(ValueError, match="completed"):
        reconcile(registry, workspace / "outputs", evaluation_date=date(2026, 7, 20))


def test_health_policy_runs_in_an_onboarded_fixture_repository() -> None:
    repo = make_workspace("health-onboarded")
    (repo / ".git").mkdir()
    onboarding = onboard_repository(repo, apply=True)
    assert onboarding.outcome == "registration_required"

    write_goal(repo, "active", "legacy", "in_progress", evidence_status="complete", review_verdict="PASS")
    registry = repo / "registry" / "REGISTRY.json"
    enable_health_policy(registry, {"in_progress": 3})

    entry = reconcile(registry, repo / "health-output", evaluation_date=date(2026, 7, 11))[0]

    assert "health_stale" in entry.issues
    assert entry.health["policy_version"] == 1
