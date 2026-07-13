from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from agentgoals.artifact_audit import (
    AuditStoreError,
    audit_database_reference,
    begin_audit_receipt,
    complete_audit_receipt,
    fail_audit_receipt,
)
from agentgoals.frontmatter import parse_frontmatter
from agentgoals.io import atomic_write_text
from agentgoals.validate import SCHEMA_DIR


DECISION_SCHEMA = SCHEMA_DIR / "artifact-decision.schema.json"
ALLOWED_LAYOUTS = {
    "small": {("none", False), ("single_file", True)},
    "standard": {("single_file", True)},
    "goal_grade": {("single_file", True), ("directory", True)},
}


class ArtifactToolError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactFile:
    path: Path
    text: str
    sha256: str
    action: str = "planned"


@dataclass(frozen=True)
class ArtifactResult:
    status: str
    files: tuple[ArtifactFile, ...]


def preview_artifacts(repo_root: Path, artifact_root: Path, raw_decision: Mapping[str, Any]) -> ArtifactResult:
    decision = parse_decision(raw_decision)
    repo = repo_root.resolve()
    ensure_within(artifact_root.resolve(), repo, "artifact root is outside repository root")
    # Keep the caller's spelling of the path in previews.  This makes the preview
    # directly actionable while containment is still decided from resolved paths.
    root = artifact_root.resolve()
    if decision["layout"] == "none":
        return ArtifactResult("no_write", ())
    if decision["layout"] == "single_file":
        path = root / f"{decision['goal_id']}-goal-contract.md"
        text = render_single_file(decision, path.name)
        return ArtifactResult("preview", (artifact_file(path, text),))
    goal_dir = root / decision["goal_id"]
    files = (
        artifact_file(goal_dir / "CONTRACT.md", render_contract(decision)),
        artifact_file(goal_dir / "PLAN.md", render_plan(decision)),
        artifact_file(goal_dir / "EVIDENCE.md", render_evidence(decision)),
    )
    return ArtifactResult("preview", files)


def apply_artifacts(repo_root: Path, artifact_root: Path, raw_decision: Mapping[str, Any]) -> ArtifactResult:
    preview = preview_artifacts(repo_root, artifact_root, raw_decision)
    if preview.status == "no_write":
        return preview
    conflicts = [item.path for item in preview.files if item.path.exists()]
    if conflicts:
        raise ArtifactToolError(f"artifact target already exists: {conflicts[0]}")
    root = artifact_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    ensure_within(root.resolve(), repo_root.resolve(), "artifact root is outside repository root")
    root = root.resolve()
    if len(preview.files) == 1:
        item = preview.files[0]
        publish_single_file(item, repo_root.resolve())
    else:
        goal_dir = preview.files[0].path.parent
        stage_dir = root / f".{goal_dir.name}.{uuid.uuid4().hex}.stage"
        stage_dir.mkdir()
        try:
            for item in preview.files:
                relative = item.path.relative_to(goal_dir)
                atomic_write_text(stage_dir / relative, item.text)
            publish_directory(stage_dir, goal_dir, repo_root.resolve())
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)
    applied = tuple(ArtifactFile(item.path, item.text, item.sha256, "created") for item in preview.files)
    return ArtifactResult("applied", applied)


