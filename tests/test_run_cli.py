from __future__ import annotations

import json
from pathlib import Path

import goal_lifecycle.run as run_module
from goal_lifecycle.run import main, run_pipeline
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
    aggregate_called = False

    def record_aggregate(*args, **kwargs):
        nonlocal aggregate_called
        aggregate_called = True
        return []

    monkeypatch.setattr(run_module, "aggregate", record_aggregate)

    summary = run_pipeline(
        registry,
        workspace / "outputs",
        global_registry_path=workspace / "global-registry.json",
        global_out_dir=Path.home() / ".codex" / "forbidden-global-output",
    )

    assert summary.exit_code == 1
    assert stage_statuses(summary) == ["passed", "passed", "failed", "skipped"]
    assert "must not be under the global Codex directory" in str(summary.stages[2].message)
    assert aggregate_called is False


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
    assert set(payload) == {"version", "status", "exit_code", "stages"}
    assert payload["version"] == 1
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
