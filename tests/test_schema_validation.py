import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from agentgoals.reconcile import reconcile
from agentgoals.validate import resolve_schema_dir, validate_json_file, validate_registry, validate_state
from tests.test_reconcile import make_workspace, write_goal, write_registry


def test_registry_schema_accepts_project_registry() -> None:
    validate_registry(Path("registry/REGISTRY.json"))


def test_generated_state_matches_schema() -> None:
    workspace = make_workspace("schema-state")
    write_goal(workspace, "active", "schema-goal", "review_pending")
    registry = workspace / "registry" / "REGISTRY.json"
    out_dir = workspace / "outputs"
    write_registry(registry, workspace / "goals")
    reconcile(registry, out_dir)

    validate_state(out_dir / "STATE.json")


def test_registry_schema_rejects_missing_required_field() -> None:
    workspace = make_workspace("invalid-registry")
    schema = Path("schemas/goal-registry.schema.json")
    invalid = workspace / "REGISTRY.json"
    invalid.write_text(json.dumps({"version": 1, "updated": "2026-07-07"}), encoding="utf-8")

    with pytest.raises(ValueError, match="roots"):
        validate_json_file(invalid, schema)


def test_state_schema_rejects_unknown_status() -> None:
    workspace = make_workspace("invalid-state")
    schema = Path("schemas/goal-state.schema.json")
    invalid = workspace / "STATE.json"
    invalid.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-07-07T00:00:00+00:00",
                "entries": [
                    {
                        "id": "bad",
                        "title": "Bad",
                        "status": "unknown_status",
                        "project": "test",
                        "goal_root": "goals",
                        "contract_path": "CONTRACT.md",
                        "plan_path": None,
                        "evidence_path": None,
                        "owner": None,
                        "updated": None,
                        "completed": None,
                        "review": {"required": False, "verdict": None},
                        "evidence": {"status": None},
                        "next_action": None,
                        "blocked_reason": None,
                        "source_hash": "",
                        "last_seen": "2026-07-07T00:00:00+00:00",
                        "issues": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown_status"):
        validate_json_file(invalid, schema)


@contextmanager
def schema_test_dir() -> Iterator[Path]:
    path = Path(".tmp") / "schema-install-test" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path.resolve()
    finally:
        import shutil

        shutil.rmtree(path, ignore_errors=True)


def test_schema_resolver_finds_installed_share_directory(monkeypatch) -> None:
    with schema_test_dir() as prefix:
        schema_dir = prefix / "share" / "goal-lifecycle" / "schemas"
        schema_dir.mkdir(parents=True)
        (schema_dir / "goal-state.schema.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(sys, "prefix", str(prefix))

        assert resolve_schema_dir(Path("C:/missing-runtime-root")) == schema_dir.resolve()
