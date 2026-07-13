from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

import agentgoals.onboard as onboard_module
import agentgoals.reconcile as reconcile_module
from agentgoals.onboard import main, onboard_repository, rollback_created_files
from agentgoals.run import RunSummary, StageResult
from agentgoals.validate import validate_json_file
from tests.test_aggregate import global_root, write_global_registry
from tests.test_reconcile import make_workspace, write_goal, write_registry


def make_repo(name: str) -> Path:
    repo = make_workspace(name)
    (repo / ".git").mkdir()
    return repo


def registration_plan(repo: Path, global_registry: Path) -> str:
    dry_run = onboard_repository(repo, global_registry_path=global_registry.resolve())
    assert dry_run.outcome == "dry_run_ready"
    assert dry_run.registration["plan_sha256"]
    return dry_run.registration["plan_sha256"]


def test_canonical_onboarding_rejects_relative_repository_without_resolution() -> None:
    result = onboard_repository(Path("relative/repo"))

    assert result.outcome == "conflict"
    assert result.exit_code == 1
    assert result.target_repo == str(Path("relative/repo"))
    assert "absolute repository path" in result.message
    assert result.metrics == {
        "resume_context_bytes": 0,
        "semantic_model_calls": 0,
        "pipeline_invocations": 0,
    }


