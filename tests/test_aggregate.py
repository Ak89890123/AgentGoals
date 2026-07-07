import json
from pathlib import Path

import pytest

from goal_lifecycle.aggregate import aggregate, load_global_registry
from goal_lifecycle.reconcile import reconcile
from tests.test_reconcile import make_workspace, write_goal, write_registry


def write_global_registry(path: Path, roots: list[dict]) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"version": 1, "updated": "2026-07-07", "roots": roots}, indent=2),
        encoding="utf-8",
    )


def global_root(workspace: Path, root_id: str, state_path: Path, active: bool = True) -> dict:
    return {
        "id": root_id,
        "label": root_id,
        "repo_root": workspace.resolve().as_posix(),
        "goal_root": (workspace / "goals").resolve().as_posix(),
        "state_path": state_path.resolve().as_posix(),
        "scope": "harness",
        "project": "test",
        "active": active,
        "added": "2026-07-07",
        "last_seen": None,
    }


def test_aggregate_merges_registered_repo_state() -> None:
    workspace = make_workspace("aggregate-merge")
    write_goal(workspace, "active", "repo-goal", "review_pending")
    repo_registry = workspace / "registry" / "REGISTRY.json"
    repo_out = workspace / "outputs"
    write_registry(repo_registry, workspace / "goals")
    reconcile(repo_registry, repo_out)

    global_registry = workspace / "global" / "REGISTRY.json"
    out_dir = workspace / "global-out"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", repo_out / "STATE.json")])

    entries = aggregate(global_registry, out_dir)

    assert [entry.id for entry in entries] == ["repo-goal"]
    assert (out_dir / "STATE.json").exists()
    rendered = (out_dir / "STATE.md").read_text(encoding="utf-8")
    assert "repo-goal" in rendered


def test_aggregate_reports_missing_repo_state_without_source_mutation() -> None:
    workspace = make_workspace("aggregate-missing")
    missing_state = workspace / "outputs" / "STATE.json"
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "missing-repo", missing_state)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert len(entries) == 1
    assert entries[0].id == "missing-repo"
    assert entries[0].status == "missing"
    assert entries[0].issues == ["missing"]
    assert not (workspace / "goals").exists()


def test_aggregate_reports_malformed_repo_state() -> None:
    workspace = make_workspace("aggregate-malformed")
    state_path = workspace / "outputs" / "STATE.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"version": 1, "entries": "not-valid"}', encoding="utf-8")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "bad-repo", state_path)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert len(entries) == 1
    assert entries[0].id == "bad-repo"
    assert entries[0].status == "parse_error"
    assert entries[0].issues == ["parse_error"]


def test_aggregate_skips_inactive_roots() -> None:
    workspace = make_workspace("aggregate-inactive")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "inactive-repo", workspace / "missing" / "STATE.json", active=False)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert entries == []
    rendered = (workspace / "global-out" / "STATE.md").read_text(encoding="utf-8")
    assert "No goals found" in rendered


def test_global_registry_schema_rejects_missing_state_path() -> None:
    workspace = make_workspace("aggregate-schema")
    registry = workspace / "global" / "REGISTRY.json"
    root = global_root(workspace, "bad-registry", workspace / "outputs" / "STATE.json")
    del root["state_path"]
    write_global_registry(registry, [root])

    with pytest.raises(ValueError, match="state_path"):
        load_global_registry(registry)


def test_global_registry_accepts_utf8_bom() -> None:
    workspace = make_workspace("aggregate-bom")
    registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(registry, [global_root(workspace, "bom-registry", workspace / "outputs" / "STATE.json")])
    text = registry.read_text(encoding="utf-8")
    registry.write_text(text, encoding="utf-8-sig")

    roots = load_global_registry(registry)

    assert roots[0].id == "bom-registry"


def test_global_registry_rejects_relative_paths() -> None:
    workspace = make_workspace("aggregate-relative-registry")
    registry = workspace / "global" / "REGISTRY.json"
    root = global_root(workspace, "relative-registry", workspace / "outputs" / "STATE.json")
    root["state_path"] = "outputs/STATE.json"
    write_global_registry(registry, [root])

    with pytest.raises(ValueError, match="state_path"):
        load_global_registry(registry)


