from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from agentgoals.aggregate import aggregate, load_global_registry
from agentgoals.reconcile import StateEntry, reconcile
from agentgoals.validate import load_json, validate_registry, validate_state


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str
    output_path: str | None
    entry_count: int | None
    issue_count: int | None
    message: str | None


@dataclass(frozen=True)
class RunSummary:
    version: int
    status: str
    exit_code: int
    stages: list[StageResult]
    operation_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def run_pipeline(
    registry_path: Path,
    out_dir: Path,
    global_registry_path: Path | None = None,
    global_out_dir: Path | None = None,
    evaluation_date: date | None = None,
    operation_id: str | None = None,
    require_global: bool = False,
) -> RunSummary:
    operation_id = operation_id or uuid4().hex
    stages: list[StageResult] = []
    local_state_path = out_dir / "STATE.json"
    resolved_global_out = global_out_dir or out_dir / "global"
    global_state_path = resolved_global_out / "STATE.json"

    if require_global:
        if global_registry_path is None:
            return required_global_summary(
                local_state_path,
                global_state_path,
                operation_id,
                "Global registry is required for global refresh.",
            )
        if not global_registry_path.resolve().is_file():
            return required_global_summary(
                local_state_path,
                global_state_path,
                operation_id,
                f"Global registry is required for global refresh: {global_registry_path.resolve()}",
            )

    if global_registry_path is not None:
        try:
            ensure_output_allowed(resolved_global_out, "global_out")
        except Exception as exc:
            return required_global_summary(
                local_state_path,
                global_state_path,
                operation_id,
                str(exc),
            )

    try:
        ensure_output_allowed(out_dir, "out")
        if evaluation_date is None:
            local_entries = reconcile(registry_path, out_dir, operation_id=operation_id)
        else:
            local_entries = reconcile(
                registry_path,
                out_dir,
                evaluation_date=evaluation_date,
                operation_id=operation_id,
            )
        stages.append(result_for_entries("reconcile", local_state_path, local_entries))
    except Exception as exc:
        stages.append(failed_result("reconcile", local_state_path, exc))
        stages.append(skipped_result("validate_local", local_state_path, "reconcile failed"))
        stages.extend(skipped_global_results(global_registry_path, global_state_path, "local pipeline failed"))
        return finish(stages, operation_id)

    try:
        validate_registry(registry_path)
        validate_state(local_state_path)
        stages.append(passed_validation_result("validate_local", local_state_path, local_entries))
    except Exception as exc:
        stages.append(failed_result("validate_local", local_state_path, exc))
        stages.extend(skipped_global_results(global_registry_path, global_state_path, "local validation failed"))
        return finish(stages, operation_id)

    if global_registry_path is None:
        stages.extend(skipped_global_results(None, global_state_path, "global registry not supplied"))
        return finish(stages, operation_id)

    try:
        global_entries = aggregate(global_registry_path, resolved_global_out, operation_id=operation_id)
        stages.append(result_for_entries("aggregate", global_state_path, global_entries))
    except Exception as exc:
        stages.append(failed_result("aggregate", global_state_path, exc))
        stages.append(skipped_result("validate_global", global_state_path, "aggregate failed"))
        return finish(stages, operation_id)

    try:
        validate_state(global_state_path)
        verify_global_refresh(local_state_path, global_state_path, operation_id, global_registry_path)
        stages.append(passed_validation_result("validate_global", global_state_path, global_entries))
    except Exception as exc:
        stages.append(failed_result("validate_global", global_state_path, exc))

    return finish(stages, operation_id)


def result_for_entries(name: str, state_path: Path, entries: list[StateEntry]) -> StageResult:
    issue_count = count_issues(entries)
    return StageResult(
        name=name,
        status="issues" if issue_count else "passed",
        output_path=absolute_path(state_path),
        entry_count=len(entries),
        issue_count=issue_count,
        message=None,
    )


def passed_validation_result(name: str, state_path: Path, entries: list[StateEntry]) -> StageResult:
    return StageResult(
        name=name,
        status="passed",
        output_path=absolute_path(state_path),
        entry_count=len(entries),
        issue_count=count_issues(entries),
        message=None,
    )


def failed_result(name: str, state_path: Path, exc: Exception) -> StageResult:
    return StageResult(
        name=name,
        status="failed",
        output_path=absolute_path(state_path),
        entry_count=None,
        issue_count=None,
        message=f"{type(exc).__name__}: {exc}",
    )


def skipped_result(name: str, state_path: Path | None, reason: str) -> StageResult:
    return StageResult(
        name=name,
        status="skipped",
        output_path=absolute_path(state_path) if state_path else None,
        entry_count=None,
        issue_count=None,
        message=reason,
    )


