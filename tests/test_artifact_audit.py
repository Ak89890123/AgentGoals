from __future__ import annotations

import json
import hashlib
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import ANY

import pytest

from goal_lifecycle import artifact_audit, artifact_tool
from goal_lifecycle.artifact_audit import (
    AuditStoreError,
    audit_database_path,
    begin_audit_receipt,
    complete_audit_receipt,
    finalize_pending_audit_receipt,
    import_legacy_jsonl,
    list_audit_receipts,
    normalize_time_boundary,
)
from goal_lifecycle.artifact_tool import ArtifactFile, ArtifactResult, ArtifactToolError, execute_artifact_tool
from tests.test_reconcile import make_workspace


def audit_result(root: Path, *, action: str = "planned") -> ArtifactResult:
    path = root / "goals" / "active" / "login-retry-goal-contract.md"
    return ArtifactResult(
        "preview" if action == "planned" else "applied",
        (ArtifactFile(path, "secret Goal body", "a" * 64, action),),
    )


def test_receipts_live_in_a_repo_local_sqlite_database_without_goal_content() -> None:
    repo = make_workspace("artifact-audit-local")
    preview = audit_result(repo)

    receipt_id = begin_audit_receipt(repo, repo / "goals" / "active", "login-retry", preview)
    complete_audit_receipt(repo, receipt_id, audit_result(repo, action="created"))

    database = audit_database_path(repo)
    rows = list_audit_receipts(repo, goal_id="login-retry")

    assert database == repo.resolve() / ".goal-lifecycle" / "artifact-audit.sqlite"
    assert database.is_file()
    assert rows[0] == {
        "receipt_id": receipt_id,
        "goal_id": "login-retry",
        "status": "applied",
        "mode": "apply",
        "created_at": ANY,
        "completed_at": ANY,
        "files": [
            {
                "path": "goals/active/login-retry-goal-contract.md",
                "sha256": "a" * 64,
                "action": "created",
            }
        ],
    }
    assert list_audit_receipts(repo, since="9999-01-01T00:00:00+00:00") == []
    assert b"secret Goal body" not in database.read_bytes()
    assert str(repo.resolve()).encode("utf-8") not in database.read_bytes()


def test_audit_database_rejects_a_symlinked_audit_directory() -> None:
    repo = make_workspace("artifact-audit-symlink")
    outside = repo.parent / "artifact-audit-symlink-outside"
    outside.mkdir(exist_ok=True)
    audit_dir = repo / ".goal-lifecycle"
    try:
        audit_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this platform does not permit creating directory symlinks")

    with pytest.raises(AuditStoreError, match="must not use symlinks"):
        audit_database_path(repo)


def test_legacy_jsonl_import_is_explicit_idempotent_and_preserves_the_source_file() -> None:
    repo = make_workspace("artifact-audit-legacy")
    legacy = repo / "fixtures" / "legacy-audit.jsonl"
    legacy.parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "mode": "apply",
        "status": "applied",
        "file_count": 1,
        "files": [
            {
                "path": str(repo / "goals" / "active" / "legacy-goal-goal-contract.md"),
                "sha256": "b" * 64,
                "action": "created",
            }
        ],
    }
    legacy.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    original = legacy.read_bytes()

    assert import_legacy_jsonl(repo, legacy) == 1
    assert import_legacy_jsonl(repo, legacy) == 0
    assert legacy.read_bytes() == original
    assert list_audit_receipts(repo, goal_id="legacy-goal") == [
        {
            "receipt_id": ANY,
            "goal_id": "legacy-goal",
            "status": "applied",
            "mode": "apply",
            "created_at": ANY,
            "completed_at": ANY,
            "files": [
                {
                    "path": "goals/active/legacy-goal-goal-contract.md",
                    "sha256": "b" * 64,
                    "action": "created",
                }
            ],
        }
    ]


def test_legacy_import_rejects_a_path_outside_the_explicit_repo_root() -> None:
    repo = make_workspace("artifact-audit-legacy-escape")

    with pytest.raises(AuditStoreError, match="outside repository root"):
        import_legacy_jsonl(repo, repo.parent / "outside.jsonl")


def test_time_boundaries_are_normalized_to_utc_and_require_an_offset() -> None:
    assert normalize_time_boundary("2026-07-12T08:00:00+08:00") == "2026-07-12T00:00:00+00:00"
    with pytest.raises(AuditStoreError, match="include an offset"):
        normalize_time_boundary("2026-07-12T08:00:00")


