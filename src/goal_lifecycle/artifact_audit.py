from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_DIRECTORY = ".goal-lifecycle"
AUDIT_FILENAME = "artifact-audit.sqlite"
SCHEMA_VERSION = 1


class AuditStoreError(ValueError):
    pass


def translate_database_errors(function: Any) -> Any:
    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except sqlite3.DatabaseError as exc:
            raise AuditStoreError("artifact audit database operation failed") from exc

    return wrapped


def audit_database_path(repo_root: Path) -> Path:
    repo = repo_root.resolve()
    audit_dir = repo / AUDIT_DIRECTORY
    database = audit_dir / AUDIT_FILENAME
    if audit_dir.is_symlink() or (database.exists() and database.is_symlink()):
        raise AuditStoreError("audit database path must not use symlinks")
    return require_within(database, repo, "audit database path is outside repository root")


def audit_database_reference(repo_root: Path) -> str:
    repo = repo_root.resolve()
    return audit_database_path(repo).relative_to(repo).as_posix()


@translate_database_errors
def begin_audit_receipt(repo_root: Path, artifact_root: Path, goal_id: str, result: Any) -> str:
    repo = repo_root.resolve()
    root = require_within(artifact_root, repo, "artifact root is outside repository root")
    receipt_id = str(uuid.uuid4())
    files = normalize_files(getattr(result, "files", ()), repo)
    with connect(repo) as connection:
        connection.execute(
            """
            INSERT INTO receipts (
                receipt_id, created_at, completed_at, status, mode, goal_id,
                repository_ref, artifact_root, file_count, error_code, legacy_fingerprint
            ) VALUES (?, ?, NULL, 'pending', 'apply', ?, ?, ?, ?, NULL, NULL)
            """,
            (receipt_id, now_iso(), goal_id, ".", relative_path(root, repo), len(files)),
        )
        insert_files(connection, receipt_id, files)
    return receipt_id


@translate_database_errors
def complete_audit_receipt(repo_root: Path, receipt_id: str, result: Any) -> Path:
    repo = repo_root.resolve()
    files = normalize_files(result_files(result), repo)
    status_value = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    status = "no_write" if status_value == "no_write" else "applied"
    with connect(repo) as connection:
        updated = connection.execute(
            """
            UPDATE receipts
            SET completed_at = ?, status = ?, file_count = ?, error_code = NULL
            WHERE receipt_id = ? AND status = 'pending'
            """,
            (now_iso(), status, len(files), receipt_id),
        ).rowcount
        if updated != 1:
            raise AuditStoreError(f"pending audit receipt not found: {receipt_id}")
        connection.execute("DELETE FROM receipt_files WHERE receipt_id = ?", (receipt_id,))
        insert_files(connection, receipt_id, files)
    return audit_database_path(repo)