def test_canonical_cli_rejects_relative_repository(capsys) -> None:
    exit_code = main(["--repo", "relative/repo", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["outcome"] == "conflict"
    assert payload["message"] == "--repo must be an absolute repository path."


def test_dry_run_reports_plan_without_writing() -> None:
    repo = make_repo("onboard-dry-run")

    result = onboard_repository(repo)

    assert result.outcome == "dry_run_ready"
    assert result.exit_code == 0
    assert result.mode == "check"
    assert "create_goal_directories" in result.planned_actions
    assert "create_repo_registry" in result.planned_actions
    assert "emit_global_registration_proposal_after_validation" in result.planned_actions
    assert result.proposal is None
    assert not (repo / "goals").exists()
    assert not (repo / "registry").exists()
    assert not (repo / "outputs").exists()


def test_apply_scaffolds_reconciles_and_emits_registration_proposal() -> None:
    repo = make_repo("onboard-apply")

    result = onboard_repository(repo, apply=True)

    assert result.outcome == "registration_required"
    assert result.exit_code == 2
    assert result.mode == "apply"
    assert result.registered is False
    assert result.proposal is not None
    assert Path(result.proposal["repo_root"]) == repo.resolve()
    assert (repo / "goals" / "active").is_dir()
    assert (repo / "goals" / "completed").is_dir()
    assert (repo / "registry" / "REGISTRY.json").is_file()
    assert (repo / "outputs" / "goal-lifecycle" / "STATE.json").is_file()
    report = repo / "outputs" / "ONBOARDING.json"
    assert report.is_file()
    validate_json_file(report, Path("schemas/onboarding-result.schema.json"))


def test_apply_is_idempotent_and_preserves_goal_sources() -> None:
    repo = make_repo("onboard-idempotent")
    write_goal(repo, "active", "legacy-goal", "draft")
    source_paths = sorted((repo / "goals").rglob("*.md"))
    before = {str(path): path.read_bytes() for path in source_paths}

    first = onboard_repository(repo, apply=True)
    registry_before = (repo / "registry" / "REGISTRY.json").read_bytes()
    second = onboard_repository(repo, apply=True)

    assert first.outcome == "registration_required"
    assert second.outcome == "registration_required"
    assert second.planned_actions == []
    assert (repo / "registry" / "REGISTRY.json").read_bytes() == registry_before
    assert {str(path): path.read_bytes() for path in source_paths} == before
    assert all(item["before_sha256"] == item["after_sha256"] for item in second.preserved_files)


def test_preflight_rejects_non_repository_and_path_escape() -> None:
    not_repo = make_workspace("onboard-not-repo")
    missing_git = onboard_repository(not_repo)
    escaped = onboard_repository(make_repo("onboard-escape"), local_out=Path("../escape"))

    assert missing_git.outcome == "conflict"
    assert "Git repository" in str(missing_git.message)
    assert escaped.outcome == "conflict"
    assert "inside target repository" in str(escaped.message)


def test_explicit_invalid_root_id_still_emits_schema_valid_conflict() -> None:
    repo = make_repo("onboard-invalid-root-id")

    result = onboard_repository(repo, root_id="BAD_ID")

    assert result.outcome == "conflict"
    assert result.root_id == "bad-id"
    validate_json_payload = result.to_dict()
    onboard_module.validate_result(validate_json_payload)


def test_all_write_target_aliases_and_global_registry_alias_fail_closed() -> None:
    repos = [make_repo(f"onboard-alias-{index}") for index in range(4)]
    results = [
        onboard_repository(repos[0], apply=True, report=Path("outputs/goal-lifecycle/STATE.md")),
        onboard_repository(repos[1], apply=True, registry=Path("outputs/goal-lifecycle/STATE.md")),
        onboard_repository(repos[2], apply=True, report=Path("outputs/global/STATE.json")),
        onboard_repository(repos[3], apply=True, registry=Path("outputs/goal-lifecycle/registry.json")),
    ]
    for repo, result in zip(repos, results, strict=True):
        assert result.outcome == "conflict"
        assert not (repo / "goals").exists()

    protected_repo = make_repo("onboard-global-registry-alias")
    protected = protected_repo / "outputs" / "goal-lifecycle" / "STATE.json"
    result = onboard_repository(
        protected_repo,
        apply=True,
        global_registry_path=protected,
    )
    assert result.outcome == "conflict"
    assert "Global registry" in str(result.message)
    assert not (protected_repo / "goals").exists()


def test_preflight_rejects_unrecognized_output_collision() -> None:
    repo = make_repo("onboard-output-collision")
    output = repo / "outputs"
    output.mkdir(parents=True)
    report = output / "ONBOARDING.json"
    report.write_text("user data", encoding="utf-8")

    result = onboard_repository(repo, apply=True)

    assert result.outcome == "conflict"
    assert "not recognized" in str(result.message)
    assert report.read_text(encoding="utf-8") == "user data"
    assert not (repo / "registry").exists()


def test_unrelated_sibling_outputs_do_not_block_onboarding() -> None:
    repo = make_repo("onboard-output-sibling")
    sibling = repo / "outputs" / "historical" / "snapshot.json"
    sibling.parent.mkdir(parents=True)
    sibling.write_text('{"keep": true}', encoding="utf-8")

    result = onboard_repository(repo, apply=True)

    assert result.outcome == "registration_required"
    assert sibling.read_text(encoding="utf-8") == '{"keep": true}'


def test_apply_merges_partial_registry_without_replacing_existing_roots() -> None:
    repo = make_repo("onboard-partial-registry")
    other_goal_root = repo / "other-goals"
    other_goal_root.mkdir()
    registry = repo / "registry" / "REGISTRY.json"
    write_registry(registry, other_goal_root)
    before_payload = json.loads(registry.read_text(encoding="utf-8"))

    result = onboard_repository(repo, apply=True)
    after_payload = json.loads(registry.read_text(encoding="utf-8"))

    assert result.outcome == "registration_required"
    assert result.planned_actions == ["create_goal_directories", "update_repo_registry"]
    assert after_payload["roots"][0] == before_payload["roots"][0]
    assert len(after_payload["roots"]) == 2


def test_existing_custom_root_id_is_reused_when_not_explicitly_overridden() -> None:
    repo = make_repo("onboard-existing-root-id")
    registry = repo / "registry" / "REGISTRY.json"
    write_registry(registry, repo / "goals")

    result = onboard_repository(repo, apply=True)

    assert result.outcome == "registration_required"
    assert result.root_id == "test-root"
    assert result.proposal is not None
    assert result.proposal["id"] == "test-root"
    assert result.proposal["label"] == "Test Root"
    assert result.proposal["project"] == "test"
    assert result.planned_actions == ["create_goal_directories"]


def test_invalid_and_duplicate_repo_registries_fail_closed() -> None:
    invalid_repo = make_repo("onboard-invalid-registry")
    invalid_registry = invalid_repo / "registry" / "REGISTRY.json"
    invalid_registry.parent.mkdir()
    invalid_registry.write_text('{"version": 1, "roots": []}', encoding="utf-8")

    duplicate_repo = make_repo("onboard-duplicate-registry")
    duplicate_registry = duplicate_repo / "registry" / "REGISTRY.json"
    write_registry(duplicate_registry, duplicate_repo / "goals")
    payload = json.loads(duplicate_registry.read_text(encoding="utf-8"))
    payload["roots"].append(dict(payload["roots"][0]))
    duplicate_registry.write_text(json.dumps(payload), encoding="utf-8")

    invalid = onboard_repository(invalid_repo, apply=True)
    duplicate = onboard_repository(duplicate_repo, apply=True, root_id="test-root")

    assert invalid.outcome == "conflict"
    assert "updated" in str(invalid.message)
    assert duplicate.outcome == "conflict"
    assert "duplicate" in str(duplicate.message).lower()
    assert not (invalid_repo / "goals").exists()
    assert not (duplicate_repo / "outputs").exists()


def test_inactive_repo_registry_root_fails_closed() -> None:
    repo = make_repo("onboard-inactive-registry")
    registry = repo / "registry" / "REGISTRY.json"
    write_registry(registry, repo / "goals")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["roots"][0]["active"] = False
    registry.write_text(json.dumps(payload), encoding="utf-8")

    result = onboard_repository(repo, apply=True, root_id="test-root")

    assert result.outcome == "conflict"
    assert "inactive" in str(result.message)
    assert not (repo / "goals").exists()
    assert not (repo / "outputs").exists()


def test_custom_registry_location_uses_absolute_new_goal_root() -> None:
    repo = make_repo("onboard-custom-registry")
    registry = Path("config/lifecycle.json")

    result = onboard_repository(repo, apply=True, registry=registry)
    payload = json.loads((repo / registry).read_text(encoding="utf-8"))

    assert result.outcome == "registration_required"
    assert Path(payload["roots"][0]["goal_root"]) == (repo / "goals").resolve()


def test_registered_repo_verifies_derived_global_visibility() -> None:
    repo = make_repo("onboard-global-visible")
    write_goal(
        repo,
        "active",
        "ready-goal",
        "ready",
        evidence_status="complete",
        review_verdict="PASS",
    )
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    global_before = global_registry.read_bytes()

    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)

    assert result.outcome == "visibility_verified"
    assert result.exit_code == 0
    assert result.registered is True
    assert result.visibility_verified is True
    assert result.proposal is None
    assert result.resume["next_goal"] == "registered-repo/ready-goal"
    assert (repo / "outputs" / "global" / "STATE.json").is_file()
    assert global_registry.read_bytes() == global_before
    protected = [item for item in result.preserved_files if item["path"] == str(global_registry.resolve())]
    assert len(protected) == 1
    assert protected[0]["before_sha256"] == protected[0]["after_sha256"]


def test_global_registration_mismatch_fails_before_repo_write() -> None:
    repo = make_repo("onboard-global-conflict")
    global_registry = repo / "operator" / "REGISTRY.json"
    root = global_root(repo, "registered-repo", repo / "wrong" / "STATE.json")
    write_global_registry(global_registry, [root])

    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)

    assert result.outcome == "conflict"
    assert "state_path" in str(result.message)
    assert not (repo / "registry").exists()
    assert not (repo / "outputs").exists()