def test_database_errors_are_exposed_as_audit_store_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_workspace("artifact-audit-database-error")
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True)
    database.touch()

    def unavailable_connection(*_args: object, **_kwargs: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(artifact_audit, "connect", unavailable_connection)

    with pytest.raises(AuditStoreError, match="database operation failed"):
        list_audit_receipts(repo)


def test_concurrent_receipt_creation_serializes_without_losing_records() -> None:
    repo = make_workspace("artifact-audit-contention")
    result = audit_result(repo)

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipt_ids = list(
            executor.map(
                lambda _: begin_audit_receipt(repo, repo / "goals" / "active", "login-retry", result),
                range(2),
            )
        )

    rows = list_audit_receipts(repo, goal_id="login-retry")
    assert {row["receipt_id"] for row in rows} == set(receipt_ids)
    assert {row["status"] for row in rows} == {"pending"}


def test_failed_apply_marks_the_prepared_receipt_failed_without_publishing_an_artifact() -> None:
    repo = make_workspace("artifact-audit-failed-apply")
    target = repo / "goals" / "active"
    target.mkdir(parents=True)
    existing = target / "login-retry-goal-contract.md"
    existing.write_text("external content", encoding="utf-8")
    raw_decision = {
        "version": 1,
        "goal_id": "login-retry",
        "title": "Login Retry",
        "project": "test-project",
        "owner": "engineering",
        "date": "2026-07-12",
        "size": "standard",
        "layout": "single_file",
        "file_write": True,
        "review_required": False,
    }

    with pytest.raises(ArtifactToolError, match="already exists"):
        execute_artifact_tool(repo, target, raw_decision, apply=True, write_audit=True)

    assert existing.read_text(encoding="utf-8") == "external content"
    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "failed"


def test_unknown_schema_version_fails_without_querying_receipts() -> None:
    repo = make_workspace("artifact-audit-schema-version")
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(AuditStoreError, match="unsupported artifact audit schema version"):
        list_audit_receipts(repo)


def test_unversioned_partial_schema_fails_closed_without_changing_the_database() -> None:
    repo = make_workspace("artifact-audit-partial-schema")
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE receipts (receipt_id TEXT PRIMARY KEY)")
    original = database.read_bytes()

    with pytest.raises(AuditStoreError, match="unversioned or partial"):
        list_audit_receipts(repo)

    assert database.read_bytes() == original


def test_claimed_current_schema_with_missing_tables_fails_closed() -> None:
    repo = make_workspace("artifact-audit-incomplete-current-schema")
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(AuditStoreError, match="incomplete artifact audit schema"):
        list_audit_receipts(repo)


def test_claimed_current_schema_with_missing_column_fails_closed() -> None:
    repo = make_workspace("artifact-audit-incomplete-column")
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE receipts (receipt_id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE receipt_files (receipt_id TEXT, path TEXT, sha256 TEXT, action TEXT)")
        connection.execute("CREATE TABLE schema_migrations (version INTEGER, applied_at TEXT)")
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(AuditStoreError, match="incomplete artifact audit schema"):
        list_audit_receipts(repo)


def test_schema_migration_failure_rolls_back_every_created_table() -> None:
    raw = sqlite3.connect(":memory:")

    class FaultingConnection:
        def execute(self, statement: str, *args: object) -> sqlite3.Cursor:
            if "CREATE TABLE receipt_files" in statement:
                raise sqlite3.OperationalError("simulated interrupted migration")
            return raw.execute(statement, *args)

        def commit(self) -> None:
            raw.commit()

        def rollback(self) -> None:
            raw.rollback()

    with pytest.raises(AuditStoreError, match="schema migration failed"):
        artifact_audit.initialize_schema(FaultingConnection())  # type: ignore[arg-type]

    assert raw.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []


def test_completed_artifact_with_unfinished_receipt_is_reported_as_recoverable_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = make_workspace("artifact-audit-complete-failure")
    target = repo / "goals" / "active"
    raw_decision = {
        "version": 1,
        "goal_id": "login-retry",
        "title": "Login Retry",
        "project": "test-project",
        "owner": "engineering",
        "date": "2026-07-12",
        "size": "standard",
        "layout": "single_file",
        "file_write": True,
        "review_required": False,
    }

    def fail_completion(*_args: object, **_kwargs: object) -> Path:
        raise AuditStoreError("simulated audit completion failure")

    monkeypatch.setattr(artifact_tool, "complete_audit_receipt", fail_completion)

    with pytest.raises(ArtifactToolError, match="artifact created but audit receipt remains pending"):
        execute_artifact_tool(repo, target, raw_decision, apply=True, write_audit=True)

    assert (target / "login-retry-goal-contract.md").is_file()
    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "pending"


def test_pending_receipt_requires_explicit_manual_finalization() -> None:
    repo = make_workspace("artifact-audit-manual-finalize")
    path = repo / "goals" / "active" / "login-retry-goal-contract.md"
    path.parent.mkdir(parents=True)
    path.write_text("materialized", encoding="utf-8")
    result = ArtifactResult("applied", (ArtifactFile(path, "materialized", hashlib.sha256(b"materialized").hexdigest(), "created"),))
    receipt_id = begin_audit_receipt(repo, repo / "goals" / "active", "login-retry", result)

    finalize_pending_audit_receipt(repo, receipt_id, result)

    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "applied"


def test_pending_finalization_rejects_a_substituted_manifest() -> None:
    repo = make_workspace("artifact-audit-substituted-manifest")
    path = repo / "goals" / "active" / "login-retry-goal-contract.md"
    path.parent.mkdir(parents=True)
    path.write_text("materialized", encoding="utf-8")
    sha256 = hashlib.sha256(b"materialized").hexdigest()
    result = ArtifactResult("applied", (ArtifactFile(path, "materialized", sha256, "created"),))
    receipt_id = begin_audit_receipt(repo, path.parent, "login-retry", result)
    substituted = {"files": [{"path": "goals/active/other.md", "sha256": sha256, "action": "created"}]}

    with pytest.raises(AuditStoreError, match="does not match"):
        finalize_pending_audit_receipt(repo, receipt_id, substituted)

    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "pending"


def test_cli_finalizes_pending_receipt_only_after_hash_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_workspace("artifact-audit-cli-finalize")
    path = repo / "goals" / "active" / "login-retry-goal-contract.md"
    path.parent.mkdir(parents=True)
    path.write_text("materialized", encoding="utf-8")
    sha256 = hashlib.sha256(b"materialized").hexdigest()
    result = ArtifactResult("applied", (ArtifactFile(path, "materialized", sha256, "created"),))
    receipt_id = begin_audit_receipt(repo, path.parent, "login-retry", result)
    result_path = repo / "recovery-result.json"
    result_path.write_text(
        json.dumps({"status": "applied", "files": [{"path": "goals/active/login-retry-goal-contract.md", "sha256": sha256, "action": "created"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["artifact_audit", "--repo-root", str(repo), "--finalize-pending", receipt_id, "--result", str(result_path)],
    )

    artifact_audit.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "finalized",
        "receipt_id": receipt_id,
        "audit_path": ".goal-lifecycle/artifact-audit.sqlite",
    }
    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "applied"


def test_cli_import_is_explicit_and_reports_the_number_of_new_legacy_receipts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = make_workspace("artifact-audit-cli-import")
    legacy = repo / "legacy.jsonl"
    legacy.write_text(
        json.dumps(
            {
                "mode": "apply",
                "status": "applied",
                "files": [
                    {
                        "path": str(repo / "goals" / "active" / "cli-goal-goal-contract.md"),
                        "sha256": "c" * 64,
                        "action": "created",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["artifact_audit", "--repo-root", str(repo), "--import-legacy", str(legacy)],
    )

    artifact_audit.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "imported",
        "count": 1,
        "audit_path": ".goal-lifecycle/artifact-audit.sqlite",
    }


def test_cli_lists_receipts_by_goal_without_writing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo = make_workspace("artifact-audit-cli-list")
    receipt_id = begin_audit_receipt(repo, repo / "goals" / "active", "login-retry", audit_result(repo))
    complete_audit_receipt(repo, receipt_id, audit_result(repo, action="created"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["artifact_audit", "--repo-root", str(repo), "--list-receipts", "--goal-id", "login-retry"],
    )

    artifact_audit.main()

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "listed"
    assert output["receipts"][0]["receipt_id"] == receipt_id
