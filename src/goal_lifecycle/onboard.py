from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from jsonschema import Draft202012Validator

from goal_lifecycle.aggregate import GlobalRegistryRoot, load_global_registry
from goal_lifecycle.io import atomic_write_text
from goal_lifecycle.run import RunSummary, run_pipeline
from goal_lifecycle.validate import SCHEMA_DIR, load_json, validate_json_file, validate_registry, validate_state


RESULT_SCHEMA = SCHEMA_DIR / "onboarding-result.schema.json"


@dataclass(frozen=True)
class OnboardingResult:
    version: int
    outcome: str
    exit_code: int
    mode: str
    target_repo: str
    root_id: str
    registered: bool
    visibility_verified: bool
    stages: list[dict[str, Any]]
    proposal: dict[str, Any] | None
    resume: dict[str, Any]
    metrics: dict[str, int]
    planned_actions: list[str]
    artifacts: list[dict[str, Any]]
    directories: list[dict[str, str]]
    preserved_files: list[dict[str, str]]
    message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OnboardingPaths:
    repo: Path
    goal_root: Path
    registry: Path
    local_out: Path
    global_out: Path
    report: Path


@dataclass(frozen=True)
class Preflight:
    paths: OnboardingPaths
    root_id: str
    label: str
    project: str
    registry_payload: dict[str, Any]
    registry_changed: bool
    planned_actions: list[str]
    global_root: GlobalRegistryRoot | None
    proposal: dict[str, Any] | None


def onboard_repository(
    repo_path: Path,
    *,
    apply: bool = False,
    root_id: str | None = None,
    label: str | None = None,
    project: str | None = None,
    goal_root: Path = Path("goals"),
    registry: Path = Path("registry/REGISTRY.json"),
    local_out: Path = Path("outputs/goal-lifecycle"),
    global_registry_path: Path | None = None,
    global_out: Path = Path("outputs/goal-lifecycle/global"),
    report: Path = Path("outputs/goal-lifecycle/ONBOARDING.json"),
) -> OnboardingResult:
    try:
        return _onboard_repository(
            repo_path,
            apply=apply,
            root_id=root_id,
            label=label,
            project=project,
            goal_root=goal_root,
            registry=registry,
            local_out=local_out,
            global_registry_path=global_registry_path,
            global_out=global_out,
            report=report,
        )
    except Exception as exc:
        resolved_repo = repo_path.resolve()
        resolved_root_id = root_id or slugify(resolved_repo.name)
        return unexpected_result(resolved_repo, resolved_root_id, "apply" if apply else "check", exc)