def test_global_registry_rejects_state_path_outside_repo_root() -> None:
    workspace = make_workspace("aggregate-registry-outside")
    registry = workspace / "global" / "REGISTRY.json"
    outside_state = workspace.parent / "outside" / "STATE.json"
    write_global_registry(registry, [global_root(workspace, "outside-registry", outside_state)])

    with pytest.raises(ValueError, match="outside repo_root"):
        load_global_registry(registry)


def test_aggregate_rebases_relative_repo_state_paths() -> None:
    workspace = make_workspace("aggregate-rebase")
    write_goal(workspace, "active", "repo-goal", "review_pending")
    repo_registry = workspace / "registry" / "REGISTRY.json"
    repo_out = workspace / "outputs"
    write_registry(repo_registry, workspace / "goals")
    reconcile(repo_registry, repo_out)
    state_path = repo_out / "STATE.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["entries"][0]["goal_root"] = "goals"
    payload["entries"][0]["contract_path"] = "goals/active/repo-goal/CONTRACT.md"
    payload["entries"][0]["plan_path"] = "goals/active/repo-goal/PLAN.md"
    payload["entries"][0]["evidence_path"] = "goals/active/repo-goal/EVIDENCE.md"
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", state_path)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert entries[0].status == "review_pending"
    assert Path(entries[0].goal_root).is_absolute()
    assert Path(entries[0].contract_path).is_absolute()
    assert Path(entries[0].contract_path).resolve() == (workspace / "goals" / "active" / "repo-goal" / "CONTRACT.md").resolve()


def test_aggregate_reports_repo_state_path_escape() -> None:
    workspace = make_workspace("aggregate-path-escape")
    write_goal(workspace, "active", "repo-goal", "review_pending")
    repo_registry = workspace / "registry" / "REGISTRY.json"
    repo_out = workspace / "outputs"
    write_registry(repo_registry, workspace / "goals")
    reconcile(repo_registry, repo_out)
    state_path = repo_out / "STATE.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["entries"][0]["contract_path"] = "../outside/CONTRACT.md"
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", state_path)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert len(entries) == 1
    assert entries[0].id == "repo-one"
    assert entries[0].status == "parse_error"
    assert entries[0].issues == ["parse_error"]
    assert "outside registered goal_root" in str(entries[0].blocked_reason)


def test_aggregate_accepts_repo_state_utf8_bom() -> None:
    workspace = make_workspace("aggregate-state-bom")
    write_goal(workspace, "active", "repo-goal", "review_pending")
    repo_registry = workspace / "registry" / "REGISTRY.json"
    repo_out = workspace / "outputs"
    write_registry(repo_registry, workspace / "goals")
    reconcile(repo_registry, repo_out)
    state_path = repo_out / "STATE.json"
    state_text = state_path.read_text(encoding="utf-8")
    state_path.write_text(state_text, encoding="utf-8-sig")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", state_path)])

    entries = aggregate(global_registry, workspace / "global-out")

    assert [entry.id for entry in entries] == ["repo-goal"]


def test_aggregate_merges_multiple_active_roots_with_duplicate_goal_ids() -> None:
    workspace_one = make_workspace("aggregate-multi-one")
    workspace_two = make_workspace("aggregate-multi-two")
    for workspace in (workspace_one, workspace_two):
        write_goal(workspace, "active", "shared-goal", "review_pending")
        repo_registry = workspace / "registry" / "REGISTRY.json"
        write_registry(repo_registry, workspace / "goals")
        reconcile(repo_registry, workspace / "outputs")
    global_registry = workspace_one / "global" / "REGISTRY.json"
    write_global_registry(
        global_registry,
        [
            global_root(workspace_one, "repo-one", workspace_one / "outputs" / "STATE.json"),
            global_root(workspace_two, "repo-two", workspace_two / "outputs" / "STATE.json"),
        ],
    )

    entries = aggregate(global_registry, workspace_one / "global-out")

    assert [entry.id for entry in entries] == ["shared-goal", "shared-goal"]
    assert len({entry.contract_path for entry in entries}) == 2
    assert all(Path(entry.contract_path).is_absolute() for entry in entries)