def test_inactive_duplicate_and_goal_root_mismatch_global_entries_fail_closed() -> None:
    inactive_repo = make_repo("onboard-global-inactive")
    inactive_registry = inactive_repo / "operator" / "REGISTRY.json"
    inactive_root = global_root(inactive_repo, "inactive", inactive_repo / "outputs" / "goal-lifecycle" / "STATE.json", active=False)
    write_global_registry(inactive_registry, [inactive_root])

    duplicate_repo = make_repo("onboard-global-duplicate")
    duplicate_registry = duplicate_repo / "operator" / "REGISTRY.json"
    duplicate_root = global_root(duplicate_repo, "duplicate-one", duplicate_repo / "outputs" / "goal-lifecycle" / "STATE.json")
    duplicate_root_two = dict(duplicate_root)
    duplicate_root_two["id"] = "duplicate-two"
    write_global_registry(duplicate_registry, [duplicate_root, duplicate_root_two])

    mismatch_repo = make_repo("onboard-global-goal-root-mismatch")
    mismatch_registry = mismatch_repo / "operator" / "REGISTRY.json"
    mismatch_root = global_root(mismatch_repo, "mismatch", mismatch_repo / "outputs" / "goal-lifecycle" / "STATE.json")
    mismatch_root["goal_root"] = (mismatch_repo / "other-goals").resolve().as_posix()
    write_global_registry(mismatch_registry, [mismatch_root])

    inactive = onboard_repository(inactive_repo, apply=True, global_registry_path=inactive_registry)
    duplicate = onboard_repository(duplicate_repo, apply=True, global_registry_path=duplicate_registry)
    mismatch = onboard_repository(mismatch_repo, apply=True, global_registry_path=mismatch_registry)

    assert inactive.outcome == duplicate.outcome == mismatch.outcome == "conflict"
    assert "inactive" in str(inactive.message)
    assert "duplicate" in str(duplicate.message).lower()
    assert "goal_root" in str(mismatch.message)
    assert not (inactive_repo / "goals").exists()
    assert not (duplicate_repo / "goals").exists()
    assert not (mismatch_repo / "goals").exists()


def test_registered_repo_reports_global_issues() -> None:
    repo = make_repo("onboard-global-issues")
    write_goal(repo, "active", "draft-goal", "draft")
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])

    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)

    assert result.outcome == "global_issues"
    assert result.exit_code == 2
    assert result.visibility_verified is True
    assert [item["status"] for item in result.stages if item["name"] == "aggregate"] == ["issues"]


def test_visibility_verification_reports_missing_canonical_keys() -> None:
    repo = make_repo("onboard-visibility-missing")
    write_goal(repo, "active", "visible-goal", "ready", evidence_status="complete", review_verdict="PASS")
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    first = onboard_repository(repo, apply=True, global_registry_path=global_registry)
    assert first.outcome == "visibility_verified"

    global_state = repo / "outputs" / "global" / "STATE.json"
    payload = json.loads(global_state.read_text(encoding="utf-8"))
    payload["entries"] = []
    global_state.write_text(json.dumps(payload), encoding="utf-8")
    preflight = onboard_module.build_preflight(
        repo.resolve(),
        onboard_module.slugify(repo.name),
        False,
        repo.name,
        repo.name,
        Path("goals"),
        Path("registry/REGISTRY.json"),
        Path("outputs/goal-lifecycle"),
        global_registry,
        Path("outputs/global"),
        Path("outputs/ONBOARDING.json"),
    )

    verified, message = onboard_module.verify_visibility(preflight)

    assert verified is False
    assert "registered-repo/visible-goal" in message