def _onboard_repository(
    repo_path: Path,
    *,
    apply: bool = False,
    root_id: str | None = None,
    label: str | None = None,
    project: str | None = None,
    goal_root: Path = Path("goals"),
    registry: Path = Path("registry/REGISTRY.json"),
    local_out: Path = Path("outputs/goal-lifecycle"),
    global_registry_path: Path | None = None,
    global_out: Path = Path("outputs/goal-lifecycle/global"),
    report: Path = Path("outputs/goal-lifecycle/ONBOARDING.json"),
) -> OnboardingResult:
    mode = "apply" if apply else "check"
    resolved_repo = repo_path.resolve()
    resolved_root_id = root_id or slugify(resolved_repo.name)

    try:
        preflight = build_preflight(
            resolved_repo,
            resolved_root_id,
            root_id is not None,
            label or resolved_repo.name,
            project or resolved_repo.name,
            goal_root,
            registry,
            local_out,
            global_registry_path,
            global_out,
            report,
        )
    except Exception as exc:
        return conflict_result(resolved_repo, resolved_root_id, mode, exc)

    if not apply:
        dry_run_actions = list(preflight.planned_actions)
        if preflight.global_root is None:
            dry_run_actions.append("emit_global_registration_proposal_after_validation")
        return OnboardingResult(
            version=1,
            outcome="dry_run_ready",
            exit_code=0,
            mode=mode,
            target_repo=str(preflight.paths.repo),
            root_id=preflight.root_id,
            registered=preflight.global_root is not None,
            visibility_verified=False,
            stages=[stage("preflight", "passed"), stage("scaffold", "skipped", "dry-run")],
            proposal=None,
            resume={},
            metrics={"resume_context_bytes": 0, "semantic_model_calls": 0, "pipeline_invocations": 0},
            planned_actions=dry_run_actions,
            artifacts=[],
            directories=[],
            preserved_files=[],
            message="Dry-run completed without writes.",
        )

    source_before = snapshot_goal_sources(preflight.paths.goal_root)
    if global_registry_path and global_registry_path.resolve().is_file():
        protected = global_registry_path.resolve()
        source_before[protected] = hash_file(protected)
    artifact_before = snapshot_artifacts(preflight.paths)
    directory_before = snapshot_directories(preflight.paths)
    runtime_metrics = {"semantic_model_calls": 0, "pipeline_invocations": 0}
    stages = [stage("preflight", "passed")]

    try:
        apply_scaffold(preflight)
        stages.append(stage("scaffold", "passed"))
    except Exception as exc:
        stages.append(stage("scaffold", "failed", f"{type(exc).__name__}: {exc}"))
        return finish_apply(
            preflight,
            stages,
            "local_failed",
            1,
            False,
            {},
            source_before,
            artifact_before,
            directory_before,
            runtime_metrics,
            f"Scaffolding failed: {exc}",
        )

    try:
        runtime_metrics["pipeline_invocations"] += 1
        run_summary = run_pipeline(
            preflight.paths.registry,
            preflight.paths.local_out,
            global_registry_path=global_registry_path if preflight.global_root else None,
            global_out_dir=preflight.paths.global_out if preflight.global_root else None,
        )
    except Exception as exc:
        stages.append(stage("pipeline", "failed", f"{type(exc).__name__}: {exc}"))
        return finish_apply(
            preflight,
            stages,
            "local_failed",
            1,
            False,
            {},
            source_before,
            artifact_before,
            directory_before,
            runtime_metrics,
            f"Pipeline failed unexpectedly: {exc}",
        )
    stages.extend(asdict(item) for item in run_summary.stages)

    visibility_verified = False
    if preflight.global_root and not global_pipeline_failed(run_summary):
        try:
            visibility_verified, visibility_message = verify_visibility(preflight)
            stages.append(
                stage(
                    "visibility",
                    "passed" if visibility_verified else "failed",
                    visibility_message,
                )
            )
        except Exception as exc:
            stages.append(stage("visibility", "failed", f"{type(exc).__name__}: {exc}"))
    else:
        reason = "registration required" if preflight.global_root is None else "global pipeline failed"
        stages.append(stage("visibility", "skipped", reason))

    outcome, exit_code, message = choose_outcome(
        run_summary,
        preflight.global_root is not None,
        visibility_verified,
    )
    try:
        resume = build_resume(preflight.paths, visibility_verified)
    except Exception as exc:
        stages.append(stage("resume", "failed", f"{type(exc).__name__}: {exc}"))
        outcome = "global_failed" if preflight.global_root else "local_failed"
        exit_code = 1
        visibility_verified = False
        resume = {}
        message = f"Resume context generation failed: {exc}"
    return finish_apply(
        preflight,
        stages,
        outcome,
        exit_code,
        visibility_verified,
        resume,
        source_before,
        artifact_before,
        directory_before,
        runtime_metrics,
        message,
    )


