from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from goal_lifecycle import artifact_tool
from goal_lifecycle.artifact_audit import audit_database_path, list_audit_receipts
from goal_lifecycle.artifact_tool import (
    ArtifactToolError,
    apply_artifacts,
    audit_payload,
    execute_artifact_tool,
    preview_artifacts,
    validate_artifacts,
)
from goal_lifecycle.reconcile import reconcile
from tests.test_reconcile import make_workspace, write_registry


ARTIFACT_FIXTURES = Path("fixtures/goal_artifact_tool/v1")

def decision(*, size: str = "standard", layout: str = "single_file", file_write: bool = True) -> dict:
    return {
        "version": 1,
        "goal_id": "login-retry",
        "title": "Login Retry",
        "project": "test-project",
        "owner": "engineering",
        "date": "2026-07-11",
        "size": size,
        "layout": layout,
        "file_write": file_write,
        "review_required": False,
    }


def fixture_root(name: str) -> tuple[Path, Path]:
    repo = make_workspace(name)
    target = repo / "fixtures" / "artifact-output"
    return repo, target


def test_preview_for_no_write_small_decision_creates_nothing() -> None:
    repo, target = fixture_root("artifact-no-write")

    preview = preview_artifacts(repo, target, decision(size="small", layout="none", file_write=False))

    assert preview.files == ()
    assert not target.exists()


def test_preview_is_deterministic_and_has_no_write_side_effect() -> None:
    repo, target = fixture_root("artifact-preview")

    first = preview_artifacts(repo, target, decision())
    second = preview_artifacts(repo, target, decision())

    assert [item.path for item in first.files] == [target.resolve() / "login-retry-goal-contract.md"]
    assert [item.sha256 for item in first.files] == [item.sha256 for item in second.files]
    assert not target.exists()


def test_apply_single_file_creates_valid_contract_and_audit() -> None:
    repo, target = fixture_root("artifact-single")

    result = apply_artifacts(repo, target, decision())

    assert result.status == "applied"
    assert [item.path.name for item in result.files] == ["login-retry-goal-contract.md"]
    assert result.files[0].path.is_file()
    assert validate_artifacts(result.files) == []
    assert result.files[0].action == "created"


def test_small_explicit_file_output_is_materialized_as_a_single_contract() -> None:
    repo, target = fixture_root("artifact-small-explicit-file")

    result = apply_artifacts(repo, target, decision(size="small", layout="single_file", file_write=True))

    assert [item.path.name for item in result.files] == ["login-retry-goal-contract.md"]
    assert validate_artifacts(result.files) == []


def test_goal_grade_single_file_preserves_the_skill_default_output_mode() -> None:
    repo, target = fixture_root("artifact-goal-grade-single")

    result = apply_artifacts(repo, target, decision(size="goal_grade", layout="single_file", file_write=True))

    assert [item.path.name for item in result.files] == ["login-retry-goal-contract.md"]


def test_standard_artifact_is_visible_to_the_lifecycle_reconciler() -> None:
    repo, _ = fixture_root("artifact-reconcile-single")
    artifact_root = repo / "goals" / "active"
    result = apply_artifacts(repo, artifact_root, decision())
    registry = repo / "registry" / "REGISTRY.json"
    write_registry(registry, repo / "goals")

    entries = reconcile(registry, repo / "outputs")

    assert [entry.id for entry in entries] == ["login-retry"]
    assert Path(entries[0].contract_path) == result.files[0].path.resolve()


def test_apply_directory_creates_contract_plan_and_evidence() -> None:
    repo, target = fixture_root("artifact-directory")

    result = apply_artifacts(repo, target, decision(size="goal_grade", layout="directory"))

    assert [item.path.name for item in result.files] == ["CONTRACT.md", "PLAN.md", "EVIDENCE.md"]
    assert validate_artifacts(result.files) == []


def test_apply_directory_rejects_an_existing_empty_goal_directory_without_replacing_it() -> None:
    repo, target = fixture_root("artifact-directory-conflict")
    existing = target / "login-retry"
    existing.mkdir(parents=True)

    with pytest.raises(ArtifactToolError, match="artifact target already exists"):
        apply_artifacts(repo, target, decision(size="goal_grade", layout="directory"))

    assert existing.is_dir()
    assert list(existing.iterdir()) == []