def test_registered_repo_distinguishes_aggregate_and_global_validation_failure(monkeypatch) -> None:
    def registered_repo(name: str) -> tuple[Path, Path]:
        repo = make_repo(name)
        state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
        global_registry = repo / "operator" / "REGISTRY.json"
        write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
        return repo, global_registry

    aggregate_repo, aggregate_registry = registered_repo("onboard-aggregate-failed")
    validation_repo, validation_registry = registered_repo("onboard-global-validation-failed")
    real_run_pipeline = onboard_module.run_pipeline

    def failed_summary(stage_name: str) -> RunSummary:
        stages = [
            StageResult("reconcile", "passed", None, 0, 0, None),
            StageResult("validate_local", "passed", None, 0, 0, None),
            StageResult("aggregate", "failed" if stage_name == "aggregate" else "passed", None, None, None, "boom" if stage_name == "aggregate" else None),
            StageResult("validate_global", "failed" if stage_name == "validate_global" else "skipped", None, None, None, "boom"),
        ]
        return RunSummary(version=1, status="failed", exit_code=1, stages=stages)

    monkeypatch.setattr(onboard_module, "run_pipeline", lambda *args, **kwargs: failed_summary("aggregate"))
    aggregate_result = onboard_repository(aggregate_repo, apply=True, global_registry_path=aggregate_registry)
    monkeypatch.setattr(onboard_module, "run_pipeline", lambda *args, **kwargs: failed_summary("validate_global"))
    validation_result = onboard_repository(validation_repo, apply=True, global_registry_path=validation_registry)
    monkeypatch.setattr(onboard_module, "run_pipeline", real_run_pipeline)

    assert aggregate_result.outcome == "global_failed"
    assert validation_result.outcome == "global_failed"
    assert aggregate_result.exit_code == validation_result.exit_code == 1
    assert [item["status"] for item in aggregate_result.stages if item["name"] == "visibility"] == ["skipped"]
    assert [item["status"] for item in validation_result.stages if item["name"] == "visibility"] == ["skipped"]


def test_registered_resume_context_is_less_than_half_of_identical_source_scenario() -> None:
    repo = make_repo("onboard-context")
    write_goal(repo, "active", "context-goal", "draft")
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    source_payload = b"".join(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        for path in sorted((repo / "goals").rglob("*.md"))
    )
    source_bytes = len(source_payload)

    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)
    resume_bytes = len(
        json.dumps(result.resume, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )

    assert resume_bytes <= source_bytes * 0.65
    assert source_bytes == 580
    assert hashlib.sha256(source_payload).hexdigest() == "ea70ff2d3940e272b1566fbf89a91a35babdb6ae341de533d14283920822903f"
    assert resume_bytes < 400
    assert len(result.resume["state_sha256"]) == 64
    assert result.registered is True
    assert result.resume["source"] == "global"
    assert result.metrics["semantic_model_calls"] == 0
    assert result.metrics["pipeline_invocations"] == 1


def test_dry_run_preserves_preexisting_local_and_global_inputs_byte_for_byte() -> None:
    repo = make_repo("onboard-dry-run-existing")
    write_goal(repo, "active", "existing-goal", "ready", evidence_status="complete", review_verdict="PASS")
    onboard_repository(repo, apply=True)
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    before = {path: path.read_bytes() for path in repo.rglob("*") if path.is_file()}

    result = onboard_repository(repo, global_registry_path=global_registry)
    after = {path: path.read_bytes() for path in repo.rglob("*") if path.is_file()}

    assert result.outcome == "dry_run_ready"
    assert result.registered is True
    assert after == before


def test_deferred_rollback_is_verification_only_and_deletes_nothing() -> None:
    repo = make_repo("onboard-rollback")
    result = onboard_repository(repo, apply=True)
    report = repo / "outputs" / "ONBOARDING.json"

    rollback = rollback_created_files(report)

    assert result.outcome == "registration_required"
    assert rollback["outcome"] == "rollback_review_required"
    assert rollback["deleted"] == []
    assert (repo / "registry" / "REGISTRY.json").exists()
    assert (repo / "outputs" / "goal-lifecycle" / "STATE.json").exists()
    assert (repo / "outputs" / "goal-lifecycle" / "STATE.md").exists()
    assert (repo / "goals" / "active").is_dir()
    assert (repo / "goals" / "completed").is_dir()
    assert report.exists()


def test_rollback_review_reports_hash_mismatch_without_deleting() -> None:
    repo = make_repo("onboard-rollback-mismatch")
    onboard_repository(repo, apply=True)
    registry = repo / "registry" / "REGISTRY.json"
    registry.write_text('{"user": "changed"}', encoding="utf-8")

    rollback = rollback_created_files(repo / "outputs" / "ONBOARDING.json")

    assert rollback["outcome"] == "rollback_review_required"
    assert rollback["deleted"] == []
    assert registry.exists()
    assert any(
        item["path"] == str(registry.resolve()) and item["reason"].startswith("hash mismatch")
        for item in rollback["retained"]
    )


def test_rollback_rejects_forged_user_goal_and_directory_entries() -> None:
    repo = make_repo("onboard-rollback-forged")
    keep = repo / "KEEP.txt"
    keep.write_text("keep me", encoding="utf-8")
    write_goal(repo, "active", "protected-goal", "draft")
    protected_goal = repo / "goals" / "active" / "protected-goal" / "CONTRACT.md"
    arbitrary_directory = repo / "empty-user-directory"
    arbitrary_directory.mkdir()
    onboard_repository(repo, apply=True)
    report = repo / "outputs" / "ONBOARDING.json"
    payload = json.loads(report.read_text(encoding="utf-8"))

    for path in (keep, protected_goal):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        payload["artifacts"].append(
            {
                "path": str(path.resolve()),
                "kind": "derived_local_state",
                "action": "created",
                "before_sha256": None,
                "after_sha256": digest,
                "rollback_eligible": True,
            }
        )
    payload["directories"].append({"path": str(arbitrary_directory.resolve()), "action": "created"})
    report.write_text(json.dumps(payload), encoding="utf-8")

    rollback = rollback_created_files(report)

    assert rollback["outcome"] == "rollback_review_required"
    assert rollback["deleted"] == []
    assert keep.read_text(encoding="utf-8") == "keep me"
    assert protected_goal.is_file()
    assert arbitrary_directory.is_dir()
    assert sum(item["reason"] == "artifact is outside the derived rollback write set" for item in rollback["retained"]) == 2


def test_schema_rejects_contradictory_rollback_eligible_artifact() -> None:
    repo = make_repo("onboard-rollback-schema")
    result = onboard_repository(repo, apply=True)
    payload = result.to_dict()
    payload["artifacts"].append(
        {
            "path": str((repo / "KEEP.txt").resolve()),
            "kind": "derived_local_state",
            "action": "updated",
            "before_sha256": "before",
            "after_sha256": "after",
            "rollback_eligible": True,
        }
    )

    with pytest.raises(ValueError, match="rollback_eligible|created"):
        onboard_module.validate_result(payload)


def test_schema_rejects_visibility_and_outcome_contradictions() -> None:
    repo = make_repo("onboard-schema-visibility-contradiction")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    state_path = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [global_root(repo, "registered-repo", state_path)])
    result = onboard_repository(repo, apply=True, global_registry_path=global_registry)

    resume_contradiction = result.to_dict()
    resume_contradiction["resume"]["visibility_verified"] = False
    with pytest.raises(ValueError, match="visibility_verified|True was expected"):
        onboard_module.validate_result(resume_contradiction)

    outcome_contradiction = result.to_dict()
    outcome_contradiction["outcome"] = "global_failed"
    outcome_contradiction["exit_code"] = 1
    with pytest.raises(ValueError, match="visibility_verified|False was expected"):
        onboard_module.validate_result(outcome_contradiction)