def build_preflight(
    repo: Path,
    root_id: str,
    root_id_explicit: bool,
    label: str,
    project: str,
    goal_root: Path,
    registry: Path,
    local_out: Path,
    global_registry_path: Path | None,
    global_out: Path,
    report: Path,
) -> Preflight:
    if not repo.is_dir() or not (repo / ".git").exists():
        raise ValueError(f"Target must be an existing Git repository: {repo}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", root_id):
        raise ValueError(f"root_id must be kebab-case: {root_id}")

    paths = OnboardingPaths(
        repo=repo,
        goal_root=resolve_inside(repo, goal_root, "goal_root"),
        registry=resolve_inside(repo, registry, "registry"),
        local_out=resolve_inside(repo, local_out, "local_out"),
        global_out=resolve_inside(repo, global_out, "global_out"),
        report=resolve_inside(repo, report, "report"),
    )
    validate_path_boundaries(paths, global_registry_path)
    validate_output_collisions(paths)
    (
        registry_payload,
        registry_changed,
        planned_actions,
        effective_root_id,
        effective_label,
        effective_project,
    ) = prepare_repo_registry(
        paths,
        root_id,
        root_id_explicit,
        label,
        project,
    )
    global_root, proposal = inspect_global_registration(
        paths,
        effective_root_id,
        effective_label,
        effective_project,
        global_registry_path,
    )
    return Preflight(
        paths=paths,
        root_id=effective_root_id,
        label=effective_label,
        project=effective_project,
        registry_payload=registry_payload,
        registry_changed=registry_changed,
        planned_actions=planned_actions,
        global_root=global_root,
        proposal=proposal,
    )


def prepare_repo_registry(
    paths: OnboardingPaths,
    root_id: str,
    root_id_explicit: bool,
    label: str,
    project: str,
) -> tuple[dict[str, Any], bool, list[str], str, str, str]:
    planned_actions = []
    if not (paths.goal_root / "active").is_dir() or not (paths.goal_root / "completed").is_dir():
        planned_actions.append("create_goal_directories")

    if paths.registry.exists():
        validate_registry(paths.registry)
        payload = load_json(paths.registry)
    else:
        payload = {"version": 1, "updated": today(), "roots": []}

    matching_id = [item for item in payload["roots"] if item["id"] == root_id]
    matching_path = [
        item
        for item in payload["roots"]
        if resolve_registry_goal_root(paths.registry, item["goal_root"]) == paths.goal_root
    ]
    if matching_path and not matching_id and not root_id_explicit:
        root_id = matching_path[0]["id"]
        matching_id = matching_path
    if matching_id and matching_id[0] not in matching_path:
        raise ValueError(f"Repo registry id collision for {root_id}")
    if matching_path and matching_path[0]["id"] != root_id:
        raise ValueError(f"Goal root is already registered as {matching_path[0]['id']}")
    if len(matching_id) > 1 or len(matching_path) > 1:
        raise ValueError("Repo registry contains duplicate onboarding roots")
    if matching_path and not matching_path[0]["active"]:
        raise ValueError(f"Repo registry entry is inactive: {matching_path[0]['id']}")

    effective_label = matching_path[0]["label"] if matching_path else label
    effective_project = matching_path[0]["project"] if matching_path else project

    changed = False
    if not matching_id:
        payload["roots"].append(
            {
                "id": root_id,
                "label": label,
                "goal_root": str(paths.goal_root),
                "scope": "repo",
                "project": project,
                "active": True,
                "added": today(),
                "last_seen": None,
            }
        )
        payload["updated"] = today()
        changed = True
        planned_actions.append("create_repo_registry" if not paths.registry.exists() else "update_repo_registry")
    return payload, changed, planned_actions, root_id, effective_label, effective_project


def inspect_global_registration(
    paths: OnboardingPaths,
    root_id: str,
    label: str,
    project: str,
    global_registry_path: Path | None,
) -> tuple[GlobalRegistryRoot | None, dict[str, Any] | None]:
    proposal = global_registry_proposal(paths, root_id, label, project)
    if global_registry_path is None:
        return None, proposal
    global_registry_path = global_registry_path.resolve()
    if not global_registry_path.is_file():
        raise ValueError(f"Global registry not found: {global_registry_path}")
    roots = load_global_registry(global_registry_path)
    same_repo = [root for root in roots if root.repo_root.resolve() == paths.repo]
    if len(same_repo) > 1:
        raise ValueError("Global registry contains duplicate entries for target repository")
    if not same_repo:
        if any(root.id == root_id for root in roots):
            raise ValueError(f"Global registry id collision for {root_id}")
        return None, proposal

    root = same_repo[0]
    if not root.active:
        raise ValueError(f"Global registry entry is inactive: {root.id}")
    if root.goal_root.resolve() != paths.goal_root:
        raise ValueError(f"Global registry goal_root mismatch: {root.goal_root}")
    expected_state = paths.local_out / "STATE.json"
    if root.state_path.resolve() != expected_state:
        raise ValueError(f"Global registry state_path mismatch: {root.state_path}")
    return root, None