@translate_database_errors
def finalize_pending_audit_receipt(repo_root: Path, receipt_id: str, result: Any) -> Path:
    """Explicit recovery path: confirm the materialized hashes before closing a pending receipt."""
    repo = repo_root.resolve()
    supplied_files = normalize_files(result_files(result), repo)
    with connect(repo) as connection:
        stored_files = [
            {"path": row["path"], "sha256": row["sha256"], "action": row["action"]}
            for row in connection.execute(
                "SELECT path, sha256, action FROM receipt_files WHERE receipt_id = ? ORDER BY path", (receipt_id,)
            ).fetchall()
        ]
        if not stored_files or supplied_files != stored_files:
            raise AuditStoreError("recovery result does not match the pending receipt manifest")
        for item in stored_files:
            path = repo / item["path"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise AuditStoreError(f"cannot finalize pending receipt; artifact hash does not match: {item['path']}")
        updated = connection.execute(
            "UPDATE receipts SET completed_at = ?, status = 'applied', error_code = NULL WHERE receipt_id = ? AND status = 'pending'",
            (now_iso(), receipt_id),
        ).rowcount
        if updated != 1:
            raise AuditStoreError(f"pending audit receipt not found: {receipt_id}")
    return audit_database_path(repo)


@translate_database_errors
def fail_audit_receipt(repo_root: Path, receipt_id: str, error: BaseException) -> None:
    repo = repo_root.resolve()
    with connect(repo) as connection:
        connection.execute(
            """
            UPDATE receipts
            SET completed_at = ?, status = 'failed', error_code = ?
            WHERE receipt_id = ? AND status = 'pending'
            """,
            (now_iso(), type(error).__name__, receipt_id),
        )


@translate_database_errors
def list_audit_receipts(
    repo_root: Path,
    *,
    goal_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    repo = repo_root.resolve()
    database = audit_database_path(repo)
    if not database.is_file():
        return []
    with connect(repo) as connection:
        conditions = []
        parameters: list[Any] = []
        if goal_id is not None:
            conditions.append("goal_id = ?")
            parameters.append(goal_id)
        if since is not None:
            conditions.append("created_at >= ?")
            parameters.append(normalize_time_boundary(since))
        if until is not None:
            conditions.append("created_at <= ?")
            parameters.append(normalize_time_boundary(until))
        statement = "SELECT receipt_id, goal_id, status, mode, created_at, completed_at FROM receipts"
        if conditions:
            statement += " WHERE " + " AND ".join(conditions)
        statement += " ORDER BY created_at, receipt_id"
        rows = connection.execute(statement, tuple(parameters)).fetchall()
        return [
            {
                "receipt_id": row["receipt_id"],
                "goal_id": row["goal_id"],
                "status": row["status"],
                "mode": row["mode"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "files": [
                    {
                        "path": file_row["path"],
                        "sha256": file_row["sha256"],
                        "action": file_row["action"],
                    }
                    for file_row in connection.execute(
                        """
                        SELECT path, sha256, action
                        FROM receipt_files
                        WHERE receipt_id = ?
                        ORDER BY path
                        """,
                        (row["receipt_id"],),
                    ).fetchall()
                ],
            }
            for row in rows
        ]


@translate_database_errors
def import_legacy_jsonl(repo_root: Path, legacy_path: Path) -> int:
    repo = repo_root.resolve()
    legacy = require_within(legacy_path, repo, "legacy audit path is outside repository root")
    if not legacy.is_file():
        raise AuditStoreError(f"legacy audit file not found: {legacy}")
    imported = 0
    with connect(repo) as connection:
        for raw_line in legacy.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise AuditStoreError(f"invalid legacy audit JSON: {legacy}") from exc
            if not isinstance(payload, dict):
                raise AuditStoreError("legacy audit record must be a JSON object")
            files = normalize_files(payload.get("files", ()), repo)
            fingerprint = hashlib.sha256(raw_line.encode("utf-8")).hexdigest()
            receipt_id = f"legacy-{fingerprint}"
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO receipts (
                    receipt_id, created_at, completed_at, status, mode, goal_id,
                    repository_ref, artifact_root, file_count, error_code, legacy_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    receipt_id,
                    now_iso(),
                    now_iso(),
                    normalize_status(payload.get("status")),
                    str(payload.get("mode") or "apply"),
                    infer_goal_id(files),
                    ".",
                    infer_artifact_root(files),
                    len(files),
                    fingerprint,
                ),
            )
            if cursor.rowcount:
                insert_files(connection, receipt_id, files)
                imported += 1
    return imported


def connect(repo: Path) -> sqlite3.Connection:
    database = audit_database_path(repo)
    database.parent.mkdir(parents=True, exist_ok=True)
    database = audit_database_path(repo)
    connection = sqlite3.connect(database)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        initialize_schema(connection)
    except Exception:
        connection.close()
        raise
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise AuditStoreError("cannot read artifact audit schema version") from exc
    if version not in {0, SCHEMA_VERSION}:
        raise AuditStoreError(f"unsupported artifact audit schema version: {version}")
    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    if version == SCHEMA_VERSION:
        required_columns = {
            "receipts": {"receipt_id", "created_at", "completed_at", "status", "mode", "goal_id", "repository_ref", "artifact_root", "file_count", "error_code", "legacy_fingerprint"},
            "receipt_files": {"receipt_id", "path", "sha256", "action"},
            "schema_migrations": {"version", "applied_at"},
        }
        if not set(required_columns).issubset(tables) or any(
            not columns.issubset({row[1] for row in connection.execute(f"PRAGMA table_info({table})")})
            for table, columns in required_columns.items()
        ):
            raise AuditStoreError("incomplete artifact audit schema for current version")
        return
    try:
        connection.execute("BEGIN IMMEDIATE")
        # Another process may have initialized the database while this
        # connection waited for the write lock. Re-read under that lock rather
        # than acting on the stale pre-lock empty-schema snapshot.
        locked_version = connection.execute("PRAGMA user_version").fetchone()[0]
        locked_tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        if locked_version == SCHEMA_VERSION:
            connection.commit()
            return initialize_schema(connection)
        if locked_version != 0 or locked_tables:
            connection.rollback()
            raise AuditStoreError("unversioned or partial artifact audit schema; refusing to modify it")
        connection.execute(
            """
            CREATE TABLE receipts (
                receipt_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('pending', 'applied', 'failed', 'no_write')),
                mode TEXT NOT NULL,
                goal_id TEXT,
                repository_ref TEXT NOT NULL,
                artifact_root TEXT NOT NULL,
                file_count INTEGER NOT NULL,
                error_code TEXT,
                legacy_fingerprint TEXT UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE receipt_files (
                receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                action TEXT NOT NULL,
                PRIMARY KEY (receipt_id, path)
            )
            """
        )
        connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        connection.execute("CREATE INDEX receipts_goal_created_idx ON receipts(goal_id, created_at)")
        connection.execute("CREATE INDEX receipts_status_created_idx ON receipts(status, created_at)")
        connection.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (SCHEMA_VERSION, now_iso()))
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise AuditStoreError("artifact audit schema migration failed") from exc


def insert_files(connection: sqlite3.Connection, receipt_id: str, files: Iterable[dict[str, str]]) -> None:
    connection.executemany(
        "INSERT INTO receipt_files (receipt_id, path, sha256, action) VALUES (?, ?, ?, ?)",
        [(receipt_id, item["path"], item["sha256"], item["action"]) for item in files],
    )


def normalize_files(raw_files: Iterable[Any], repo: Path) -> list[dict[str, str]]:
    files = []
    for item in raw_files:
        if isinstance(item, dict):
            raw_path = item.get("path")
            sha256 = item.get("sha256")
            action = item.get("action")
        else:
            raw_path = getattr(item, "path", None)
            sha256 = getattr(item, "sha256", None)
            action = getattr(item, "action", None)
        if not isinstance(raw_path, (str, Path)) or not isinstance(sha256, str) or not isinstance(action, str):
            raise AuditStoreError("audit files require path, sha256, and action")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            from_cwd = candidate.resolve()
            try:
                from_cwd.relative_to(repo)
            except ValueError:
                candidate = repo / candidate
            else:
                candidate = from_cwd
        path = require_within(candidate, repo, "artifact path is outside repository root")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256.lower()):
            raise AuditStoreError(f"invalid artifact sha256: {path}")
        files.append({"path": relative_path(path, repo), "sha256": sha256, "action": action})
    return files