def test_schema_rejects_contradictory_registration_and_recovery_states() -> None:
    repo = make_repo("onboard-schema-registration-contradiction")
    result = onboard_repository(repo)

    authorization_contradiction = result.to_dict()
    authorization_contradiction["registration"]["authorized"] = True
    with pytest.raises(ValueError, match="authorized|False was expected"):
        onboard_module.validate_result(authorization_contradiction)

    recovery_contradiction = result.to_dict()
    recovery_contradiction["recovery"] = {
        "status": "recovery_required",
        "path": str((repo / "operator" / "REGISTRY.json").resolve()),
        "before_sha256": "a" * 64,
        "after_sha256": "b" * 64,
        "current_sha256": "c" * 64,
    }
    with pytest.raises(ValueError, match="recovery_required|const"):
        onboard_module.validate_result(recovery_contradiction)


def test_custom_path_artifacts_are_not_rollback_eligible() -> None:
    repo = make_repo("onboard-rollback-custom")
    result = onboard_repository(
        repo,
        apply=True,
        registry=Path("config/lifecycle.json"),
        local_out=Path("artifacts/lifecycle"),
        global_out=Path("artifacts/lifecycle/global"),
        report=Path("artifacts/lifecycle/ONBOARDING.json"),
    )

    assert result.outcome == "registration_required"
    assert all(item["rollback_eligible"] is False for item in result.artifacts)


def test_partial_state_write_returns_result_can_rollback_and_retry(monkeypatch) -> None:
    repo = make_repo("onboard-partial-write")
    real_atomic_write = reconcile_module.atomic_write_text
    failed_once = False

    def fail_state_markdown_once(path: Path, text: str) -> None:
        nonlocal failed_once
        if path.name == "STATE.md" and not failed_once:
            failed_once = True
            raise OSError("simulated markdown write failure")
        real_atomic_write(path, text)

    monkeypatch.setattr(reconcile_module, "atomic_write_text", fail_state_markdown_once)
    failed = onboard_repository(repo, apply=True)
    report = repo / "outputs" / "ONBOARDING.json"

    assert failed.outcome == "local_failed"
    assert failed.exit_code == 1
    assert failed.proposal is None
    assert report.exists()
    assert any(item["status"] == "failed" for item in failed.stages)

    monkeypatch.setattr(reconcile_module, "atomic_write_text", real_atomic_write)
    retried = onboard_repository(repo, apply=True)

    assert retried.outcome == "registration_required"