def apply_scaffold(preflight: Preflight) -> None:
    (preflight.paths.goal_root / "active").mkdir(parents=True, exist_ok=True)
    (preflight.paths.goal_root / "completed").mkdir(parents=True, exist_ok=True)
    if preflight.registry_changed:
        atomic_write_json(preflight.paths.registry, preflight.registry_payload)


def verify_visibility(preflight: Preflight) -> tuple[bool, str]:
    assert preflight.global_root is not None
    local_payload = load_json(preflight.paths.local_out / "STATE.json")
    global_payload = load_json(preflight.paths.global_out / "STATE.json")
    expected = {
        f"{preflight.global_root.id}/{item['id']}"
        for item in local_payload.get("entries", [])
    }
    observed = {item["goal_key"] for item in global_payload.get("entries", [])}
    missing = sorted(expected - observed)
    if missing:
        return False, f"Derived global aggregate is missing canonical Goal keys: {missing}"
    return True, f"Verified {len(expected)} canonical Goal keys in derived global aggregate."


def build_resume(paths: OnboardingPaths, visibility_verified: bool) -> dict[str, Any]:
    state_path = paths.global_out / "STATE.json" if visibility_verified else paths.local_out / "STATE.json"
    if not state_path.exists():
        return {}
    payload = load_json(state_path)
    queue = payload.get("queue", {})
    return {
        "source": "global" if visibility_verified else "local",
        "visibility_verified": visibility_verified,
        "next_goal": queue.get("next_goal"),
        "next_planned_goal": queue.get("next_planned_goal"),
        "open_count": queue.get("open_count", 0),
        "runnable_count": queue.get("runnable_count", 0),
        "invalid_count": queue.get("invalid_count", 0),
    }


def choose_outcome(
    summary: RunSummary,
    registered: bool,
    visibility_verified: bool,
) -> tuple[str, int, str]:
    by_name = {item.name: item for item in summary.stages}
    if any(by_name[name].status == "failed" for name in ("reconcile", "validate_local")):
        return "local_failed", 1, "Local reconciliation or validation failed."
    if not registered:
        return "registration_required", 2, "Local onboarding passed; global registration is required."
    if any(by_name[name].status == "failed" for name in ("aggregate", "validate_global")):
        return "global_failed", 1, "Derived global aggregation or validation failed."
    if not visibility_verified:
        return "global_failed", 1, "Derived global visibility verification failed."
    if any(item.status == "issues" for item in summary.stages):
        return "global_issues", 2, "Visibility was verified, but lifecycle issues remain."
    return "visibility_verified", 0, "Local onboarding and derived global visibility verification passed."


