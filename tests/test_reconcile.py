from pathlib import Path
from uuid import uuid4

from goal_lifecycle.reconcile import reconcile


def make_workspace(name: str) -> Path:
    root = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    root.mkdir(parents=True)
    return root


def write_goal(
    root: Path,
    folder: str,
    goal_id: str,
    status: str,
    evidence_status: str = "partial",
    review_verdict: str = "pending",
    write_plan: bool = True,
    write_evidence: bool = True,
    updated: str | None = "2026-07-07",
    priority: int | None = None,
    depends_on: list[str] | None = None,
) -> None:
    goal_dir = root / "goals" / folder / goal_id
    goal_dir.mkdir(parents=True)
    updated_line = f"updated: {updated}\n" if updated is not None else ""
    scheduling_lines = ""
    if priority is not None or depends_on is not None:
        scheduling_lines = f"scheduling:\n  priority: {priority if priority is not None else 50}\n  depends_on:"
        if depends_on:
            scheduling_lines += "\n" + "\n".join(f"    - {dependency}" for dependency in depends_on)
        else:
            scheduling_lines += " []"
        scheduling_lines += "\n"
    (goal_dir / "CONTRACT.md").write_text(
        f"""---
type: goal-contract
schema_version: 1
id: {goal_id}
title: {goal_id}
status: {status}
created: 2026-07-07
{updated_line}completed:
owner: engineering
file_mode: directory
project: test
review:
  required: true
  verdict: {review_verdict}
{scheduling_lines}---

# Goal Contract
""",
        encoding="utf-8",
    )
    if write_plan:
        (goal_dir / "PLAN.md").write_text(
            f"""---
type: goal-plan
schema_version: 1
goal_id: {goal_id}
status: draft
updated: 2026-07-07
contract: ./CONTRACT.md
evidence: ./EVIDENCE.md
---
""",
            encoding="utf-8",
        )
    if write_evidence:
        (goal_dir / "EVIDENCE.md").write_text(
            f"""---
type: goal-evidence
schema_version: 1
goal_id: {goal_id}
status: {evidence_status}
updated: 2026-07-07
contract: ./CONTRACT.md
plan: ./PLAN.md
review:
  verdict: pending
---
""",
            encoding="utf-8",
        )


def write_broken_contract(root: Path, folder: str, goal_id: str) -> None:
    goal_dir = root / "goals" / folder / goal_id
    goal_dir.mkdir(parents=True)
    (goal_dir / "CONTRACT.md").write_text("---\n[not: valid: yaml\n---\n", encoding="utf-8")


def write_broken_related_file(root: Path, folder: str, goal_id: str, filename: str) -> None:
    goal_dir = root / "goals" / folder / goal_id
    (goal_dir / filename).write_text("---\n[not: valid: yaml\n---\n", encoding="utf-8")


def write_registry(path: Path, goal_root: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        f"""{{
  "version": 1,
  "updated": "2026-07-07",
  "roots": [
    {{
      "id": "test-root",
      "label": "Test Root",
      "goal_root": "{goal_root.resolve().as_posix()}",
      "scope": "harness",
      "project": "test",
      "active": true,
      "added": "2026-07-07",
      "last_seen": null
    }}
  ]
}}
""",
        encoding="utf-8",
    )


def test_reconcile_writes_state_outputs() -> None:
    workspace = make_workspace("state-outputs")
    write_goal(workspace, "active", "active-goal", "review_pending")
    registry = workspace / "registry" / "REGISTRY.json"
    out_dir = workspace / "outputs"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, out_dir)

    assert [entry.id for entry in entries] == ["active-goal"]
    assert entries[0].issues == ["evidence_incomplete", "review_pending"]
    assert (out_dir / "STATE.json").exists()
    assert (out_dir / "STATE.md").read_text(encoding="utf-8").startswith("# Goal State")


def test_reconcile_flags_status_folder_mismatch() -> None:
    workspace = make_workspace("status-folder-mismatch")
    write_goal(workspace, "completed", "not-complete", "in_progress", evidence_status="complete")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert "status_folder_mismatch" in entries[0].issues


def test_reconcile_flags_missing_plan_and_evidence() -> None:
    workspace = make_workspace("missing-files")
    write_goal(
        workspace,
        "active",
        "missing-files",
        "in_progress",
        review_verdict="PASS",
        write_plan=False,
        write_evidence=False,
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert entries[0].issues == ["missing_plan", "missing_evidence"]


def test_reconcile_reports_missing_registered_root() -> None:
    workspace = make_workspace("missing-root")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "does-not-exist")

    entries = reconcile(registry, workspace / "outputs")

    assert entries[0].status == "missing"
    assert entries[0].issues == ["missing"]


