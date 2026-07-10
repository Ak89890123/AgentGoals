import json

from goal_lifecycle.queue import main, query_registry, query_state
from goal_lifecycle.reconcile import reconcile
from tests.test_aggregate import global_root, write_global_registry
from tests.test_reconcile import make_workspace, write_goal, write_registry


def test_query_state_returns_compact_ordered_queue() -> None:
    workspace = make_workspace("queue-state")
    write_goal(workspace, "active", "first", "ready", evidence_status="complete", review_verdict="PASS", priority=90)
    write_goal(workspace, "active", "second", "draft", evidence_status="complete", review_verdict="PASS", priority=50)
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    reconcile(registry, workspace / "outputs")

    payload = query_state(workspace / "outputs" / "STATE.json")

    assert payload["queue"]["next_goal"] == "test-root/first"
    assert [entry["goal_key"] for entry in payload["entries"]] == ["test-root/first", "test-root/second"]
    assert set(payload["entries"][0]) == {
        "goal_key",
        "title",
        "project",
        "lifecycle_status",
        "scheduling_status",
        "priority",
        "queue_position",
        "depends_on",
        "unmet_dependencies",
        "contract_path",
    }
    assert payload["invalid_entries"] == []


def test_query_registry_aggregates_without_writing_output() -> None:
    workspace = make_workspace("queue-registry")
    write_goal(workspace, "active", "ready", "ready", evidence_status="complete", review_verdict="PASS")
    repo_registry = workspace / "registry" / "REGISTRY.json"
    write_registry(repo_registry, workspace / "goals")
    reconcile(repo_registry, workspace / "outputs")
    global_registry = workspace / "global" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(workspace, "repo-one", workspace / "outputs" / "STATE.json")])

    payload = query_registry(global_registry)

    assert payload["queue"]["next_goal"] == "repo-one/ready"
    assert not (workspace / "global-out").exists()


def test_queue_cli_json_output(capsys) -> None:
    workspace = make_workspace("queue-cli")
    write_goal(workspace, "active", "ready", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    reconcile(registry, workspace / "outputs")

    main(["--state", str(workspace / "outputs" / "STATE.json"), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["version"] == 1
    assert payload["queue"]["next_goal"] == "test-root/ready"


def test_query_reports_invalid_entries_outside_ranked_queue() -> None:
    workspace = make_workspace("queue-invalid")
    write_goal(
        workspace,
        "active",
        "broken-dependency",
        "ready",
        evidence_status="complete",
        review_verdict="PASS",
        depends_on=["missing"],
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")
    reconcile(registry, workspace / "outputs")

    payload = query_state(workspace / "outputs" / "STATE.json")

    assert payload["entries"] == []
    assert payload["invalid_entries"][0]["goal_key"] == "test-root/broken-dependency"
    assert "dependency_missing" in payload["invalid_entries"][0]["issues"]
