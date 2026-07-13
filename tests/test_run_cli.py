from __future__ import annotations

import json
from pathlib import Path

import agentgoals.run as run_module
from agentgoals.run import main, run_pipeline
from tests.test_health import enable_health_policy
from tests.test_reconcile import make_workspace, write_goal, write_registry


def stage_statuses(summary) -> list[str]:
    return [stage.status for stage in summary.stages]


def test_run_pipeline_rejects_local_output_under_global_codex(monkeypatch) -> None:
    reconcile_called = False

    def record_reconcile(*args, **kwargs):
        nonlocal reconcile_called
        reconcile_called = True
        return []

    monkeypatch.setattr(run_module, "reconcile", record_reconcile)

    summary = run_pipeline(
        Path("registry.json"),
        Path.home() / ".codex" / "forbidden-local-output",
    )

    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["failed", "skipped", "skipped", "skipped"]
    assert "must not be under the global Codex directory" in str(summary.stages[0].message)
    assert reconcile_called is False


def test_run_pipeline_rejects_global_output_under_global_codex(monkeypatch) -> None:
    workspace = make_workspace("run-forbidden-global-output")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    reconcile_called = False
    aggregate_called = False

    def record_reconcile(*args, **kwargs):
        nonlocal reconcile_called
        reconcile_called = True
        return []

    def record_aggregate(*args, **kwargs):
        nonlocal aggregate_called
        aggregate_called = True
        return []

    monkeypatch.setattr(run_module, "reconcile", record_reconcile)
    monkeypatch.setattr(run_module, "aggregate", record_aggregate)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=workspace / "global-registry.json",
        global_out_dir=Path.home() / ".codex" / "forbidden-global-output",
    )

    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["skipped", "skipped", "failed", "skipped"]
    assert "must not be under the global Codex directory" in str(summary.stages[2].message)
    assert reconcile_called is False
    assert aggregate_called is False
    assert not (workspace / "outputs" / "STATE.json").exists()


def test_cli_json_output_has_stable_shape(capsys) -> None:
    workspace = make_workspace("run-json")
    write_goal(workspace, "active", "needs-review", "review_pending")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    exit_code = main(
        [
            "--registry",
            str(registry),
            "--out",
            str(workspace / "outputs"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert set(payload) == {"version", "operation_id", "status", "exit_code", "stages"}
    assert payload["version"] == 1
    assert isinstance(payload["operation_id"], str)
    assert payload["operation_id"]
    assert payload["status"] == "issues"
    assert payload["exit_code"] == 2
    assert [stage["name"] for stage in payload["stages"]] == [
        "reconcile",
        "validate_local",
        "aggregate",
        "validate_global",
    ]
    assert set(payload["stages"][0]) == {
        "name",
        "status",
        "output_path",
        "entry_count",
        "issue_count",
        "message",
    }


def test_cli_require_global_fails_without_registry(capsys) -> None:
    workspace = make_workspace("run-cli-require-global")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    out_dir = workspace / "outputs"

    exit_code = main(
        [
            "--registry",
            str(registry),
            "--out",
            str(out_dir),
            "--require-global",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["stages"][2]["status"] == "failed"
    assert "Global registry is required" in payload["stages"][2]["message"]
    assert not (out_dir / "STATE.json").exists()


def test_cli_injects_fixed_health_evaluation_date(capsys) -> None:
    workspace = make_workspace("run-health-date")
    write_goal(workspace, "active", "old", "blocked", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    enable_health_policy(registry)
    out_dir = workspace / "outputs"

    exit_code = main(
        [
            "--registry",
            str(registry),
            "--out",
            str(out_dir),
            "--evaluation-date",
            "2026-07-20",
            "--json",
        ]
    )
    capsys.readouterr()
    state = json.loads((out_dir / "STATE.json").read_text(encoding="utf-8"))

    assert exit_code == 2
    assert state["entries"][0]["health"]["evaluated_on"] == "2026-07-20"
    assert "health_stale" in state["entries"][0]["issues"]
