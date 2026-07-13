from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentgoals.onboard import onboard_repository
from agentgoals.session_handoff import (
    assess_session_handoff,
    gate_for_status,
    main,
    select_session_handoff,
)
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
    report_path = repo / "outputs" / "ONBOARDING.json"
    global_state = repo / "outputs" / "global" / "STATE.json"
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
        "contract_path": str((report.parents[1] / "goals" / "active" / "focus-goal" / "CONTRACT.md").resolve()),
        "plan_path": str((report.parents[1] / "goals" / "active" / "focus-goal" / "PLAN.md").resolve()),
        "evidence_path": str((report.parents[1] / "goals" / "active" / "focus-goal" / "EVIDENCE.md").resolve()),
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
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["resume"]["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=25)
    ).isoformat()
    report.write_text(json.dumps(payload), encoding="utf-8")
    stale = assess_session_handoff(report, state, max_age=timedelta(hours=24))
    assert stale["fallback_reason"] == CASES["fallback_cases"]["stale"]

    repo = make_repo("handoff-unregistered")
    result = onboard_repository(repo, apply=True)
    unregistered_report = repo / "outputs" / "ONBOARDING.json"
    assert result.registered is False
    unregistered = assess_session_handoff(
        unregistered_report,
        repo / "outputs" / "goal-lifecycle" / "STATE.json",
    )
    assert unregistered["fallback_reason"] == CASES["fallback_cases"]["unregistered"]


def test_freshness_uses_report_metadata_and_state_fingerprint_not_mtime() -> None:
    # Given: a current report whose filesystem timestamp is old.
    report, state = registered_report("handoff-content-freshness")
    old = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    os.utime(report, (old, old))

    # When: the report is assessed against its matching State.
    current = assess_session_handoff(report, state)
    state.write_text(state.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    mismatched = assess_session_handoff(report, state)

    # Then: metadata remains current while changed State content is rejected.
    assert current["mode"] == "fast_path"
    assert mismatched["fallback_reason"] == "state_fingerprint_mismatch"


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
    focus["contract_path"] = str((report.parents[1].parent / "other-repo" / "CONTRACT.md").resolve())
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
        repo / "outputs" / "ONBOARDING.json",
        repo / "outputs" / "global" / "STATE.json",
    )

    assert result["mode"] == "fast_path"
    assert result["focus"] is None
    assert result["resume"]["open_count"] == 0


def test_cli_returns_zero_for_fast_path_and_two_for_fallback(capsys) -> None:
    report, state = registered_report("handoff-cli")
    repo = report.parents[1]

    assert main(["--repo", str(repo), "--report", str(report), "--state", str(state)]) == 0
    fast = json.loads(capsys.readouterr().out)
    assert fast["mode"] == "fast_path"

    missing = repo / "missing.json"
    assert main(["--repo", str(repo), "--report", str(missing), "--state", str(state)]) == 0
    fallback_payload = json.loads(capsys.readouterr().out)
    assert fallback_payload["mode"] == "fast_path"
    assert fallback_payload["attempts"][0]["fallback_reason"] == "report_missing"


def test_cli_selects_repo_local_canonical_pair_without_explicit_paths(capsys) -> None:
    # Given: a repository with one valid allowlisted canonical pair.
    report, _ = registered_report("handoff-cli-canonical")
    repo = report.parents[1]

    # When: the CLI receives only the repository boundary.
    exit_code = main(["--repo", str(repo)])
    payload = json.loads(capsys.readouterr().out)

    # Then: selection succeeds without report guessing or path prompting.
    assert exit_code == 0
    assert payload["selected_report"] == str(report.resolve())


def test_selector_uses_compatible_canonical_pair_after_explicit_legacy_report() -> None:
    # Given: a valid canonical pair and an explicitly supplied legacy report.
    report, state = registered_report("handoff-candidate-selection")
    repo = report.parents[1]
    compatibility_report = repo / "outputs" / "goal-lifecycle" / "ONBOARDING.json"
    compatibility_state = repo / "outputs" / "goal-lifecycle" / "global" / "STATE.json"
    compatibility_report.parent.mkdir(parents=True, exist_ok=True)
    compatibility_state.parent.mkdir(parents=True, exist_ok=True)
    compatibility_report.write_bytes(report.read_bytes())
    compatibility_state.write_bytes(state.read_bytes())
    legacy = repo / "outputs" / "ONBOARDING.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"resume": {"version": 0}}), encoding="utf-8")

    # When: deterministic selection assesses the explicit candidate first.
    result = select_session_handoff(repo, report_path=legacy, state_path=state)

    # Then: the supported allowlisted canonical pair is selected.
    assert result["mode"] == "fast_path"
    assert result["selected_report"] == str(compatibility_report.resolve())
    assert result["attempts"][0]["fallback_reason"] == "resume_unsupported"