def finish_apply(
    preflight: Preflight,
    stages: list[dict[str, Any]],
    outcome: str,
    exit_code: int,
    visibility_verified: bool,
    resume: dict[str, Any],
    source_before: dict[Path, str],
    artifact_before: dict[Path, str | None],
    directory_before: dict[Path, bool],
    runtime_metrics: dict[str, int],
    message: str,
) -> OnboardingResult:
    preserved_files = compare_preserved(source_before)
    changed_preserved = [item for item in preserved_files if item["before_sha256"] != item["after_sha256"]]
    if changed_preserved:
        stages.append(stage("integrity", "failed", "Pre-existing protected-file hashes changed."))
        outcome = "conflict"
        exit_code = 1
        visibility_verified = False
        message = "Pre-existing Goal source or protected registry files changed during onboarding."
    else:
        stages.append(stage("integrity", "passed"))

    artifacts = audit_artifacts(preflight.paths, artifact_before)
    directories = audit_directories(directory_before)
    metrics = {
        "resume_context_bytes": len(json.dumps(resume, ensure_ascii=False, sort_keys=True).encode("utf-8")),
        "semantic_model_calls": runtime_metrics["semantic_model_calls"],
        "pipeline_invocations": runtime_metrics["pipeline_invocations"],
    }
    validated_proposal = (
        preflight.proposal
        if any(item["name"] == "validate_local" and item["status"] == "passed" for item in stages)
        else None
    )
    stages.append(stage("report", "passed"))
    result = OnboardingResult(
        version=1,
        outcome=outcome,
        exit_code=exit_code,
        mode="apply",
        target_repo=str(preflight.paths.repo),
        root_id=preflight.root_id,
        registered=preflight.global_root is not None,
        visibility_verified=visibility_verified,
        stages=stages,
        proposal=validated_proposal,
        resume=resume,
        metrics=metrics,
        planned_actions=preflight.planned_actions,
        artifacts=artifacts,
        directories=directories,
        preserved_files=preserved_files,
        message=message,
    )
    payload = result.to_dict()
    try:
        validate_result(payload)
        atomic_write_json(preflight.paths.report, payload)
        return result
    except Exception as exc:
        failed_stages = stages[:-1] + [stage("report", "failed", f"{type(exc).__name__}: {exc}")]
        failed_artifacts = [item for item in artifacts if item["kind"] != "onboarding_report"]
        if preflight.paths.report.is_file():
            report_hash = hash_file(preflight.paths.report)
            failed_artifacts.append(
                {
                    "path": str(preflight.paths.report),
                    "kind": "onboarding_report",
                    "action": "unchanged",
                    "before_sha256": report_hash,
                    "after_sha256": report_hash,
                    "rollback_eligible": False,
                }
            )
        return OnboardingResult(
            version=1,
            outcome="local_failed",
            exit_code=1,
            mode="apply",
            target_repo=str(preflight.paths.repo),
            root_id=preflight.root_id,
            registered=preflight.global_root is not None,
            visibility_verified=False,
            stages=failed_stages,
            proposal=validated_proposal,
            resume=resume,
            metrics=metrics,
            planned_actions=preflight.planned_actions,
            artifacts=failed_artifacts,
            directories=directories,
            preserved_files=preserved_files,
            message=f"Onboarding report failed: {exc}",
        )


def conflict_result(repo: Path, root_id: str, mode: str, exc: Exception) -> OnboardingResult:
    result = OnboardingResult(
        version=1,
        outcome="conflict",
        exit_code=1,
        mode=mode,
        target_repo=str(repo),
        root_id=slugify(root_id),
        registered=False,
        visibility_verified=False,
        stages=[stage("preflight", "failed", f"{type(exc).__name__}: {exc}")],
        proposal=None,
        resume={},
        metrics={"resume_context_bytes": 0, "semantic_model_calls": 0, "pipeline_invocations": 0},
        planned_actions=[],
        artifacts=[],
        directories=[],
        preserved_files=[],
        message=str(exc),
    )
    validate_result(result.to_dict())
    return result


def unexpected_result(repo: Path, root_id: str, mode: str, exc: Exception) -> OnboardingResult:
    outcome = "local_failed" if mode == "apply" else "conflict"
    result = OnboardingResult(
        version=1,
        outcome=outcome,
        exit_code=1,
        mode=mode,
        target_repo=str(repo),
        root_id=slugify(root_id),
        registered=False,
        visibility_verified=False,
        stages=[stage("internal", "failed", f"{type(exc).__name__}: {exc}")],
        proposal=None,
        resume={},
        metrics={"resume_context_bytes": 0, "semantic_model_calls": 0, "pipeline_invocations": 0},
        planned_actions=[],
        artifacts=[],
        directories=[],
        preserved_files=[],
        message=f"Unexpected onboarding failure: {exc}",
    )
    validate_result(result.to_dict())
    return result