def test_report_write_failure_returns_documented_result(monkeypatch) -> None:
    repo = make_repo("onboard-report-failure")
    (repo / "goals" / "active").mkdir(parents=True)
    (repo / "goals" / "completed").mkdir()
    write_registry(repo / "registry" / "REGISTRY.json", repo / "goals")

    monkeypatch.setattr(
        onboard_module,
        "atomic_write_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("report denied")),
    )
    result = onboard_repository(repo, apply=True, root_id="test-root")

    assert result.outcome == "local_failed"
    assert result.exit_code == 1
    assert [item["status"] for item in result.stages if item["name"] == "report"] == ["failed"]
    assert not (repo / "outputs" / "ONBOARDING.json").exists()
    assert all(item["kind"] != "onboarding_report" for item in result.artifacts)


def test_report_write_failure_preserves_previous_canonical_bytes(monkeypatch) -> None:
    # Given: a previously validated canonical onboarding report.
    repo = make_repo("onboard-report-preserve")
    first = onboard_repository(repo, apply=True)
    report = repo / "outputs" / "ONBOARDING.json"
    before = report.read_bytes()
    assert first.outcome == "registration_required"

    # When: the next atomic publication fails before replacement.
    monkeypatch.setattr(
        onboard_module,
        "atomic_write_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace denied")),
    )
    failed = onboard_repository(repo, apply=True)

    # Then: the last valid canonical report remains byte-for-byte intact.
    assert failed.outcome == "local_failed"
    assert report.read_bytes() == before


def test_unexpected_internal_exception_returns_documented_result(monkeypatch) -> None:
    repo = make_repo("onboard-unexpected-exception")
    monkeypatch.setattr(
        onboard_module,
        "snapshot_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("unexpected audit failure")),
    )

    result = onboard_repository(repo, apply=True)

    assert result.outcome == "local_failed"
    assert result.exit_code == 1
    assert [item["name"] for item in result.stages] == ["internal"]
    onboard_module.validate_result(result.to_dict())


def test_cli_returns_machine_exit_code_and_json(capsys) -> None:
    repo = make_repo("onboard-cli")

    exit_code = main(["--repo", str(repo), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["outcome"] == "dry_run_ready"
    assert payload["mode"] == "check"
    assert payload["proposal"] is None


def test_cli_hash_guarded_rollback(capsys) -> None:
    repo = make_repo("onboard-cli-rollback")
    onboard_repository(repo, apply=True)
    report = repo / "outputs" / "ONBOARDING.json"

    exit_code = main(["--rollback-report", str(report), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["outcome"] == "rollback_review_required"
    assert payload["deleted"] == []


def test_register_requires_apply_and_absolute_global_registry_without_writes() -> None:
    repo = make_repo("onboard-register-gate")
    relative_registry = repo / "operator" / "REGISTRY.json"

    missing_apply = onboard_repository(
        repo,
        register=True,
        global_registry_path=relative_registry,
    )
    missing_registry = onboard_repository(repo, apply=True, register=True)

    assert missing_apply.outcome == "conflict"
    assert missing_registry.outcome == "conflict"
    assert "--apply" in str(missing_apply.message)
    assert "absolute" in str(missing_apply.message)
    assert "global registry" in str(missing_registry.message).lower()
    assert not (repo / "goals").exists()
    assert not (repo / "registry").exists()
    assert not relative_registry.exists()

    bound_repo = make_repo("onboard-register-plan-gate")
    bound_registry = bound_repo / "operator" / "REGISTRY.json"
    write_global_registry(bound_registry, [])
    no_plan = onboard_repository(
        bound_repo,
        apply=True,
        register=True,
        global_registry_path=bound_registry.resolve(),
    )
    plan = registration_plan(bound_repo, bound_registry)
    mismatched_plan = onboard_repository(
        bound_repo,
        apply=True,
        register=True,
        registration_plan_sha256=("0" if plan[0] != "0" else "1") + plan[1:],
        global_registry_path=bound_registry.resolve(),
    )

    assert no_plan.outcome == "conflict"
    assert "plan SHA" in str(no_plan.message)
    assert mismatched_plan.outcome == "conflict"
    assert "does not match" in str(mismatched_plan.message)
    assert not (bound_repo / "goals").exists()


def test_dry_run_discloses_registration_target_entry_and_exact_write_set() -> None:
    repo = make_repo("onboard-register-dry-run")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])

    result = onboard_repository(repo, global_registry_path=global_registry)

    assert result.outcome == "dry_run_ready"
    registration = result.registration
    assert registration["requested"] is False
    assert registration["authorized"] is False
    assert registration["global_registry_path"] == str(global_registry.resolve())
    assert registration["before_sha256"] == hashlib.sha256(global_registry.read_bytes()).hexdigest()
    assert registration["proposed_entry"]["repo_root"] == str(repo.resolve())
    assert str((repo / "registry" / "REGISTRY.json").resolve()) in registration["planned_write_set"]
    assert str(global_registry.resolve()) in registration["planned_write_set"]
    assert str((repo / "outputs" / "global" / "STATE.json").resolve()) in registration["planned_write_set"]
    assert len(registration["plan_sha256"]) == 64
    onboard_module.validate_result(result.to_dict())


def test_authorized_register_publishes_once_and_verifies_global_visibility() -> None:
    repo = make_repo("onboard-register-success")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    source_paths = sorted((repo / "goals").rglob("*.md"))
    source_before = {path: path.read_bytes() for path in source_paths}
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)

    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    payload = json.loads(global_registry.read_text(encoding="utf-8"))
    assert result.outcome == "visibility_verified"
    assert result.exit_code == 0
    assert result.registered is True
    assert result.visibility_verified is True
    assert result.registration["requested"] is True
    assert result.registration["authorized"] is True
    assert result.registration["status"] == "published"
    assert str((global_registry.parent / ".REGISTRY.json.agentgoals.lock").resolve()) in result.registration["planned_write_set"]
    assert len(payload["roots"]) == 1
    assert Path(payload["roots"][0]["repo_root"]) == repo.resolve()
    assert global_registry.read_bytes() != before
    assert {path: path.read_bytes() for path in source_paths} == source_before
    global_preserved = next(item for item in result.preserved_files if item["path"] == str(global_registry.resolve()))
    assert global_preserved["before_sha256"] == hashlib.sha256(before).hexdigest()
    assert global_preserved["after_sha256"] == hashlib.sha256(global_registry.read_bytes()).hexdigest()
    validate_json_file(repo / "outputs" / "ONBOARDING.json", Path("schemas/onboarding-result.schema.json"))


def test_authorized_register_supports_spaces_and_unicode_paths() -> None:
    repo = make_repo("onboard register 空間")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator config" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)

    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "visibility_verified"
    assert result.registration["global_registry_path"] == str(global_registry.resolve())
    assert Path(result.registration["proposed_entry"]["repo_root"]) == repo.resolve()


def test_legacy_apply_with_unregistered_global_registry_remains_proposal_only() -> None:
    repo = make_repo("onboard-register-legacy-global")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)

    result = onboard_repository(repo, apply=True, global_registry_path=global_registry.resolve())

    assert result.outcome == "registration_required"
    assert result.registered is False
    assert result.registration["requested"] is False
    assert global_registry.read_bytes() == before