def test_selector_returns_one_truthful_reason_when_no_candidate_is_valid() -> None:
    # Given: a repository with no onboarding report or aggregate State.
    repo = make_repo("handoff-no-valid-candidate")

    # When: deterministic selection checks only allowlisted paths.
    result = select_session_handoff(repo)

    # Then: one stable fallback reason summarizes the failed selection.
    assert result["mode"] == "fallback"
    assert result["fallback_reason"] == "no_valid_candidate"
    assert len(result["attempts"]) == 2


def test_selector_rejects_explicit_candidate_from_another_repository() -> None:
    # Given: an explicit valid pair owned by a different repository.
    foreign_report, foreign_state = registered_report("handoff-foreign")
    repo = make_repo("handoff-expected-repo")

    # When: selection is bounded to the expected repository.
    result = select_session_handoff(
        repo,
        report_path=foreign_report,
        state_path=foreign_state,
    )

    # Then: the foreign pair is rejected before it can become the fast path.
    assert result["mode"] == "fallback"
    assert result["attempts"][0]["fallback_reason"] == "identity_mismatch"


def test_selector_chooses_newest_compatible_allowlisted_pair() -> None:
    # Given: both allowlisted pairs are valid with different generation metadata.
    canonical_report, canonical_state = registered_report("handoff-newest")
    repo = canonical_report.parents[1]
    compatibility_report = repo / "outputs" / "goal-lifecycle" / "ONBOARDING.json"
    compatibility_state = repo / "outputs" / "goal-lifecycle" / "global" / "STATE.json"
    compatibility_report.parent.mkdir(parents=True, exist_ok=True)
    compatibility_state.parent.mkdir(parents=True, exist_ok=True)
    compatibility_report.write_bytes(canonical_report.read_bytes())
    compatibility_state.write_bytes(canonical_state.read_bytes())
    payload = json.loads(canonical_report.read_text(encoding="utf-8"))
    payload["resume"]["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    canonical_report.write_text(json.dumps(payload), encoding="utf-8")

    # When: repository-local candidates are selected without explicit paths.
    result = select_session_handoff(repo)

    # Then: validated generation metadata selects the newer compatibility pair.
    assert result["mode"] == "fast_path"
    assert result["selected_report"] == str(compatibility_report.resolve())


def test_future_generated_report_is_rejected() -> None:
    # Given: a report claiming a generation time in the future.
    report, state = registered_report("handoff-future")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["resume"]["generated_at"] = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    report.write_text(json.dumps(payload), encoding="utf-8")

    # When: the candidate is assessed.
    result = assess_session_handoff(report, state)

    # Then: it cannot extend its own freshness window.
    assert result["fallback_reason"] == "report_from_future"


def test_canonical_symlink_escape_is_rejected_before_external_report_read() -> None:
    # Given: an allowlisted canonical filename that resolves to malformed data outside the repo.
    repo = make_repo("handoff-symlink-escape")
    external = repo.parent / f"{repo.name}-external.json"
    external.write_text("not json", encoding="utf-8")
    report = repo / "outputs" / "ONBOARDING.json"
    report.parent.mkdir(parents=True)
    try:
        report.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")

    # When: repository-bounded selection resolves the allowlisted candidate.
    result = select_session_handoff(repo)

    # Then: containment wins before malformed external bytes are parsed.
    assert result["attempts"][0]["fallback_reason"] == "identity_mismatch"


def test_external_malformed_explicit_report_is_rejected_before_parsing() -> None:
    # Given: malformed report bytes outside the requested repository.
    repo = make_repo("handoff-external-malformed")
    external = repo.parent / f"{repo.name}-malformed.json"
    external.write_text("not json", encoding="utf-8")
    state = repo / "outputs" / "global" / "STATE.json"

    # When: the external path is supplied explicitly.
    result = select_session_handoff(repo, report_path=external, state_path=state)

    # Then: repository containment rejects it before JSON parsing.
    assert result["attempts"][0]["fallback_reason"] == "identity_mismatch"
