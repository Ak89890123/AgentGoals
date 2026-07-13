from __future__ import annotations

import json
from pathlib import Path

import agentgoals.run as run_module
from agentgoals.run import run_pipeline
from tests.test_aggregate import global_root, write_global_registry
from tests.test_reconcile import make_workspace, write_goal, write_registry


def stage_statuses(summary) -> list[str]:
    return [stage.status for stage in summary.stages]


def test_run_pipeline_completes_clean_local_sequence_without_source_mutation() -> None:
    workspace = make_workspace("run-clean-local")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    goal_dir = workspace / "goals" / "active" / "ready-goal"
    source_before = {
        path.name: path.read_text(encoding="utf-8")
        for path in (goal_dir / "CONTRACT.md", goal_dir / "PLAN.md", goal_dir / "EVIDENCE.md")
    }

    summary = run_pipeline(registry, workspace / "outputs")

    assert summary.status == "passed"
    assert summary.exit_code == 0
    assert stage_statuses(summary) == ["passed", "passed", "skipped", "skipped"]
    assert summary.stages[0].entry_count == 1
    assert summary.stages[0].issue_count == 0
    assert {
        path.name: path.read_text(encoding="utf-8")
        for path in (goal_dir / "CONTRACT.md", goal_dir / "PLAN.md", goal_dir / "EVIDENCE.md")
    } == source_before


def test_run_pipeline_returns_two_when_lifecycle_issues_exist() -> None:
    workspace = make_workspace("run-issues")
    write_goal(workspace, "active", "needs-review", "review_pending")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    summary = run_pipeline(registry, workspace / "outputs")

    assert summary.status == "issues"
    assert summary.exit_code == 2
    assert stage_statuses(summary) == ["issues", "passed", "skipped", "skipped"]
    assert summary.stages[0].issue_count == 2
    assert summary.stages[1].issue_count == 2


def test_run_pipeline_skips_dependent_stages_after_local_failure() -> None:
    workspace = make_workspace("run-local-failure")

    summary = run_pipeline(workspace / "missing-registry.json", workspace / "outputs")

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["failed", "skipped", "skipped", "skipped"]
    assert "FileNotFoundError" in str(summary.stages[0].message)
    assert summary.stages[1].message == "reconcile failed"


def test_run_pipeline_completes_optional_global_sequence() -> None:
    workspace = make_workspace("run-global")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    registry_before = global_registry.read_text(encoding="utf-8")

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=workspace / "global-out",
    )

    assert summary.status == "passed"
    assert summary.exit_code == 0
    assert stage_statuses(summary) == ["passed", "passed", "passed", "passed"]
    assert summary.stages[2].entry_count == 1
    assert Path(str(summary.stages[3].output_path)).exists()
    assert global_registry.read_text(encoding="utf-8") == registry_before


def test_run_pipeline_requires_global_registry_for_explicit_global_refresh() -> None:
    workspace = make_workspace("run-require-global")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    out_dir = workspace / "outputs"

    summary = run_pipeline(
        registry,
        out_dir,
        operation_id="operation-required",
        require_global=True,
    )

    assert summary.operation_id == "operation-required"
    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["skipped", "skipped", "failed", "skipped"]
    assert "Global registry is required" in str(summary.stages[2].message)
    assert not (out_dir / "STATE.json").exists()


def test_run_pipeline_propagates_operation_id_and_verifies_global_visibility() -> None:
    workspace = make_workspace("run-operation-id")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    operation_id = "operation-shared"

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=workspace / "global-out",
        operation_id=operation_id,
        require_global=True,
    )

    assert summary.status == "passed"
    assert summary.operation_id == operation_id
    local_payload = json.loads((workspace / "outputs" / "STATE.json").read_text(encoding="utf-8"))
    global_payload = json.loads((workspace / "global-out" / "STATE.json").read_text(encoding="utf-8"))
    assert local_payload["operation_id"] == operation_id
    assert global_payload["operation_id"] == operation_id
    assert global_payload["generated_at"] >= local_payload["generated_at"]
    assert {f"repo-one/{item['id']}" for item in local_payload["entries"]} <= {
        item["goal_key"] for item in global_payload["entries"]
    }


def test_run_pipeline_rejects_global_operation_id_mismatch(monkeypatch) -> None:
    workspace = make_workspace("run-operation-id-mismatch")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    global_out = workspace / "global-out"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    real_aggregate = run_module.aggregate

    def aggregate_with_mismatched_operation(registry_path, out_dir, operation_id=None):
        entries = real_aggregate(registry_path, out_dir, operation_id=operation_id)
        path = out_dir / "STATE.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["operation_id"] = "different-operation"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return entries

    monkeypatch.setattr(run_module, "aggregate", aggregate_with_mismatched_operation)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=global_out,
        operation_id="expected-operation",
        require_global=True,
    )

    assert summary.status == "failed"
    assert summary.stages[3].status == "failed"
    assert "Global STATE operation_id" in str(summary.stages[3].message)


