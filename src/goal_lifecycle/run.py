from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from goal_lifecycle.aggregate import aggregate
from goal_lifecycle.reconcile import StateEntry, reconcile
from goal_lifecycle.validate import validate_registry, validate_state


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

    def to_dict(self) -> dict:
        return asdict(self)


def run_pipeline(
    registry_path: Path,
    out_dir: Path,
    global_registry_path: Path | None = None,
    global_out_dir: Path | None = None,
    evaluation_date: date | None = None,
) -> RunSummary:
    stages: list[StageResult] = []
    local_state_path = out_dir / "STATE.json"
    resolved_global_out = global_out_dir or out_dir / "global"
    global_state_path = resolved_global_out / "STATE.json"

    try:
        ensure_output_allowed(out_dir, "out")
        if evaluation_date is None:
            local_entries = reconcile(registry_path, out_dir)
        else:
            local_entries = reconcile(registry_path, out_dir, evaluation_date=evaluation_date)
        stages.append(result_for_entries("reconcile", local_state_path, local_entries))
    except Exception as exc:
        stages.append(failed_result("reconcile", local_state_path, exc))
        stages.append(skipped_result("validate_local", local_state_path, "reconcile failed"))
        stages.extend(skipped_global_results(global_registry_path, global_state_path, "local pipeline failed"))
        return finish(stages)

    try:
        validate_registry(registry_path)
        validate_state(local_state_path)
        stages.append(passed_validation_result("validate_local", local_state_path, local_entries))
    except Exception as exc:
        stages.append(failed_result("validate_local", local_state_path, exc))
        stages.extend(skipped_global_results(global_registry_path, global_state_path, "local validation failed"))
        return finish(stages)

    if global_registry_path is None:
        stages.extend(skipped_global_results(None, global_state_path, "global registry not supplied"))
        return finish(stages)

    try:
        ensure_output_allowed(resolved_global_out, "global_out")
        global_entries = aggregate(global_registry_path, resolved_global_out)
        stages.append(result_for_entries("aggregate", global_state_path, global_entries))
    except Exception as exc:
        stages.append(failed_result("aggregate", global_state_path, exc))
        stages.append(skipped_result("validate_global", global_state_path, "aggregate failed"))
        return finish(stages)

    try:
        validate_state(global_state_path)
        stages.append(passed_validation_result("validate_global", global_state_path, global_entries))
    except Exception as exc:
        stages.append(failed_result("validate_global", global_state_path, exc))

    return finish(stages)


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


def finish(stages: list[StageResult]) -> RunSummary:
    if any(stage.status == "failed" for stage in stages):
        return RunSummary(version=1, status="failed", exit_code=1, stages=stages)
    if any(stage.status == "issues" for stage in stages):
        return RunSummary(version=1, status="issues", exit_code=2, stages=stages)
    return RunSummary(version=1, status="passed", exit_code=0, stages=stages)


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
    lines = [f"status={summary.status} exit_code={summary.exit_code}"]
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
    parser = argparse.ArgumentParser(description="Run the deterministic read-only Goal Lifecycle pipeline.")
    parser.add_argument("--registry", type=Path, default=Path("registry/REGISTRY.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--global-registry", type=Path)
    parser.add_argument("--global-out", type=Path)
    parser.add_argument("--evaluation-date", type=date.fromisoformat)
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
    )
    if args.json_output:
        print(json.dumps(summary.to_dict(), ensure_ascii=False))
    else:
        print(render_human(summary))
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