def validate_artifacts(files: tuple[ArtifactFile, ...]) -> list[str]:
    findings = []
    for item in files:
        if not item.path.is_file():
            findings.append(f"missing artifact: {item.path}")
            continue
        if sha256_text(item.path.read_text(encoding="utf-8")) != item.sha256:
            findings.append(f"hash mismatch: {item.path}")
        try:
            document = parse_frontmatter(item.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append(f"cannot parse {item.path}: {type(exc).__name__}")
            continue
        expected_type, required_heading = expected_shape(item.path)
        if document.metadata.get("type") != expected_type:
            findings.append(f"{item.path.name} type must be {expected_type}")
        if required_heading not in document.body:
            findings.append(f"{item.path.name} is missing {required_heading}")
    return findings


def audit_payload(mode: str, result: ArtifactResult, repo_root: Path) -> dict[str, Any]:
    """Return a content-free, serializable record for a preview or apply event."""
    repo = repo_root.resolve()
    return {
        "version": 1,
        "mode": mode,
        "status": result.status,
        "file_count": len(result.files),
        "files": [
            {"path": ensure_relative_path(item.path, repo), "sha256": item.sha256, "action": item.action}
            for item in result.files
        ],
    }


def execute_artifact_tool(
    repo_root: Path,
    artifact_root: Path,
    raw_decision: Mapping[str, Any],
    *,
    apply: bool = False,
    write_audit: bool = False,
) -> dict[str, Any]:
    """Execute the explicit mode and return a content-free JSON-safe receipt."""
    if write_audit and not apply:
        raise ArtifactToolError("write_audit requires explicit apply mode")
    if not apply:
        result = preview_artifacts(repo_root, artifact_root, raw_decision)
        return audit_payload("preview", result, repo_root)

    decision = parse_decision(raw_decision)
    receipt_id: str | None = None
    if write_audit:
        planned = preview_artifacts(repo_root, artifact_root, decision)
        receipt_id = begin_audit_receipt(repo_root, artifact_root, decision["goal_id"], planned)
    try:
        result = apply_artifacts(repo_root, artifact_root, decision)
        findings = validate_artifacts(result.files)
        if findings:
            raise ArtifactToolError("generated artifacts failed validation: " + "; ".join(findings))
    except Exception as exc:
        if receipt_id is not None:
            try:
                fail_audit_receipt(repo_root, receipt_id, exc)
            except AuditStoreError:
                pass
        raise
    payload = audit_payload("apply" if apply else "preview", result, repo_root)
    if receipt_id is not None:
        try:
            audit_path = complete_audit_receipt(repo_root, receipt_id, result)
        except AuditStoreError as exc:
            raise ArtifactToolError(
                f"artifact created but audit receipt remains pending: {receipt_id}"
            ) from exc
        payload["audit_path"] = audit_database_reference(repo_root)
    return payload


def parse_decision(raw_decision: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_decision, Mapping):
        raise ArtifactToolError("decision must be a JSON object")
    decision = dict(raw_decision)
    errors = sorted(Draft202012Validator(load_schema()).iter_errors(decision), key=lambda error: list(error.path))
    if errors:
        message = "; ".join(f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}" for error in errors)
        size = decision.get("size")
        prefix = f"{size} decision is invalid: " if isinstance(size, str) else ""
        raise ArtifactToolError(prefix + message)
    if (decision["layout"], decision["file_write"]) not in ALLOWED_LAYOUTS[decision["size"]]:
        raise ArtifactToolError(f"{decision['size']} does not allow layout={decision['layout']} with file_write={decision['file_write']}")
    try:
        date.fromisoformat(decision["date"])
    except ValueError as exc:
        raise ArtifactToolError("date must be a valid ISO calendar date") from exc
    return decision


def render_single_file(decision: Mapping[str, Any], filename: str) -> str:
    return "\n".join(
        (
            "---",
            "type: goal-contract",
            "schema_version: 1",
            f"id: {yaml_scalar(decision['goal_id'])}",
            f"title: {yaml_scalar(decision['title'])}",
            "status: draft",
            f"created: {yaml_scalar(decision['date'])}",
            f"updated: {yaml_scalar(decision['date'])}",
            "completed:",
            f"owner: {yaml_scalar(decision['owner'])}",
            "file_mode: single-file",
            f"project: {yaml_scalar(decision['project'])}",
            "paths:",
            f"  contract: ./{filename}",
            "review:",
            f"  required: {str(decision['review_required']).lower()}",
            "  verdict: pending",
            "tags: []",
            "---",
            "",
            f"# Goal Contract: {decision['title']}",
            "",
            "## Contract",
            "",
            "### Goal",
            "",
            "[Describe the requested outcome.]",
            "",
            "## Completion Notes",
            "",
            "- Final status: pending",
            "",
        )
    )


def render_contract(decision: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "---",
            "type: goal-contract",
            "schema_version: 1",
            f"id: {yaml_scalar(decision['goal_id'])}",
            f"title: {yaml_scalar(decision['title'])}",
            "status: draft",
            f"created: {yaml_scalar(decision['date'])}",
            f"updated: {yaml_scalar(decision['date'])}",
            "completed:",
            f"owner: {yaml_scalar(decision['owner'])}",
            "file_mode: directory",
            f"project: {yaml_scalar(decision['project'])}",
            "paths:",
            "  contract: ./CONTRACT.md",
            "  plan: ./PLAN.md",
            "  evidence: ./EVIDENCE.md",
            "review:",
            f"  required: {str(decision['review_required']).lower()}",
            "  verdict: pending",
            "tags: []",
            "---",
            "",
            f"# Goal Contract: {decision['title']}",
            "",
            "## Contract",
            "",
            "### Goal",
            "",
            "[Describe the requested outcome.]",
            "",
        )
    )


