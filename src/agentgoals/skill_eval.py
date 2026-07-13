from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from jsonschema import Draft202012Validator

from agentgoals.frontmatter import parse_frontmatter
from agentgoals.io import atomic_write_text
from agentgoals.validate import SCHEMA_DIR


MANIFEST_SCHEMA = SCHEMA_DIR / "skill-eval-manifest.schema.json"
OBSERVATIONS_SCHEMA = SCHEMA_DIR / "skill-eval-observations.schema.json"
DECISION_FIELDS = ("trigger", "size", "output_mode", "file_write", "review_required", "reference_loads")


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    validate_instance(manifest, MANIFEST_SCHEMA)
    validate_manifest_balance(manifest)
    return manifest


def load_observations(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    observations = load_json(path)
    validate_instance(observations, OBSERVATIONS_SCHEMA)
    if observations["manifest_version"] != manifest["version"]:
        raise ValueError("observations manifest_version does not match the manifest")
    if observations["skill_sha256"] != manifest["skill"]["sha256"]:
        raise ValueError("observations skill_sha256 does not match the frozen manifest Skill hash")
    validate_observation_ids(manifest, observations)
    return observations


def validate_manifest_balance(manifest: dict[str, Any]) -> None:
    cases = manifest["cases"]
    ids = [case["id"] for case in cases]
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"manifest has duplicate case ids: {', '.join(duplicates)}")
    by_language_and_trigger = Counter((case["language"], case["expected"]["trigger"]) for case in cases)
    for language in ("zh_TW", "en"):
        for triggered in (True, False):
            if by_language_and_trigger[language, triggered] < 2:
                raise ValueError(f"manifest needs at least two {language} cases with trigger={triggered}")
    if not any(case["category"] == "ambiguous" for case in cases):
        raise ValueError("manifest needs at least one ambiguous case")
    if not any(case["category"] == "adversarial" for case in cases):
        raise ValueError("manifest needs at least one adversarial case")


def validate_observation_ids(manifest: dict[str, Any], observations: dict[str, Any]) -> None:
    expected_ids = {case["id"] for case in manifest["cases"]}
    for run in observations["runs"]:
        ids = [item["case_id"] for item in run["observations"]]
        duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
        unknown = sorted(set(ids) - expected_ids)
        missing = sorted(expected_ids - set(ids))
        if duplicates or unknown or missing:
            fragments = []
            if duplicates:
                fragments.append(f"duplicate={duplicates}")
            if unknown:
                fragments.append(f"unknown={unknown}")
            if missing:
                fragments.append(f"missing={missing}")
            raise ValueError(f"run {run['id']} does not cover the manifest exactly: {'; '.join(fragments)}")


def evaluate(manifest_path: Path, observations_path: Path | None = None) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    skill_path = Path(manifest["skill"]["path"])
    current_skill_hash = hash_file(skill_path) if skill_path.is_file() else None
    frozen_skill_matches = current_skill_hash == manifest["skill"]["sha256"]
    report: dict[str, Any] = {
        "version": 1,
        "manifest": str(manifest_path.resolve()),
        "manifest_version": manifest["version"],
        "rubric_version": manifest["rubric_version"],
        "case_count": len(manifest["cases"]),
        "frozen_skill": {**manifest["skill"], "current_sha256": current_skill_hash, "matches": frozen_skill_matches},
        "thresholds": manifest["thresholds"],
    }
    if observations_path is None:
        report.update(
            {
                "status": "awaiting_observations",
                "baseline_ready": False,
                "reason": "No model-runtime observations supplied; fixture and rubric validation completed only.",
            }
        )
        return report

    observations = load_observations(observations_path, manifest)
    if not observations["runs"]:
        report.update(
            {
                "status": "awaiting_observations",
                "baseline_ready": False,
                "observations": str(observations_path.resolve()),
                "observation_source": observations["observation_source"],
                "runtime": observations.get("runtime", {}),
                "reason": "The observations file contains no completed model-runtime runs.",
            }
        )
        return report
    runs = [score_run(manifest, run, observations_path.parent.resolve()) for run in observations["runs"]]
    aggregate = aggregate_scores(runs)
    thresholds = threshold_results(manifest["thresholds"], aggregate)
    model_runtime = observations["observation_source"] == "model_runtime"
    baseline_ready = bool(frozen_skill_matches and model_runtime and thresholds["passed"])
    report.update(
        {
            "status": "passed" if baseline_ready else "needs_evidence",
            "baseline_ready": baseline_ready,
            "observations": str(observations_path.resolve()),
            "observation_source": observations["observation_source"],
            "runtime": observations.get("runtime", {}),
            "runs": runs,
            "aggregate": aggregate,
            "threshold_results": thresholds,
            "variance": variance(runs),
            "token_usage": token_usage(observations),
        }
    )
    return report