def test_reconcile_reports_parse_errors() -> None:
    workspace = make_workspace("parse-error")
    write_broken_contract(workspace, "active", "broken")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert entries[0].status == "parse_error"
    assert entries[0].issues == ["parse_error"]


def test_reconcile_reports_related_metadata_parse_errors_without_aborting() -> None:
    workspace = make_workspace("related-parse-error")
    write_goal(workspace, "active", "broken-evidence", "in_progress", evidence_status="complete", review_verdict="PASS")
    write_broken_related_file(workspace, "active", "broken-evidence", "EVIDENCE.md")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert len(entries) == 1
    assert entries[0].id == "broken-evidence"
    assert entries[0].status == "in_progress"
    assert "parse_error" in entries[0].issues
    assert "EVIDENCE.md" in str(entries[0].blocked_reason)


def test_reconcile_flags_stale_when_contract_has_no_updated_date() -> None:
    workspace = make_workspace("stale-contract")
    write_goal(
        workspace,
        "active",
        "stale-goal",
        "in_progress",
        evidence_status="complete",
        review_verdict="PASS",
        updated=None,
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert entries[0].issues == ["stale"]
    rendered = (workspace / "outputs" / "STATE.md").read_text(encoding="utf-8")
    assert "## Stale Entries" in rendered


def test_reconcile_covers_status_lifecycle_without_issues() -> None:
    workspace = make_workspace("status-lifecycle")
    for status in ["draft", "ready", "in_progress", "blocked"]:
        write_goal(workspace, "active", f"{status}-goal", status, evidence_status="complete", review_verdict="PASS")
    for status in ["completed", "cancelled"]:
        write_goal(workspace, "completed", f"{status}-goal", status, evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert {entry.status for entry in entries} == {"draft", "ready", "in_progress", "blocked", "completed", "cancelled"}
    assert all(entry.issues == [] for entry in entries)


def test_rendered_state_groups_actionable_views() -> None:
    workspace = make_workspace("rendered-views")
    write_goal(workspace, "active", "needs-review", "review_pending")
    write_goal(workspace, "completed", "mismatch", "in_progress", evidence_status="complete", review_verdict="PASS")
    write_broken_contract(workspace, "active", "broken")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    reconcile(registry, workspace / "outputs")
    rendered = (workspace / "outputs" / "STATE.md").read_text(encoding="utf-8")

    assert "## Waiting Review" in rendered
    assert "## Evidence Incomplete" in rendered
    assert "## Folder Mismatches" in rendered
    assert "## Parse Errors" in rendered


def test_reconcile_defaults_scheduling_and_writes_queue_summary() -> None:
    workspace = make_workspace("scheduling-default")
    write_goal(workspace, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")
    payload = __import__("json").loads((workspace / "outputs" / "STATE.json").read_text(encoding="utf-8"))

    assert entries[0].goal_key == "test-root/ready-goal"
    assert entries[0].scheduling == {
        "priority": 50,
        "depends_on": [],
        "status": "runnable",
        "queue_position": 1,
        "unmet_dependencies": [],
    }
    assert payload["version"] == 2
    assert payload["queue"]["next_goal"] == "test-root/ready-goal"


def test_dependency_order_wins_over_priority() -> None:
    workspace = make_workspace("dependency-priority")
    write_goal(workspace, "active", "foundation", "ready", evidence_status="complete", review_verdict="PASS", priority=10)
    write_goal(
        workspace,
        "active",
        "urgent-dependent",
        "ready",
        evidence_status="complete",
        review_verdict="PASS",
        priority=100,
        depends_on=["foundation"],
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert [entry.id for entry in entries] == ["foundation", "urgent-dependent"]
    assert entries[0].scheduling["status"] == "runnable"
    assert entries[1].scheduling["status"] == "dependency_blocked"
    assert entries[1].scheduling["unmet_dependencies"] == ["test-root/foundation"]


def test_priority_orders_independent_ready_goals() -> None:
    workspace = make_workspace("priority-order")
    write_goal(workspace, "active", "low", "ready", evidence_status="complete", review_verdict="PASS", priority=10)
    write_goal(workspace, "active", "high", "ready", evidence_status="complete", review_verdict="PASS", priority=90)
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert [entry.id for entry in entries] == ["high", "low"]
    assert [entry.scheduling["queue_position"] for entry in entries] == [1, 2]


def test_completed_dependency_unlocks_dependent_goal() -> None:
    workspace = make_workspace("dependency-completed")
    write_goal(workspace, "completed", "foundation", "completed", evidence_status="complete", review_verdict="PASS")
    write_goal(
        workspace,
        "active",
        "dependent",
        "ready",
        evidence_status="complete",
        review_verdict="PASS",
        depends_on=["foundation"],
    )
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")
    by_id = {entry.id: entry for entry in entries}

    assert by_id["foundation"].scheduling["queue_position"] is None
    assert by_id["dependent"].scheduling["status"] == "runnable"
    assert by_id["dependent"].scheduling["queue_position"] == 1


def test_reconcile_reports_missing_dependency_and_cycle() -> None:
    missing_workspace = make_workspace("dependency-missing")
    write_goal(
        missing_workspace,
        "active",
        "missing-dependent",
        "ready",
        evidence_status="complete",
        review_verdict="PASS",
        depends_on=["not-found"],
    )
    missing_registry = missing_workspace / "registry" / "REGISTRY.json"
    write_registry(missing_registry, missing_workspace / "goals")

    missing_entries = reconcile(missing_registry, missing_workspace / "outputs")

    assert "dependency_missing" in missing_entries[0].issues
    assert missing_entries[0].scheduling["status"] == "invalid"

    cycle_workspace = make_workspace("dependency-cycle")
    write_goal(cycle_workspace, "active", "one", "ready", evidence_status="complete", review_verdict="PASS", depends_on=["two"])
    write_goal(cycle_workspace, "active", "two", "ready", evidence_status="complete", review_verdict="PASS", depends_on=["one"])
    cycle_registry = cycle_workspace / "registry" / "REGISTRY.json"
    write_registry(cycle_registry, cycle_workspace / "goals")

    cycle_entries = reconcile(cycle_registry, cycle_workspace / "outputs")

    assert all("dependency_cycle" in entry.issues for entry in cycle_entries)
    assert all(entry.scheduling["status"] == "invalid" for entry in cycle_entries)


def test_invalid_scheduling_and_pending_review_are_not_runnable() -> None:
    invalid_workspace = make_workspace("scheduling-invalid")
    write_goal(invalid_workspace, "active", "invalid-priority", "ready", evidence_status="complete", review_verdict="PASS")
    contract = invalid_workspace / "goals" / "active" / "invalid-priority" / "CONTRACT.md"
    text = contract.read_text(encoding="utf-8").replace("review:\n", "scheduling:\n  priority: 101\n  depends_on: []\nreview:\n")
    contract.write_text(text, encoding="utf-8")
    invalid_registry = invalid_workspace / "registry" / "REGISTRY.json"
    write_registry(invalid_registry, invalid_workspace / "goals")

    invalid_entry = reconcile(invalid_registry, invalid_workspace / "outputs")[0]

    assert "invalid_scheduling" in invalid_entry.issues
    assert invalid_entry.scheduling["status"] == "invalid"

    review_workspace = make_workspace("scheduling-review")
    write_goal(review_workspace, "active", "review-gate", "ready", evidence_status="complete", review_verdict="pending")
    review_registry = review_workspace / "registry" / "REGISTRY.json"
    write_registry(review_registry, review_workspace / "goals")

    review_entry = reconcile(review_registry, review_workspace / "outputs")[0]

    assert "review_pending" in review_entry.issues
    assert review_entry.scheduling["status"] == "not_ready"


def test_duplicate_goal_keys_are_invalid_and_unranked() -> None:
    workspace = make_workspace("scheduling-duplicate")
    write_goal(workspace, "active", "duplicate", "ready", evidence_status="complete", review_verdict="PASS")
    write_goal(workspace, "completed", "historical", "completed", evidence_status="complete", review_verdict="PASS")
    historical = workspace / "goals" / "completed" / "historical" / "CONTRACT.md"
    historical.write_text(historical.read_text(encoding="utf-8").replace("id: historical", "id: duplicate"), encoding="utf-8")
    registry = workspace / "registry" / "REGISTRY.json"
    write_registry(registry, workspace / "goals")

    entries = reconcile(registry, workspace / "outputs")

    assert all("duplicate_goal_key" in entry.issues for entry in entries)
    assert all(entry.scheduling["status"] == "invalid" for entry in entries)
    assert all(entry.scheduling["queue_position"] is None for entry in entries)
