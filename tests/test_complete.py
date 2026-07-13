from __future__ import annotations

from pathlib import Path

import pytest

from agentgoals.complete import complete_goal
from tests.test_reconcile import make_workspace


def write_completed_goal(repo: Path, goal_id: str = "done-goal") -> Path:
    goal = repo / "goals" / "active" / goal_id
    goal.mkdir(parents=True)
    (goal / "CONTRACT.md").write_text(f"""---
type: goal-contract
id: {goal_id}
status: completed
completed: 2026-07-13
review:
  required: true
  verdict: PASS
---
""", encoding="utf-8")
    (goal / "PLAN.md").write_text(f"""---
type: goal-plan
goal_id: {goal_id}
status: completed
---
""", encoding="utf-8")
    (goal / "EVIDENCE.md").write_text(f"""---
type: goal-evidence
goal_id: {goal_id}
status: complete
review:
  verdict: PASS
---
""", encoding="utf-8")
    return goal


def test_complete_moves_goal_then_refreshes_exactly_once() -> None:
    root = make_workspace("complete-success")
    repo = (root / "repo").resolve()
    source = write_completed_goal(repo)
    global_registry = (root / "REGISTRY.json").resolve()
    global_registry.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    result = complete_goal(repo, "done-goal", global_registry, refresher=lambda argv: calls.append(list(argv)) or 0, preflight=lambda *_: None)

    assert not source.exists()
    assert (repo / "goals" / "completed" / "done-goal").is_dir()
    assert len(calls) == 1
    assert result["refresh_invocations"] == 1
    assert result["outcome"] == "completed"


def test_complete_invalid_metadata_neither_moves_nor_refreshes() -> None:
    root = make_workspace("complete-invalid")
    repo = (root / "repo").resolve()
    source = write_completed_goal(repo)
    contract = source / "CONTRACT.md"
    contract.write_text(contract.read_text(encoding="utf-8").replace("status: completed", "status: in_progress"), encoding="utf-8")
    global_registry = (root / "REGISTRY.json").resolve()
    global_registry.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    with pytest.raises(ValueError, match="status must be completed"):
        complete_goal(repo, "done-goal", global_registry, refresher=lambda argv: calls.append(list(argv)) or 0, preflight=lambda *_: None)

    assert source.is_dir()
    assert not calls


def test_complete_keeps_authoritative_move_and_reports_refresh_failure() -> None:
    root = make_workspace("complete-refresh-failure")
    repo = (root / "repo").resolve()
    write_completed_goal(repo)
    global_registry = (root / "REGISTRY.json").resolve()
    global_registry.write_text("{}", encoding="utf-8")

    result = complete_goal(repo, "done-goal", global_registry, refresher=lambda _: 2, preflight=lambda *_: None)

    assert result["outcome"] == "completed_state_refresh_issues"
    assert result["refresh_exit_code"] == 2
    assert (repo / "goals" / "completed" / "done-goal").exists()


def test_complete_rejects_completed_root_link_that_escapes_repo() -> None:
    root = make_workspace("complete-link-escape")
    repo = (root / "repo").resolve()
    source = write_completed_goal(repo)
    outside = (root / "outside").resolve()
    outside.mkdir()
    completed = repo / "goals" / "completed"
    try:
        completed.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    global_registry = (root / "REGISTRY.json").resolve()
    global_registry.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    with pytest.raises(ValueError, match="completed goal root escapes"):
        complete_goal(repo, "done-goal", global_registry, refresher=lambda argv: calls.append(list(argv)) or 0, preflight=lambda *_: None)

    assert source.is_dir()
    assert not (outside / "done-goal").exists()
    assert not calls