def result_files(result: Any) -> Iterable[Any]:
    return result.get("files", ()) if isinstance(result, dict) else getattr(result, "files", ())


def require_within(path: Path, repo: Path, message: str) -> Path:
    resolved = comparable_resolved_path(path)
    root = comparable_resolved_path(repo)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AuditStoreError(message) from exc
    return resolved


def comparable_resolved_path(path: Path) -> Path:
    resolved = str(path.resolve())
    if os.name == "nt" and resolved.startswith("\\\\?\\"):
        resolved = resolved[4:]
    return Path(resolved)


def relative_path(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def infer_goal_id(files: list[dict[str, str]]) -> str | None:
    if not files:
        return None
    name = Path(files[0]["path"]).name
    suffix = "-goal-contract.md"
    if name.endswith(suffix):
        return name[: -len(suffix)] or None
    return Path(files[0]["path"]).parent.name or None


def infer_artifact_root(files: list[dict[str, str]]) -> str:
    if not files:
        return "."
    return Path(files[0]["path"]).parent.as_posix()


def normalize_status(value: Any) -> str:
    status = str(value or "applied")
    if status not in {"pending", "applied", "failed", "no_write"}:
        raise AuditStoreError(f"unsupported legacy receipt status: {status}")
    return status


def normalize_time_boundary(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AuditStoreError(f"invalid receipt time boundary: {value}") from exc
    if parsed.tzinfo is None:
        raise AuditStoreError(f"receipt time boundary must include an offset: {value}")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import or query repo-local Goal artifact SQLite receipts.")
    parser.add_argument("--repo-root", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--import-legacy", type=Path, help="Explicit JSONL receipt file to import without deleting it.")
    action.add_argument("--list-receipts", action="store_true", help="Read receipts without mutating the database.")
    action.add_argument("--finalize-pending", metavar="RECEIPT_ID", help="Explicitly finalize one pending receipt after hash validation.")
    parser.add_argument("--result", type=Path, help="Hash-only JSON receipt payload required with --finalize-pending.")
    parser.add_argument("--goal-id", help="Optional Goal id filter for --list-receipts.")
    parser.add_argument("--since", help="Optional inclusive ISO-8601 created-at lower bound for --list-receipts.")
    parser.add_argument("--until", help="Optional inclusive ISO-8601 created-at upper bound for --list-receipts.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.list_receipts:
            print(
                json.dumps(
                    {
                        "status": "listed",
                        "receipts": list_audit_receipts(
                            args.repo_root,
                            goal_id=args.goal_id,
                            since=args.since,
                            until=args.until,
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            return
        if args.finalize_pending:
            if args.result is None:
                raise AuditStoreError("--result is required with --finalize-pending")
            result = json.loads(args.result.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise AuditStoreError("recovery result must be a JSON object")
            finalize_pending_audit_receipt(args.repo_root, args.finalize_pending, result)
            print(
                json.dumps(
                    {
                        "status": "finalized",
                        "receipt_id": args.finalize_pending,
                        "audit_path": audit_database_reference(args.repo_root),
                    },
                    ensure_ascii=False,
                )
            )
            return
        count = import_legacy_jsonl(args.repo_root, args.import_legacy)
    except (AuditStoreError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc
    print(
        json.dumps(
            {
                "status": "imported",
                "count": count,
                "audit_path": audit_database_reference(args.repo_root),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