def test_rejects_path_outside_explicit_repo_root() -> None:
    repo, _ = fixture_root("artifact-escape")

    with pytest.raises(ArtifactToolError, match="outside repository root"):
        preview_artifacts(repo, repo.parent / "outside", decision())


def test_rejects_invalid_decision_combinations_and_goal_ids() -> None:
    repo, target = fixture_root("artifact-invalid")
    invalid = decision(size="small", layout="single_file", file_write=False)

    with pytest.raises(ArtifactToolError, match="small"):
        preview_artifacts(repo, target, invalid)

    escaped = decision()
    escaped["goal_id"] = "../escape"
    with pytest.raises(ArtifactToolError, match="goal_id"):
        preview_artifacts(repo, target, escaped)

    invalid_date = decision()
    invalid_date["date"] = "2026-99-99"
    with pytest.raises(ArtifactToolError, match="date"):
        preview_artifacts(repo, target, invalid_date)

    with pytest.raises(ArtifactToolError, match="JSON object"):
        preview_artifacts(repo, target, [])  # type: ignore[arg-type]


def test_frontmatter_is_valid_when_text_fields_need_yaml_quoting() -> None:
    repo, target = fixture_root("artifact-yaml-quoting")
    quoted = decision()
    quoted["title"] = "Retry: auth #1"
    quoted["project"] = "test: project"

    result = apply_artifacts(repo, target, quoted)

    assert validate_artifacts(result.files) == []


def test_audit_payload_is_hash_only_and_has_no_source_content() -> None:
    repo, target = fixture_root("artifact-audit")
    result = preview_artifacts(repo, target, decision())

    payload = audit_payload("preview", result, repo)

    assert payload["mode"] == "preview"
    assert payload["file_count"] == 1
    assert payload["files"][0]["sha256"] == result.files[0].sha256
    assert payload["files"][0]["path"] == "fixtures/artifact-output/login-retry-goal-contract.md"
    assert str(repo.resolve()) not in payload["files"][0]["path"]
    assert "text" not in payload["files"][0]


def test_execute_preview_never_writes_and_apply_can_emit_audit_log() -> None:
    repo, target = fixture_root("artifact-execute")

    preview = execute_artifact_tool(repo, target, decision(), apply=False)

    assert preview["status"] == "preview"
    assert not target.exists()

    applied = execute_artifact_tool(repo, target, decision(), apply=True, write_audit=True)

    assert applied["status"] == "applied"
    database = audit_database_path(repo)
    assert applied["audit_path"] == ".goal-lifecycle/artifact-audit.sqlite"
    assert database.is_file()
    assert "Login Retry".encode("utf-8") not in database.read_bytes()
    assert list_audit_receipts(repo, goal_id="login-retry")[0]["status"] == "applied"


def test_audit_write_cannot_turn_a_preview_into_a_side_effect() -> None:
    repo, target = fixture_root("artifact-preview-audit")

    with pytest.raises(ArtifactToolError, match="explicit apply"):
        execute_artifact_tool(repo, target, decision(), apply=False, write_audit=True)

    assert not target.exists()


def test_cli_defaults_to_no_write_preview(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo, target = fixture_root("artifact-cli")
    decision_path = repo / "decision.json"
    decision_path.write_text(json.dumps(decision()), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact_tool",
            "--repo-root",
            str(repo),
            "--artifact-root",
            str(target),
            "--decision",
            str(decision_path),
        ],
    )

    artifact_tool.main()

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["mode"] == "preview"
    assert receipt["status"] == "preview"
    assert not target.exists()


def test_cli_apply_with_audit_emits_a_receipt_for_valid_artifacts(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo, target = fixture_root("artifact-cli-apply")
    decision_path = repo / "decision.json"
    decision_path.write_text(json.dumps(decision()), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact_tool",
            "--repo-root",
            str(repo),
            "--artifact-root",
            str(target),
            "--decision",
            str(decision_path),
            "--apply",
            "--audit",
        ],
    )

    artifact_tool.main()

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "applied"
    assert receipt["audit_path"] == ".goal-lifecycle/artifact-audit.sqlite"
    artifacts = tuple(
        artifact_tool.ArtifactFile(
            repo / item["path"],
            (repo / item["path"]).read_text(encoding="utf-8"),
            item["sha256"],
        )
        for item in receipt["files"]
    )
    assert validate_artifacts(artifacts) == []
    audit = list_audit_receipts(repo, goal_id="login-retry")
    assert audit[0]["files"] == [
        {
                "path": item["path"],
            "sha256": item["sha256"],
            "action": item["action"],
        }
        for item in receipt["files"]
    ]


