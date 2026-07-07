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
) -> None:
    goal_dir = root / "goals" / folder / goal_id
    goal_dir.mkdir(parents=True)
    updated_line = f"updated: {updated}\n" if updated is not None else ""
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
---

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