def test_authorized_register_candidate_failure_preserves_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-candidate-failure")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)

    monkeypatch.setattr(
        onboard_module,
        "aggregate",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("candidate aggregate rejected")),
    )

    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "global_failed"
    assert result.exit_code == 1
    assert global_registry.read_bytes() == before
    assert result.registration["status"] == "not_published"


def test_candidate_visibility_failure_preserves_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-visibility-failure")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)

    monkeypatch.setattr(onboard_module, "verify_visibility", lambda *args, **kwargs: (False, "missing target key"))
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "global_failed"
    assert result.registration["status"] == "not_published"
    assert global_registry.read_bytes() == before


def test_authorized_register_is_idempotent_for_existing_registration() -> None:
    repo = make_repo("onboard-register-idempotent")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    first_plan_sha256 = registration_plan(repo, global_registry)

    first = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=first_plan_sha256,
        global_registry_path=global_registry.resolve(),
    )
    before_second = global_registry.read_bytes()
    second_plan_sha256 = registration_plan(repo, global_registry)
    second = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=second_plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert first.outcome == "visibility_verified"
    assert second.outcome == "visibility_verified"
    assert second.registration["status"] == "already_registered"
    assert second.proposal is None
    assert global_registry.read_bytes() == before_second


def test_concurrent_global_registry_mutation_is_not_overwritten(monkeypatch) -> None:
    repo = make_repo("onboard-register-concurrent")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)
    real_publish = onboard_module.publish_global_registration

    def mutate_then_publish(*args, **kwargs):
        path = args[0]
        path.write_bytes(path.read_bytes() + b"\n")
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(onboard_module, "publish_global_registration", mutate_then_publish)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "conflict"
    assert result.registration["status"] == "not_published"
    assert global_registry.read_bytes().endswith(b"\n")
    assert "changed" in str(result.message).lower() or any(
        item["name"] == "registration" and item["status"] == "failed" for item in result.stages
    )


def test_atomic_global_replace_failure_preserves_previous_bytes(monkeypatch) -> None:
    repo = make_repo("onboard-register-replace-failure")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)
    real_replace = onboard_module.atomic_replace_bytes_if_hash

    def fail_global_replace(path, data, expected_sha256):
        if path.resolve() == global_registry.resolve():
            raise OSError("replace denied")
        return real_replace(path, data, expected_sha256)

    monkeypatch.setattr(onboard_module, "atomic_replace_bytes_if_hash", fail_global_replace)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "global_failed"
    assert global_registry.read_bytes() == before
    assert result.registration["status"] == "not_published"