def test_cli_rejects_audit_without_apply_without_writing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo, target = fixture_root("artifact-cli-preview-audit")
    decision_path = repo / "decision.json"
    decision_path.write_text(json.dumps(decision()), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "artifact_tool",
            "--repo-root",
            str(repo),
            "--artifact-root",
            str(target),
            "--decision",
            str(decision_path),
            "--audit",
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        artifact_tool.main()

    assert json.loads(capsys.readouterr().err)["status"] == "error"
    assert not target.exists()


@pytest.mark.parametrize(
    ("name", "expected_status", "expected_files"),
    [
        ("small-no-write.json", "no_write", 0),
        ("standard-single-file.json", "preview", 1),
        ("goal-grade-directory.json", "preview", 3),
    ],
)
def test_versioned_decision_fixtures_cover_supported_layouts(name: str, expected_status: str, expected_files: int) -> None:
    repo, target = fixture_root(f"artifact-fixture-{name}")
    payload = json.loads((ARTIFACT_FIXTURES / name).read_text(encoding="utf-8"))

    result = preview_artifacts(repo, target, payload)

    assert result.status == expected_status
    assert len(result.files) == expected_files
    assert not target.exists()


def test_versioned_invalid_decision_fixture_fails_closed() -> None:
    repo, target = fixture_root("artifact-fixture-invalid")
    payload = json.loads((ARTIFACT_FIXTURES / "invalid-small-write.json").read_text(encoding="utf-8"))

    with pytest.raises(ArtifactToolError, match="small"):
        preview_artifacts(repo, target, payload)


def test_apply_fails_closed_when_any_target_exists() -> None:
    repo, target = fixture_root("artifact-conflict")
    target.mkdir(parents=True)
    (target / "login-retry-goal-contract.md").write_text("existing", encoding="utf-8")

    with pytest.raises(ArtifactToolError, match="already exists"):
        apply_artifacts(repo, target, decision())


def test_single_file_publish_never_overwrites_a_target_created_after_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    repo, target = fixture_root("artifact-single-race")
    final_path = target / "login-retry-goal-contract.md"

    def stage_then_compete(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        final_path.write_text("competing content", encoding="utf-8")

    monkeypatch.setattr("goal_lifecycle.artifact_tool.atomic_write_text", stage_then_compete)

    with pytest.raises(ArtifactToolError, match="already exists"):
        apply_artifacts(repo, target, decision())

    assert final_path.read_text(encoding="utf-8") == "competing content"


def test_directory_publish_never_overwrites_a_target_created_after_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    repo, target = fixture_root("artifact-directory-race")
    final_dir = target / "login-retry"

    def stage_then_compete(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        if path.name == "EVIDENCE.md":
            final_dir.mkdir()
            (final_dir / "external.txt").write_text("competing content", encoding="utf-8")

    monkeypatch.setattr("goal_lifecycle.artifact_tool.atomic_write_text", stage_then_compete)

    with pytest.raises(ArtifactToolError, match="already exists"):
        apply_artifacts(repo, target, decision(size="goal_grade", layout="directory"))

    assert (final_dir / "external.txt").read_text(encoding="utf-8") == "competing content"


def test_directory_write_failure_does_not_publish_partial_target(monkeypatch: pytest.MonkeyPatch) -> None:
    repo, target = fixture_root("artifact-write-failure")
    calls = 0

    def fail_second_write(path: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated failure")
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr("goal_lifecycle.artifact_tool.atomic_write_text", fail_second_write)

    with pytest.raises(OSError, match="simulated failure"):
        apply_artifacts(repo, target, decision(size="goal_grade", layout="directory"))

    assert not (target / "login-retry").exists()
