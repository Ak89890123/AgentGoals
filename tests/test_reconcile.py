from pathlib import Path
from uuid import uuid4

from goal_lifecycle.reconcile import reconcile


def make_workspace(name: str) -> Path:
    root = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    root.mkdir(parents=True)
    return root


def write_goal(root: Path, folder: str, goal_id: str, status: str, evidence_status: str = "partial") -> None:
    goal_dir = root / "goals" / folder / goal_id
    goal_dir.mkdir(parents=True)
    (goal_dir / "CONTRACT.md").write_text(
        f"""---
type: goal-contract
schema_version: 1
id: {goal_id}
title: {goal_id}
status: {status}
created: 2026-07-07
updated: 2026-07-07
completed:
owner: engineering
file_mode: directory
project: test
review:
  required: true
  verdict: pending
---

# Goal Contract
""",
        encoding="utf-8",
    )
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