def test_post_commit_atomic_failure_restores_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-post-commit-restore")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    plan_sha256 = registration_plan(repo, global_registry)
    real_replace = onboard_module.atomic_replace_bytes_if_hash
    calls = 0

    def fail_after_replace(path, data, expected_sha256):
        nonlocal calls
        result = real_replace(path, data, expected_sha256)
        calls += 1
        if path.resolve() == global_registry.resolve() and calls == 1:
            raise OSError("readback interrupted")
        return result

    monkeypatch.setattr(onboard_module, "atomic_replace_bytes_if_hash", fail_after_replace)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "global_failed"
    assert result.recovery is not None
    assert result.recovery["status"] == "restored"
    assert global_registry.read_bytes() == before
    onboard_module.validate_result(result.to_dict())


def test_post_commit_atomic_failure_preserves_third_party_change(monkeypatch) -> None:
    repo = make_repo("onboard-register-post-commit-third-party")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)
    real_replace = onboard_module.atomic_replace_bytes_if_hash
    calls = 0

    def fail_after_third_party_change(path, data, expected_sha256):
        nonlocal calls
        result = real_replace(path, data, expected_sha256)
        calls += 1
        if path.resolve() == global_registry.resolve() and calls == 1:
            path.write_bytes(path.read_bytes() + b" third-party")
            raise OSError("readback interrupted")
        return result

    monkeypatch.setattr(onboard_module, "atomic_replace_bytes_if_hash", fail_after_third_party_change)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "recovery_required"
    assert result.recovery is not None
    assert result.recovery["status"] == "recovery_required"
    assert global_registry.read_bytes().endswith(b" third-party")
    onboard_module.validate_result(result.to_dict())


def test_post_commit_report_failure_restores_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-report-recovery")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)
    before = global_registry.read_bytes()
    real_write = onboard_module.atomic_write_json

    def fail_report(path, payload):
        if path.name == "ONBOARDING.json":
            raise OSError("report denied")
        return real_write(path, payload)

    monkeypatch.setattr(onboard_module, "atomic_write_json", fail_report)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "local_failed"
    assert result.registration["status"] == "restored"
    assert result.recovery is not None
    assert result.recovery["status"] == "restored"
    assert global_registry.read_bytes() == before
    onboard_module.validate_result(result.to_dict())


def test_post_commit_recovery_requires_manual_action_after_third_party_change(monkeypatch) -> None:
    repo = make_repo("onboard-register-recovery-required")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)
    real_write = onboard_module.atomic_write_json
    real_restore = onboard_module.guarded_restore_global

    def fail_report(path, payload):
        if path.name == "ONBOARDING.json":
            raise OSError("report denied")
        return real_write(path, payload)

    def mutate_then_restore(publication):
        publication.path.write_bytes(publication.path.read_bytes() + b" third-party")
        return real_restore(publication)

    monkeypatch.setattr(onboard_module, "atomic_write_json", fail_report)
    monkeypatch.setattr(onboard_module, "guarded_restore_global", mutate_then_restore)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "recovery_required"
    assert result.registration["status"] == "recovery_required"
    assert result.recovery is not None
    assert result.recovery["status"] == "recovery_required"
    assert global_registry.read_bytes().endswith(b" third-party")
    onboard_module.validate_result(result.to_dict())


def test_post_commit_resume_failure_restores_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-resume-recovery")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    plan_sha256 = registration_plan(repo, global_registry)
    before = global_registry.read_bytes()

    monkeypatch.setattr(
        onboard_module,
        "build_resume",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("resume interrupted")),
    )
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "local_failed"
    assert result.registration["status"] == "restored"
    assert result.recovery is not None
    assert result.recovery["status"] == "restored"
    assert global_registry.read_bytes() == before
    onboard_module.validate_result(result.to_dict())


def test_post_commit_source_integrity_failure_restores_global_registry(monkeypatch) -> None:
    repo = make_repo("onboard-register-source-integrity-recovery")
    write_goal(repo, "active", "ready-goal", "ready", evidence_status="complete", review_verdict="PASS")
    global_registry = repo / "operator" / "REGISTRY.json"
    write_global_registry(global_registry, [])
    before = global_registry.read_bytes()
    source = repo / "goals" / "active" / "ready-goal" / "CONTRACT.md"
    real_resume = onboard_module.build_resume

    def mutate_source_after_publication(paths, visibility_verified):
        source.write_text(source.read_text(encoding="utf-8") + "\nexternal mutation\n", encoding="utf-8")
        return real_resume(paths, visibility_verified)

    plan_sha256 = registration_plan(repo, global_registry)
    monkeypatch.setattr(onboard_module, "build_resume", mutate_source_after_publication)
    result = onboard_repository(
        repo,
        apply=True,
        register=True,
        registration_plan_sha256=plan_sha256,
        global_registry_path=global_registry.resolve(),
    )

    assert result.outcome == "conflict"
    assert result.registration["status"] == "restored"
    assert result.recovery is not None
    assert result.recovery["status"] == "restored"
    assert global_registry.read_bytes() == before
    assert "external mutation" in source.read_text(encoding="utf-8")
    onboard_module.validate_result(result.to_dict())