def validate_path_boundaries(paths: OnboardingPaths, global_registry_path: Path | None) -> None:
    if paths.goal_root == paths.repo:
        raise ValueError("goal_root must not be the repository root")
    if paths.registry.suffix.lower() != ".json" or paths.report.suffix.lower() != ".json":
        raise ValueError("registry and report targets must be JSON files")
    if paths.local_out.exists() and not paths.local_out.is_dir():
        raise ValueError(f"local_out is not a directory: {paths.local_out}")
    if paths.global_out.exists() and not paths.global_out.is_dir():
        raise ValueError(f"global_out is not a directory: {paths.global_out}")
    if paths.local_out == paths.global_out:
        raise ValueError("local_out and global_out must be distinct")

    write_files = {
        "registry": paths.registry,
        "report": paths.report,
        "local_state_json": paths.local_out / "STATE.json",
        "local_state_markdown": paths.local_out / "STATE.md",
        "global_state_json": paths.global_out / "STATE.json",
        "global_state_markdown": paths.global_out / "STATE.md",
    }
    items = list(write_files.items())
    for index, (left_name, left_path) in enumerate(items):
        if is_within(left_path, paths.goal_root):
            raise ValueError(f"{left_name} must not overlap Goal source files")
        for right_name, right_path in items[index + 1 :]:
            if paths_alias(left_path, right_path):
                raise ValueError(f"Write targets alias: {left_name}={left_path}, {right_name}={right_path}")

    if is_within(paths.registry, paths.local_out) or is_within(paths.registry, paths.global_out):
        raise ValueError("Repo registry must stay outside derived output directories")
    if is_within(paths.local_out, paths.registry) or is_within(paths.global_out, paths.registry):
        raise ValueError("Derived output directories must not descend from the repo registry file path")
    if not is_within(paths.report, paths.local_out):
        raise ValueError("report must be under local_out")
    if is_within(paths.global_out, paths.report):
        raise ValueError("global_out must not descend from the report file path")

    if global_registry_path:
        protected = global_registry_path.resolve()
        for name, write_path in write_files.items():
            if paths_alias(protected, write_path):
                raise ValueError(f"Global registry aliases write target {name}: {protected}")
        if is_within(protected, paths.local_out) or is_within(protected, paths.global_out):
            raise ValueError("Global registry must stay outside derived output directories")


def validate_output_collisions(paths: OnboardingPaths) -> None:
    local_state = paths.local_out / "STATE.json"
    global_state = paths.global_out / "STATE.json"
    for path, validator in (
        (local_state, validate_state),
        (global_state, validate_state),
        (paths.report, lambda item: validate_json_file(item, RESULT_SCHEMA)),
    ):
        if path.exists() and not path.is_file():
            raise ValueError(f"Derived output target is not a file: {path}")
        if path.is_file():
            try:
                validator(path)
            except Exception as exc:
                raise ValueError(f"Pre-existing derived output is not recognized: {path}: {exc}") from exc
    for markdown, state_path in (
        (paths.local_out / "STATE.md", local_state),
        (paths.global_out / "STATE.md", global_state),
    ):
        if markdown.exists() and not markdown.is_file():
            raise ValueError(f"Derived output target is not a file: {markdown}")
        if markdown.is_file() and not state_path.is_file():
            raise ValueError(f"Pre-existing STATE.md has no validated STATE.json peer: {markdown}")


def resolve_inside(repo: Path, value: Path, field_name: str) -> Path:
    resolved = value.resolve() if value.is_absolute() else (repo / value).resolve()
    if not is_within(resolved, repo):
        raise ValueError(f"{field_name} must stay inside target repository: {resolved}")
    return resolved