def skipped_global_results(
    global_registry_path: Path | None,
    global_state_path: Path,
    reason: str,
) -> list[StageResult]:
    output_path = global_state_path if global_registry_path is not None else None
    return [
        skipped_result("aggregate", output_path, reason),
        skipped_result("validate_global", output_path, reason),
    ]


def required_global_summary(
    local_state_path: Path,
    global_state_path: Path,
    operation_id: str,
    message: str,
) -> RunSummary:
    return finish(
        [
            skipped_result("reconcile", local_state_path, "global refresh preflight failed"),
            skipped_result("validate_local", local_state_path, "global refresh preflight failed"),
            failed_result("aggregate", global_state_path, ValueError(message)),
            skipped_result("validate_global", global_state_path, "aggregate failed"),
        ],
        operation_id,
    )


def verify_global_refresh(
    local_state_path: Path,
    global_state_path: Path,
    operation_id: str,
    global_registry_path: Path,
) -> None:
    local_payload = load_json(local_state_path)
    global_payload = load_json(global_state_path)
    if local_payload.get("operation_id") != operation_id:
        raise ValueError("Local STATE operation_id does not match the pipeline operation.")
    if global_payload.get("operation_id") != operation_id:
        raise ValueError("Global STATE operation_id does not match the pipeline operation.")

    local_generated = parse_generated_at(local_payload, "local")
    global_generated = parse_generated_at(global_payload, "global")
    if global_generated < local_generated:
        raise ValueError("Global STATE was generated before local STATE.")

    roots = load_global_registry(global_registry_path)
    registered_root = next(
        (root for root in roots if root.state_path.resolve() == local_state_path.resolve()),
        None,
    )
    if registered_root is None:
        raise ValueError(
            f"Global registry has no registered state_path for local STATE: {local_state_path.resolve()}"
        )
    expected = {
        f"{registered_root.id}/{item['id']}"
        for item in local_payload.get("entries", [])
    }
    observed = {str(item["goal_key"]) for item in global_payload.get("entries", [])}
    missing = sorted(expected - observed)
    if missing:
        raise ValueError(f"Global STATE is missing canonical Goal keys: {missing}")


def parse_generated_at(payload: dict, scope: str) -> datetime:
    value = payload.get("generated_at")
    if not isinstance(value, str) or not value:
        raise ValueError(f"{scope} STATE generated_at is missing.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{scope} STATE generated_at is invalid: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{scope} STATE generated_at must include a timezone.")
    return parsed.astimezone(timezone.utc)


def finish(stages: list[StageResult], operation_id: str = "") -> RunSummary:
    if any(stage.status == "failed" for stage in stages):
        return RunSummary(version=1, status="failed", exit_code=1, stages=stages, operation_id=operation_id)
    if any(stage.status == "issues" for stage in stages):
        return RunSummary(version=1, status="issues", exit_code=2, stages=stages, operation_id=operation_id)
    return RunSummary(version=1, status="passed", exit_code=0, stages=stages, operation_id=operation_id)


def count_issues(entries: list[StateEntry]) -> int:
    return sum(len(entry.issues) for entry in entries)


def absolute_path(path: Path) -> str:
    return str(path.resolve())


def ensure_output_allowed(path: Path, field_name: str) -> None:
    global_codex_root = (Path.home() / ".codex").resolve()
    try:
        path.resolve().relative_to(global_codex_root)
    except ValueError:
        return
    raise ValueError(f"{field_name} must not be under the global Codex directory: {path}")


def render_human(summary: RunSummary) -> str:
    lines = [f"status={summary.status} operation_id={summary.operation_id} exit_code={summary.exit_code}"]
    for stage in summary.stages:
        details = [stage.status]
        if stage.entry_count is not None:
            details.append(f"entries={stage.entry_count}")
        if stage.issue_count is not None:
            details.append(f"issues={stage.issue_count}")
        if stage.output_path:
            details.append(f"output={stage.output_path}")
        if stage.message:
            details.append(f"message={stage.message}")
        lines.append(f"{stage.name}: {' '.join(details)}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deterministic read-only AgentGoals pipeline.")
    parser.add_argument("--registry", type=Path, default=Path("registry/REGISTRY.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--global-registry", type=Path)
    parser.add_argument("--global-out", type=Path)
    parser.add_argument("--evaluation-date", type=date.fromisoformat)
    parser.add_argument("--operation-id")
    parser.add_argument(
        "--require-global",
        action="store_true",
        help="Fail before local writes unless a global registry is supplied for global refresh.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_pipeline(
        registry_path=args.registry,
        out_dir=args.out,
        global_registry_path=args.global_registry,
        global_out_dir=args.global_out,
        evaluation_date=args.evaluation_date,
        operation_id=args.operation_id,
        require_global=args.require_global,
    )
    if args.json_output:
        print(json.dumps(summary.to_dict(), ensure_ascii=False))
    else:
        print(render_human(summary))
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
