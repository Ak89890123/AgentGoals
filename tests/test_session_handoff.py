from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from goal_lifecycle.onboard import onboard_repository
from goal_lifecycle.session_handoff import assess_session_handoff, gate_for_status, main
from tests.test_aggregate import global_root, write_global_registry
from tests.test_onboard import make_repo
from tests.test_reconcile import write_goal


CASES = json.loads(Path("fixtures/session_handoff/cases.json").read_text(encoding="utf-8"))


def registered_report(name: str, status: str = "draft") -> tuple[Path, Path]:
    repo = make_repo(name)
    write_goal(
        repo,
        "active",
        "focus-goal",
        status,
        evidence_status="partial" if status == "in_progress" else "pending",
        review_verdict="pending",
    )
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)
    assert result.registered is True
    report_path = repo / "outputs" / "goal-lifecycle" / "ONBOARDING.json"
    global_state = repo / "outputs" / "goal-lifecycle" / "global" / "STATE.json"
    return report_path, global_state


def test_fast_path_returns_authoritative_focus_and_gate() -> None:
    report, state = registered_report("handoff-fast-path", "in_progress")

    result = assess_session_handoff(report, state)

    assert result["mode"] == "fast_path"
    assert result["fallback_reason"] is None
    assert result["focus"] == {
        "goal_key": "registered-repo/focus-goal",
        "status": "in_progress",
        "gate": "continue_before_review_gate",
        "contract_path": str((report.parents[2] / "goals" / "active" / "focus-goal" / "CONTRACT.md").resolve()),
        "plan_path": str((report.parents[2] / "goals" / "active" / "focus-goal" / "PLAN.md").resolve()),
        "evidence_path": str((report.parents[2] / "goals" / "active" / "focus-goal" / "EVIDENCE.md").resolve()),
        "evidence_status": "partial",
        "review_required": True,
        "review_verdict": "pending",
        "health_status": "disabled",
        "issues": ["evidence_incomplete", "review_pending"],
    }
    assert result["resume"]["version"] == 1


@pytest.mark.parametrize(
    "case",
    CASES["gate_cases"],
    ids=[case["id"] for case in CASES["gate_cases"]],
)
def test_gate_mapping_is_deterministic(
    case: dict[str, object],
) -> None:
    assert gate_for_status(
        str(case["status"]),
        bool(case["review_required"]),
        str(case["review_verdict"]),
    ) == case["expected_gate"]


def test_missing_malformed_stale_and_unregistered_reports_fall_back() -> None:
    missing = assess_session_handoff(Path("missing-report.json"), Path("missing-state.json"))
    assert missing["fallback_reason"] == CASES["fallback_cases"]["missing"]

    report, state = registered_report("handoff-fallbacks")
    report.write_text("not json", encoding="utf-8")
    malformed = assess_session_handoff(report, state)
    assert malformed["fallback_reason"] == CASES["fallback_cases"]["malformed"]

    report, state = registered_report("handoff-stale")
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
    os.utime(report, (old, old))
    stale = assess_session_handoff(report, state, max_age=timedelta(hours=24))
    assert stale["fallback_reason"] == CASES["fallback_cases"]["stale"]

    repo = make_repo("handoff-unregistered")
    result = onboard_repository(repo, apply=True)
    unregistered_report = repo / "outputs" / "goal-lifecycle" / "ONBOARDING.json"
    assert result.registered is False
    unregistered = assess_session_handoff(
        unregistered_report,
        repo / "outputs" / "goal-lifecycle" / "STATE.json",
    )
    assert unregistered["fallback_reason"] == CASES["fallback_cases"]["unregistered"]


def test_queue_contradiction_and_invalid_queue_fall_back() -> None:
    report, state = registered_report("handoff-contradiction")
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["queue"]["next_planned_goal"] = None
    state.write_text(json.dumps(payload), encoding="utf-8")
    contradictory = assess_session_handoff(report, state)
    assert contradictory["fallback_reason"] == CASES["fallback_cases"]["contradiction"]

    report, state = registered_report("handoff-invalid")
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    report_payload["resume"]["invalid_count"] = 1
    report.write_text(json.dumps(report_payload), encoding="utf-8")
    invalid = assess_session_handoff(report, state)
    assert invalid["fallback_reason"] == CASES["fallback_cases"]["invalid_queue"]


def test_visibility_version_and_state_failures_fall_back() -> None:
    report, state = registered_report("handoff-visibility")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["visibility_verified"] = False
    payload["resume"]["visibility_verified"] = False
    payload["resume"]["source"] = "local"
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["report_contradiction"]

    report, state = registered_report("handoff-version")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["resume"]["version"] = 2
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["unsupported"]

    report, state = registered_report("handoff-state-missing")
    assert assess_session_handoff(report, state.with_name("MISSING.json"))["fallback_reason"] == CASES["fallback_cases"]["state_missing"]

    report, state = registered_report("handoff-state-malformed")
    state.write_text("not json", encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["state_malformed"]


def test_cross_repo_root_and_source_path_mismatches_fall_back() -> None:
    report, state = registered_report("handoff-cross-repo")
    payload = json.loads(state.read_text(encoding="utf-8"))
    focus = next(item for item in payload["entries"] if item["goal_key"] == "registered-repo/focus-goal")
    focus["root_id"] = "other-repo"
    state.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["identity_mismatch"]


def test_visibility_and_outcome_contradictions_fall_back_before_schema_trust() -> None:
    report, state = registered_report("handoff-resume-visibility-contradiction")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["resume"]["visibility_verified"] = False
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["report_contradiction"]

    report, state = registered_report("handoff-outcome-contradiction")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["outcome"] = "global_failed"
    payload["exit_code"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["report_contradiction"]

    report, state = registered_report("handoff-path-escape")
    payload = json.loads(state.read_text(encoding="utf-8"))
    focus = next(item for item in payload["entries"] if item["goal_key"] == "registered-repo/focus-goal")
    focus["contract_path"] = str((report.parents[2].parent / "other-repo" / "CONTRACT.md").resolve())
    state.write_text(json.dumps(payload), encoding="utf-8")
    assert assess_session_handoff(report, state)["fallback_reason"] == CASES["fallback_cases"]["identity_mismatch"]


def test_empty_queue_is_a_valid_fast_path_without_focus() -> None:
    repo = make_repo("handoff-empty")
    write_goal(repo, "completed", "done-goal", "completed", evidence_status="complete", review_verdict="PASS")
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    onboard_repository(repo, apply=True, global_registry_path=global_registry)

    result = assess_session_handoff(
        repo / "outputs" / "goal-lifecycle" / "ONBOARDING.json",
        repo / "outputs" / "goal-lifecycle" / "global" / "STATE.json",
    )

    assert result["mode"] == "fast_path"
    assert result["focus"] is None
    assert result["resume"]["open_count"] == 0


def test_cli_returns_zero_for_fast_path_and_two_for_fallback(capsys) -> None:
    report, state = registered_report("handoff-cli")

    assert main(["--report", str(report), "--state", str(state)]) == 0
    fast = json.loads(capsys.readouterr().out)
    assert fast["mode"] == "fast_path"

    assert main(["--report", "missing.json", "--state", str(state)]) == 2
    fallback_payload = json.loads(capsys.readouterr().out)
    assert fallback_payload["fallback_reason"] == "report_missing"