def test_run_pipeline_rejects_global_state_generated_before_local(monkeypatch) -> None:
    workspace = make_workspace("run-global-before-local")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    global_out = workspace / "global-out"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    real_aggregate = run_module.aggregate

    def aggregate_with_stale_timestamp(registry_path, out_dir, operation_id=None):
        entries = real_aggregate(registry_path, out_dir, operation_id=operation_id)
        path = out_dir / "STATE.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["generated_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return entries

    monkeypatch.setattr(run_module, "aggregate", aggregate_with_stale_timestamp)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=global_out,
        operation_id="timestamp-operation",
        require_global=True,
    )

    assert summary.status == "failed"
    assert summary.stages[3].status == "failed"
    assert "generated before local" in str(summary.stages[3].message)


def test_run_pipeline_rejects_global_state_missing_local_goal_key(monkeypatch) -> None:
    workspace = make_workspace("run-global-key-mismatch")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    global_out = workspace / "global-out"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    real_aggregate = run_module.aggregate

    def aggregate_without_local_goal(registry_path, out_dir, operation_id=None):
        entries = real_aggregate(registry_path, out_dir, operation_id=operation_id)
        path = out_dir / "STATE.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["entries"] = []
        path.write_text(json.dumps(payload), encoding="utf-8")
        return entries

    monkeypatch.setattr(run_module, "aggregate", aggregate_without_local_goal)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=global_out,
        operation_id="operation-key-check",
        require_global=True,
    )

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert summary.stages[3].status == "failed"
    assert "canonical Goal keys" in str(summary.stages[3].message)


def test_run_pipeline_returns_two_when_global_state_contains_issues() -> None:
    workspace = make_workspace("run-global-issues")
    write_goal(workspace, "active", "needs-review", "review_pending")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=workspace / "global-out",
    )

    assert summary.status == "issues"
    assert summary.exit_code == 2
    assert stage_statuses(summary) == ["issues", "passed", "issues", "passed"]
    assert summary.stages[2].issue_count == 2


def test_run_pipeline_skips_global_validation_after_aggregate_failure() -> None:
    workspace = make_workspace("run-global-failure")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    global_registry.parent.mkdir(parents=True)
    global_registry.write_text('{"version": 1, "roots": [{}]}', encoding="utf-8")

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=workspace / "global-out",
    )

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["passed", "passed", "failed", "skipped"]
    assert summary.stages[3].message == "aggregate failed"


def test_run_pipeline_returns_one_when_global_validation_fails(monkeypatch) -> None:
    workspace = make_workspace("run-global-validation-failure")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    global_registry = workspace / "global" / "REGISTRY.json"
    global_out = workspace / "global-out"
    global_state = global_out / "STATE.json"
    write_global_registry(
        global_registry,
        [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")],
    )
    validate_state = run_module.validate_state

    def fail_global_validation(path: Path) -> None:
        if path == global_state:
            raise ValueError("invalid global state")
        validate_state(path)

    monkeypatch.setattr(run_module, "validate_state", fail_global_validation)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=global_registry,
        global_out_dir=global_out,
    )

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["passed", "passed", "passed", "failed"]
    assert summary.stages[3].message == "ValueError: invalid global state"


def test_run_pipeline_skips_global_stages_after_local_validation_failure(monkeypatch) -> None:
    workspace = make_workspace("run-local-validation-failure")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    aggregate_called = False

    def fail_validation(path: Path) -> None:
        raise ValueError(f"invalid registry: {path}")

    def record_aggregate(*args, **kwargs):
        nonlocal aggregate_called
        aggregate_called = True
        return []

    monkeypatch.setattr(run_module, "validate_registry", fail_validation)
    monkeypatch.setattr(run_module, "aggregate", record_aggregate)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=workspace / "global" / "REGISTRY.json",
        global_out_dir=workspace / "global-out",
    )

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["passed", "failed", "skipped", "skipped"]
    assert aggregate_called is False


def test_run_pipeline_calls_apis_in_deterministic_order(monkeypatch) -> None:
    workspace = make_workspace("run-order")
    calls: list[str] = []
    local_out = workspace / "outputs"
    global_out = workspace / "global-out"

    monkeypatch.setattr(
        run_module,
        "reconcile",
        lambda registry, out, **kwargs: calls.append("reconcile") or [],
    )
    monkeypatch.setattr(
        run_module,
        "validate_registry",
        lambda registry: calls.append("validate_registry"),
    )

    def record_validate(path: Path) -> None:
        calls.append("validate_local" if path == local_out / "STATE.json" else "validate_global")

    monkeypatch.setattr(run_module, "validate_state", record_validate)
    monkeypatch.setattr(run_module, "verify_global_refresh", lambda *args, **kwargs: calls.append("verify_global"))
    monkeypatch.setattr(
        run_module,
        "aggregate",
        lambda registry, out, **kwargs: calls.append("aggregate") or [],
    )

    summary = run_pipeline(
        workspace / "registry.json",
        local_out,
        global_registry_path=workspace / "global-registry.json",
        global_out_dir=global_out,
    )

    assert summary.exit_code == 0
    assert calls == ["reconcile", "validate_registry", "validate_local", "aggregate", "validate_global", "verify_global"]