def resolve_registry_goal_root(registry: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (registry.parent.parent / path).resolve()


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def paths_alias(left: Path, right: Path) -> bool:
    return is_within(left, right) or is_within(right, left)


def snapshot_goal_sources(goal_root: Path) -> dict[Path, str]:
    if not goal_root.exists():
        return {}
    return {
        path.resolve(): hash_file(path)
        for path in sorted(goal_root.rglob("*"))
        if path.is_file()
    }


def compare_preserved(before: dict[Path, str]) -> list[dict[str, str]]:
    return [
        {
            "path": str(path),
            "before_sha256": digest,
            "after_sha256": hash_file(path) if path.is_file() else "missing",
        }
        for path, digest in sorted(before.items(), key=lambda item: str(item[0]))
    ]


def snapshot_artifacts(paths: OnboardingPaths) -> dict[Path, str | None]:
    candidates = [
        paths.registry,
        paths.local_out / "STATE.json",
        paths.local_out / "STATE.md",
        paths.global_out / "STATE.json",
        paths.global_out / "STATE.md",
        paths.report,
    ]
    return {path: hash_file(path) if path.is_file() else None for path in candidates}


def audit_artifacts(paths: OnboardingPaths, before: dict[Path, str | None]) -> list[dict[str, Any]]:
    artifacts = []
    allowed_rollback = default_rollback_write_set(paths.repo)
    for path, before_hash in before.items():
        if path == paths.report or not path.is_file():
            continue
        after_hash = hash_file(path)
        artifacts.append(
            {
                "path": str(path),
                "kind": artifact_kind(path, paths),
                "action": "created" if before_hash is None else ("updated" if before_hash != after_hash else "unchanged"),
                "before_sha256": before_hash,
                "after_sha256": after_hash,
                "rollback_eligible": (
                    before_hash is None
                    and allowed_rollback.get(path.resolve()) == artifact_kind(path, paths)
                ),
            }
        )
    artifacts.append(
        {
            "path": str(paths.report),
            "kind": "onboarding_report",
            "action": "created" if before.get(paths.report) is None else "updated",
            "before_sha256": before.get(paths.report),
            "after_sha256": None,
            "rollback_eligible": False,
        }
    )
    return artifacts


def snapshot_directories(paths: OnboardingPaths) -> dict[Path, bool]:
    candidates = {
        paths.goal_root,
        paths.goal_root / "active",
        paths.goal_root / "completed",
        paths.registry.parent,
        paths.local_out,
        paths.global_out,
        paths.report.parent,
    }
    expanded = set(candidates)
    for candidate in candidates:
        parent = candidate.parent
        while parent != paths.repo and is_within(parent, paths.repo):
            expanded.add(parent)
            parent = parent.parent
    return {path: path.is_dir() for path in expanded if path != paths.repo}


def audit_directories(before: dict[Path, bool]) -> list[dict[str, str]]:
    return [
        {
            "path": str(path),
            "action": "existing" if existed else "created",
        }
        for path, existed in sorted(before.items(), key=lambda item: str(item[0]))
        if path.is_dir()
    ]


def rollback_created_files(report_path: Path) -> dict[str, Any]:
    report_path = report_path.resolve()
    validate_json_file(report_path, RESULT_SCHEMA)
    payload = load_json(report_path)
    repo = Path(payload["target_repo"]).resolve()
    if not is_within(report_path, repo):
        raise ValueError(f"Rollback report is outside its target repository: {report_path}")

    deleted: list[str] = []
    retained: list[dict[str, str]] = []
    allowed_write_set = default_rollback_write_set(repo)
    for artifact in reversed(payload.get("artifacts", [])):
        if not artifact.get("rollback_eligible"):
            continue
        path = Path(artifact["path"]).resolve()
        eligible_record = (
            artifact["action"] == "created"
            and artifact.get("before_sha256") is None
            and bool(artifact.get("after_sha256"))
            and artifact["kind"] != "onboarding_report"
            and allowed_write_set.get(path) == artifact["kind"]
        )
        if not eligible_record:
            retained.append({"path": str(path), "reason": "artifact is outside the derived rollback write set"})
            continue
        reason = "deferred report cannot prove file-creation provenance; no deletion performed"
        if not path.exists():
            reason = "file no longer exists; no deletion performed"
        elif not path.is_file():
            reason = "path is not a file; no deletion performed"
        elif hash_file(path) != artifact["after_sha256"]:
            reason = "hash mismatch; no deletion performed"
        retained.append({"path": str(path), "reason": reason})

    return {
        "version": 1,
        "outcome": "rollback_review_required",
        "exit_code": 2,
        "report": str(report_path),
        "deleted": deleted,
        "retained": retained,
        "message": "Deferred rollback is verification-only because a mutable report cannot prove creation provenance. No files or directories were deleted; use deterministic rerun or explicit per-file operator cleanup.",
    }


def default_rollback_write_set(repo: Path) -> dict[Path, str]:
    local_out = (repo / "outputs" / "goal-lifecycle").resolve()
    global_out = local_out / "global"
    return {
        (repo / "registry" / "REGISTRY.json").resolve(): "repo_registry",
        (local_out / "STATE.json").resolve(): "derived_local_state",
        (local_out / "STATE.md").resolve(): "derived_local_state",
        (global_out / "STATE.json").resolve(): "derived_global_state",
        (global_out / "STATE.md").resolve(): "derived_global_state",
    }


def artifact_kind(path: Path, paths: OnboardingPaths) -> str:
    if path == paths.registry:
        return "repo_registry"
    if is_within(path, paths.global_out):
        return "derived_global_state"
    return "derived_local_state"


def global_registry_proposal(
    paths: OnboardingPaths,
    root_id: str,
    label: str,
    project: str,
) -> dict[str, Any]:
    return {
        "id": root_id,
        "label": label,
        "repo_root": str(paths.repo),
        "goal_root": str(paths.goal_root),
        "state_path": str(paths.local_out / "STATE.json"),
        "scope": "repo",
        "project": project,
        "active": True,
        "added": today(),
        "last_seen": None,
    }


def global_pipeline_failed(summary: RunSummary) -> bool:
    return any(item.status == "failed" for item in summary.stages if item.name in {"aggregate", "validate_global"})


def stage(name: str, status: str, message: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "output_path": None,
        "entry_count": None,
        "issue_count": None,
        "message": message,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(path, text)


def validate_result(payload: dict[str, Any]) -> None:
    schema = load_json(RESULT_SCHEMA)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        messages = [f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors]
        raise ValueError("\n".join(messages))


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "repository"


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def render_human(result: OnboardingResult) -> str:
    lines = [f"outcome={result.outcome} exit_code={result.exit_code}"]
    lines.append(f"repo={result.target_repo} mode={result.mode} registered={str(result.registered).lower()}")
    for item in result.stages:
        line = f"{item['name']}: {item['status']}"
        if item.get("message"):
            line += f" message={item['message']}"
        lines.append(line)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely onboard one explicit repository into Goal Lifecycle.")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--rollback-report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply repo-local scaffold for this invocation and target only.")
    parser.add_argument("--root-id")
    parser.add_argument("--label")
    parser.add_argument("--project")
    parser.add_argument("--goal-root", type=Path, default=Path("goals"))
    parser.add_argument("--registry", type=Path, default=Path("registry/REGISTRY.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs/goal-lifecycle"))
    parser.add_argument("--global-registry", type=Path)
    parser.add_argument("--global-out", type=Path, default=Path("outputs/goal-lifecycle/global"))
    parser.add_argument("--report", type=Path, default=Path("outputs/goal-lifecycle/ONBOARDING.json"))
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.rollback_report:
        if args.repo or args.apply:
            parser.error("--rollback-report cannot be combined with --repo or --apply")
        try:
            rollback = rollback_created_files(args.rollback_report)
        except Exception as exc:
            rollback = {
                "version": 1,
                "outcome": "rollback_failed",
                "exit_code": 1,
                "report": str(args.rollback_report.resolve()),
                "deleted": [],
                "retained": [],
                "message": f"{type(exc).__name__}: {exc}",
            }
        print(json.dumps(rollback, ensure_ascii=False) if args.json_output else render_rollback(rollback))
        return int(rollback["exit_code"])
    if args.repo is None:
        parser.error("--repo is required unless --rollback-report is supplied")
    result = onboard_repository(
        args.repo,
        apply=args.apply,
        root_id=args.root_id,
        label=args.label,
        project=args.project,
        goal_root=args.goal_root,
        registry=args.registry,
        local_out=args.out,
        global_registry_path=args.global_registry,
        global_out=args.global_out,
        report=args.report,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False) if args.json_output else render_human(result))
    return result.exit_code


def render_rollback(result: dict[str, Any]) -> str:
    return (
        f"outcome={result['outcome']} exit_code={result['exit_code']} "
        f"deleted={len(result['deleted'])} retained={len(result['retained'])}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