def render_plan(decision: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "---",
            "type: goal-plan",
            "schema_version: 1",
            f"goal_id: {yaml_scalar(decision['goal_id'])}",
            "status: draft",
            f"updated: {yaml_scalar(decision['date'])}",
            "contract: ./CONTRACT.md",
            "evidence: ./EVIDENCE.md",
            "---",
            "",
            f"# Plan: {decision['title']}",
            "",
            "## Execution Plan",
            "",
            "1. [Add steps after the Goal is accepted.]",
            "",
        )
    )


def render_evidence(decision: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "---",
            "type: goal-evidence",
            "schema_version: 1",
            f"goal_id: {yaml_scalar(decision['goal_id'])}",
            "status: pending",
            f"updated: {yaml_scalar(decision['date'])}",
            "contract: ./CONTRACT.md",
            "plan: ./PLAN.md",
            "review:",
            "  verdict: pending",
            "---",
            "",
            f"# Evidence: {decision['title']}",
            "",
            "## Verification Results",
            "",
            "- Pending implementation evidence.",
            "",
        )
    )


def artifact_file(path: Path, text: str) -> ArtifactFile:
    return ArtifactFile(path, text, sha256_text(text))


def publish_single_file(item: ArtifactFile, repo_root: Path) -> None:
    """Publish a completed staged file without ever replacing a new competitor."""
    stage_path = item.path.parent / f".{item.path.name}.{uuid.uuid4().hex}.stage"
    try:
        atomic_write_text(stage_path, item.text)
        try:
            if item.path.parent.is_symlink():
                raise ArtifactToolError(f"artifact target parent must not be a symlink: {item.path.parent}")
            ensure_within(item.path.resolve(), repo_root, "artifact target is outside repository root")
            os.link(stage_path, item.path)
        except FileExistsError as exc:
            raise ArtifactToolError(f"artifact target already exists: {item.path}") from exc
    finally:
        if stage_path.exists():
            stage_path.unlink()


def publish_directory(stage_dir: Path, goal_dir: Path, repo_root: Path) -> None:
    """Claim a new directory and link a fully staged scaffold without replacing a competitor."""
    try:
        goal_dir.mkdir()
    except FileExistsError as exc:
        raise ArtifactToolError(f"artifact target already exists: {goal_dir}") from exc
    if goal_dir.is_symlink():
        raise ArtifactToolError(f"artifact target must not be a symlink: {goal_dir}")
    ensure_within(goal_dir.resolve(), repo_root, "artifact target is outside repository root")
    published: list[tuple[Path, Path]] = []
    try:
        for staged in stage_dir.iterdir():
            destination = goal_dir / staged.name
            os.link(staged, destination)
            published.append((staged, destination))
    except OSError:
        for staged, destination in reversed(published):
            try:
                if destination.exists() and os.path.samefile(staged, destination):
                    destination.unlink()
            except OSError:
                pass
        try:
            goal_dir.rmdir()
        except OSError:
            pass
        raise


def expected_shape(path: Path) -> tuple[str, str]:
    if path.name == "PLAN.md":
        return "goal-plan", "## Execution Plan"
    if path.name == "EVIDENCE.md":
        return "goal-evidence", "## Verification Results"
    return "goal-contract", "## Contract"


def ensure_within(path: Path, root: Path, message: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ArtifactToolError(message) from exc


def load_schema() -> dict[str, Any]:
    return json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_relative_path(path: Path, repo_root: Path) -> str:
    ensure_within(path.resolve(), repo_root, "artifact path is outside repository root")
    return path.resolve().relative_to(repo_root).as_posix()


def yaml_scalar(value: Any) -> str:
    """JSON strings are also valid YAML double-quoted scalars."""
    return json.dumps(str(value), ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or explicitly create deterministic Goal artifacts.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True, help="Path to a JSON artifact decision.")
    parser.add_argument("--apply", action="store_true", help="Create artifacts. Omit for a no-write preview.")
    parser.add_argument("--audit", action="store_true", help="With --apply, record a hash-only SQLite receipt under repository root.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        decision = json.loads(args.decision.read_text(encoding="utf-8"))
        payload = execute_artifact_tool(
            args.repo_root,
            args.artifact_root,
            decision,
            apply=args.apply,
            write_audit=args.audit,
        )
    except (ArtifactToolError, AuditStoreError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