def score_run(manifest: dict[str, Any], run: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    expected_by_id = {case["id"]: case["expected"] for case in manifest["cases"]}
    observations = {item["case_id"]: item for item in run["observations"]}
    true_positive = false_positive = true_negative = false_negative = 0
    correct_decisions = 0
    mismatches = []
    decision_signatures = {}
    artifact_findings = []
    for case_id, expected in expected_by_id.items():
        observed = observations[case_id]
        decision_signatures[case_id] = json.dumps({field: observed[field] for field in DECISION_FIELDS}, sort_keys=True)
        if expected["trigger"] and observed["trigger"]:
            true_positive += 1
        elif not expected["trigger"] and observed["trigger"]:
            false_positive += 1
        elif expected["trigger"] and not observed["trigger"]:
            false_negative += 1
        else:
            true_negative += 1
        differences = {field: {"expected": expected[field], "observed": observed[field]} for field in DECISION_FIELDS if expected[field] != observed[field]}
        findings = validate_artifacts(expected, observed, artifact_root)
        if findings:
            artifact_findings.append({"case_id": case_id, "findings": findings})
        if differences:
            mismatches.append({"case_id": case_id, "differences": differences})
        else:
            correct_decisions += 1
    precision = ratio(true_positive, true_positive + false_positive)
    recall = ratio(true_positive, true_positive + false_negative)
    return {
        "id": run["id"],
        "trigger": {"tp": true_positive, "fp": false_positive, "tn": true_negative, "fn": false_negative, "precision": precision, "recall": recall},
        "decision_accuracy": round(correct_decisions / len(expected_by_id), 4),
        "mismatches": mismatches,
        "decision_signatures": decision_signatures,
        "artifact_findings": artifact_findings,
        "artifacts_valid": not artifact_findings,
    }


def aggregate_scores(runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_count": len(runs),
        "trigger_precision": round(mean(run["trigger"]["precision"] for run in runs), 4),
        "trigger_recall": round(mean(run["trigger"]["recall"] for run in runs), 4),
        "decision_accuracy": round(mean(run["decision_accuracy"] for run in runs), 4),
        "min_trigger_precision": min(run["trigger"]["precision"] for run in runs),
        "min_trigger_recall": min(run["trigger"]["recall"] for run in runs),
        "min_decision_accuracy": min(run["decision_accuracy"] for run in runs),
        "artifacts_valid": all(run["artifacts_valid"] for run in runs),
        "false_positive_count": sum(run["trigger"]["fp"] for run in runs),
        "false_negative_count": sum(run["trigger"]["fn"] for run in runs),
    }


def threshold_results(thresholds: dict[str, float], aggregate: dict[str, Any]) -> dict[str, Any]:
    results = {
        "trigger_precision": aggregate["min_trigger_precision"] >= thresholds["trigger_precision_min"],
        "trigger_recall": aggregate["min_trigger_recall"] >= thresholds["trigger_recall_min"],
        "decision_accuracy": aggregate["min_decision_accuracy"] >= thresholds["decision_accuracy_min"],
        "artifacts": aggregate["artifacts_valid"],
    }
    return {"passed": all(results.values()), "checks": results}


def variance(runs: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        for case_id, signature in run["decision_signatures"].items():
            decisions[case_id].add(signature)
    unstable = sorted(case_id for case_id, outcomes in decisions.items() if len(outcomes) > 1)
    return {"evaluated_runs": len(runs), "unstable_case_count": len(unstable), "unstable_cases": unstable}


def validate_artifacts(expected: dict[str, Any], observed: dict[str, Any], artifact_root: Path) -> list[str]:
    paths = [Path(value) for value in observed.get("artifact_paths", [])]
    if not expected["file_write"]:
        return ["unexpected artifact paths for a no-write fallback"] if paths else []
    if not paths:
        return ["missing artifact paths for a write-producing decision"]
    resolved: dict[str, Path] = {}
    candidates: list[Path] = []
    for path in paths:
        if path.is_absolute():
            return ["artifact paths must be relative to the observations file"]
        candidate = (artifact_root / path).resolve()
        try:
            candidate.relative_to(artifact_root)
        except ValueError:
            return [f"artifact path escapes observation root: {path}"]
        resolved[path.name] = candidate
        candidates.append(candidate)
    if expected["output_mode"] == "single_file":
        valid_contract = False
        for path in candidates:
            if not path.is_file():
                continue
            try:
                document = parse_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                continue
            valid_contract = document.metadata.get("type") == "goal-contract" and "## Contract" in document.body
            if valid_contract:
                break
        return [] if valid_contract else ["missing a valid single-file goal-contract artifact"]
    required = {
        "CONTRACT.md": "goal-contract", "PLAN.md": "goal-plan", "EVIDENCE.md": "goal-evidence"
    }
    findings = []
    for name, document_type in required.items():
        path = resolved.get(name)
        if path is None:
            findings.append(f"missing required artifact: {name}")
            continue
        if not path.is_file():
            findings.append(f"artifact does not exist: {path}")
            continue
        try:
            document = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append(f"cannot parse {name}: {type(exc).__name__}")
            continue
        if document.metadata.get("type") != document_type:
            findings.append(f"{name} type must be {document_type}")
        if name == "PLAN.md":
            if "## Execution Plan" not in document.body and "# Plan" not in document.body:
                findings.append(f"{name} is missing a plan section")
        else:
            required_heading = "## Contract" if name == "CONTRACT.md" else "## Verification Results"
            if required_heading not in document.body:
                findings.append(f"{name} is missing {required_heading}")
    return findings


def token_usage(observations: dict[str, Any]) -> dict[str, Any]:
    values = [item["token_count"] for run in observations["runs"] for item in run["observations"] if "token_count" in item]
    if not values:
        return {"available": False, "reason": "The observation runtime did not expose token_count."}
    return {"available": True, "count": len(values), "total": sum(values), "mean": round(mean(values), 2)}


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON: {path}: {exc}") from exc


def validate_instance(instance: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        messages = [f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}" for error in errors]
        raise ValueError("; ".join(messages))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score a versioned Goal Skill behavior evaluation.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate(args.manifest, args.observations)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        atomic_write_text(args.report, rendered)
    print(rendered, end="")
    return 0 if report["baseline_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
