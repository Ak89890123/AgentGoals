from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from goal_lifecycle.session_handoff import assess_session_handoff


GIT_COMMANDS = (
    ("git", "rev-parse", "--show-toplevel"),
    ("git", "worktree", "list", "--porcelain"),
    ("git", "branch", "--show-current"),
    ("git", "status", "--short"),
    ("git", "log", "--oneline", "-10"),
    ("git", "diff", "--stat"),
    ("git", "stash", "list"),
    ("git", "branch", "-a"),
)


def utf8_stats(text: str) -> dict[str, Any]:
    payload = text.encode("utf-8")
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def collect_git_context(repo: Path) -> str:
    chunks = []
    for command in GIT_COMMANDS:
        result = subprocess.run(
            command,
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        chunks.append(result.stdout)
        chunks.append(result.stderr)
    return "".join(chunks)


def contract_frontmatter(path: Path) -> str:
    return markdown_frontmatter(path.read_text(encoding="utf-8"), path)


def markdown_frontmatter(text: str, label: object = "document") -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"Document has no frontmatter: {label}")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"Document frontmatter is not closed: {label}") from exc
    return "\n".join(lines[: end + 1]) + "\n"


def proposed_additions(path: Path, target: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    marker = f"*** Update File: {target}"
    try:
        start = lines.index(marker) + 1
    except ValueError as exc:
        raise ValueError(f"Patch target not found: {target}") from exc
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("*** Update File:") or lines[index] == "*** End Patch"),
        len(lines),
    )
    return "\n".join(line[1:] for line in lines[start:end] if line.startswith("+")) + "\n"


def parse_update_hunks(path: Path) -> dict[str, list[tuple[list[str], list[str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed: dict[str, list[tuple[list[str], list[str]]]] = {}
    target: str | None = None
    old: list[str] | None = None
    new: list[str] | None = None

    def finish_hunk() -> None:
        nonlocal old, new
        if target is not None and old is not None and new is not None:
            parsed.setdefault(target, []).append((old, new))
        old = None
        new = None

    for line in lines:
        if line.startswith("*** Update File: "):
            finish_hunk()
            target = line.removeprefix("*** Update File: ")
        elif line == "@@":
            finish_hunk()
            old = []
            new = []
        elif old is not None and new is not None and line:
            if line[0] == " ":
                old.append(line[1:])
                new.append(line[1:])
            elif line[0] == "-":
                old.append(line[1:])
            elif line[0] == "+":
                new.append(line[1:])
    finish_hunk()
    return parsed


def apply_patch_in_memory(path: Path, target: str) -> str:
    hunks = parse_update_hunks(path).get(target)
    if not hunks:
        raise ValueError(f"Patch target has no update hunks: {target}")
    source_path = Path(target)
    if not source_path.is_file():
        raise ValueError(f"Patch target does not exist: {target}")
    lines = source_path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    for old, new in hunks:
        matches = [index for index in range(0, len(lines) - len(old) + 1) if lines[index : index + len(old)] == old]
        if len(matches) != 1:
            raise ValueError(f"Patch hunk for {target} matched {len(matches)} locations instead of 1")
        index = matches[0]
        lines[index : index + len(old)] = new
    return "\n".join(lines)


def materialize_patch_target(path: Path, target: str) -> tuple[str, str]:
    hunks = parse_update_hunks(path).get(target)
    if not hunks:
        raise ValueError(f"Patch target has no update hunks: {target}")
    source_path = Path(target)
    if not source_path.is_file():
        raise ValueError(f"Patch target does not exist: {target}")
    current = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    lines = current.split("\n")
    installed = all(
        sum(lines[index : index + len(new)] == new for index in range(0, len(lines) - len(new) + 1)) == 1
        for _, new in hunks
        if new
    )
    if installed:
        return current, "already_applied"
    return apply_patch_in_memory(path, target), "applicable"


def verify_patch_contexts(path: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for target, hunks in parse_update_hunks(path).items():
        try:
            before = Path(target).read_text(encoding="utf-8")
            applied, application_state = materialize_patch_target(path, target)
            frontmatter_unchanged = markdown_frontmatter(before, target) == markdown_frontmatter(applied, target)
            result = {
                "path": target,
                "exists": True,
                "hunk_count": len(hunks),
                "matched_hunks": len(hunks),
                "applied_sha256": utf8_stats(applied)["sha256"],
                "frontmatter_unchanged": frontmatter_unchanged,
                "application_state": application_state,
                "valid": frontmatter_unchanged,
            }
        except (OSError, UnicodeError, ValueError):
            result = {
                "path": target,
                "exists": Path(target).is_file(),
                "hunk_count": len(hunks),
                "matched_hunks": 0,
                "applied_sha256": None,
                "frontmatter_unchanged": False,
                "application_state": "invalid",
                "valid": False,
            }
        results.append(result)
    return {
        "valid": bool(results) and all(item["valid"] for item in results),
        "targets": results,
    }


def evaluate_instruction_preservation(patch_path: Path, cases_path: Path) -> dict[str, Any]:
    fixture = json.loads(cases_path.read_text(encoding="utf-8"))
    proposed: dict[str, str] = {}
    results = []
    for case in fixture.get("cases", []):
        target = case["skill_target"]
        if target not in proposed:
            proposed[target] = materialize_patch_target(patch_path, target)[0]
        text = proposed[target]
        missing = [phrase for phrase in case.get("required_phrases", []) if phrase not in text]
        forbidden = [phrase for phrase in case.get("forbidden_phrases", []) if phrase in text]
        results.append(
            {
                "id": case["id"],
                "target": target,
                "expected_path": case["expected_path"],
                "missing_required": missing,
                "present_forbidden": forbidden,
                "passed": not missing and not forbidden,
            }
        )
    return {
        "version": fixture.get("version"),
        "passed": bool(results) and all(item["passed"] for item in results),
        "case_count": len(results),
        "results": results,
    }


def evaluate(
    repo: Path,
    skill_path: Path,
    patch_path: Path,
    patch_target: str,
    report_path: Path,
    state_path: Path,
    contract_path: Path,
    legacy_files: Sequence[Path],
    behavior_cases_path: Path | None = None,
) -> dict[str, Any]:
    git_context = collect_git_context(repo)
    skill = skill_path.read_text(encoding="utf-8")
    legacy_parts = [skill, git_context]
    legacy_parts.extend(path.read_text(encoding="utf-8") for path in legacy_files)
    baseline = "".join(legacy_parts)

    handoff = assess_session_handoff(report_path, state_path)
    compact = json.dumps(handoff, ensure_ascii=False, sort_keys=True)
    proposed_skill = materialize_patch_target(patch_path, patch_target)[0]
    candidate = "".join((proposed_skill, git_context, compact, contract_frontmatter(contract_path)))

    baseline_stats = utf8_stats(baseline)
    candidate_stats = utf8_stats(candidate)
    ratio = candidate_stats["bytes"] / baseline_stats["bytes"] if baseline_stats["bytes"] else 1.0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    metrics = report.get("metrics", {})
    patch_check = verify_patch_contexts(patch_path)
    instruction_preservation = evaluate_instruction_preservation(patch_path, behavior_cases_path) if behavior_cases_path else None
    return {
        "version": 1,
        "scenario": "registered_resume",
        "baseline": {
            **baseline_stats,
            "inputs": [str(skill_path), "git_context", *[str(path) for path in legacy_files]],
        },
        "candidate": {
            **candidate_stats,
            "inputs": [str(skill_path), str(patch_path), "git_context", str(report_path), str(state_path), str(contract_path)],
            "mode": handoff["mode"],
            "fallback_reason": handoff["fallback_reason"],
        },
        "ratio": round(ratio, 4),
        "reduction_percent": round((1 - ratio) * 100, 2),
        "target_met": ratio <= 0.5,
        "semantic_model_calls": metrics.get("semantic_model_calls"),
        "pipeline_invocations": metrics.get("pipeline_invocations"),
        "patch_contexts": patch_check,
        "instruction_preservation": instruction_preservation,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure the fixed Goal session-resume context scenario.")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--skill", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--patch-target", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--legacy-file", type=Path, action="append", default=[])
    parser.add_argument("--behavior-cases", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = evaluate(
        args.repo.resolve(),
        args.skill,
        args.patch,
        args.patch_target,
        args.report,
        args.state,
        args.contract,
        args.legacy_file,
        args.behavior_cases,
    )
    print(json.dumps(payload, ensure_ascii=False))
    instructions_passed = payload["instruction_preservation"] is None or payload["instruction_preservation"]["passed"]
    return 0 if payload["target_met"] and payload["candidate"]["mode"] == "fast_path" and payload["patch_contexts"]["valid"] and instructions_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
