from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from agentgoals.skill_eval import evaluate, hash_file, load_manifest, main
from agentgoals.skill_eval_runtime import build_prompt, main as runtime_main, plan_runs
from tests.test_reconcile import make_workspace


MANIFEST = Path("fixtures/goal_skill_eval/v1/manifest.json")


def prepared_manifest(root: Path) -> tuple[Path, dict]:
    skill = root / "SKILL.md"
    skill.write_text("---\nname: test-skill\n---\n", encoding="utf-8")
    payload = load_manifest(MANIFEST)
    payload["skill"] = {"path": str(skill), "sha256": hash_file(skill)}
    path = root / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def write_artifacts(root: Path, run_id: str, case_id: str, expected: dict) -> list[str]:
    if not expected["file_write"]:
        return []
    artifact_dir = root / "artifacts" / run_id / case_id
    artifact_dir.mkdir(parents=True)
    if expected["output_mode"] == "single_file":
        goal = artifact_dir / "fixture-goal-contract.md"
        goal.write_text("---\ntype: goal-contract\n---\n\n## Contract\n", encoding="utf-8")
        return [str(goal.relative_to(root))]
    documents = {
        "CONTRACT.md": "---\ntype: goal-contract\n---\n\n## Contract\n",
        "PLAN.md": "---\ntype: goal-plan\n---\n\n## Execution Plan\n",
        "EVIDENCE.md": "---\ntype: goal-evidence\n---\n\n## Verification Results\n",
    }
    for name, content in documents.items():
        (artifact_dir / name).write_text(content, encoding="utf-8")
    return [str((artifact_dir / name).relative_to(root)) for name in documents]


def complete_observations(manifest: dict, root: Path, *, runs: int = 2) -> dict:
    observations = []
    for run_number in range(runs):
        decisions = []
        for case in manifest["cases"]:
            run_id = f"run-{run_number + 1}"
            decision = {
                "case_id": case["id"],
                **deepcopy(case["expected"]),
                "artifact_paths": write_artifacts(root, run_id, case["id"], case["expected"]),
                "token_count": 100 + run_number,
            }
            decisions.append(decision)
        observations.append({"id": run_id, "observations": decisions})
    return {
        "version": 1,
        "manifest_version": 1,
        "skill_sha256": manifest["skill"]["sha256"],
        "observation_source": "model_runtime",
        "runtime": {"provider": "test"},
        "runs": observations,
    }


def test_versioned_goal_skill_eval_manifest_is_balanced_and_valid() -> None:
    manifest = load_manifest(MANIFEST)

    assert len(manifest["cases"]) == 16
    assert sum(case["expected"]["trigger"] for case in manifest["cases"]) == 8
    assert {case["language"] for case in manifest["cases"]} == {"zh_TW", "en"}


def test_skill_eval_scores_complete_model_observations_and_writes_a_report(capsys) -> None:
    root = make_workspace("skill-eval-complete")
    manifest_path, manifest = prepared_manifest(root)
    observations_path = root / "observations.json"
    observations_path.write_text(json.dumps(complete_observations(manifest, root)), encoding="utf-8")
    report_path = root / "report.json"

    report = evaluate(manifest_path, observations_path)

    assert report["status"] == "passed"
    assert report["baseline_ready"] is True
    assert report["aggregate"]["trigger_precision"] == 1.0
    assert report["aggregate"]["trigger_recall"] == 1.0
    assert report["token_usage"]["mean"] == 100.5
    assert report["variance"]["unstable_case_count"] == 0
    assert main(["--manifest", str(manifest_path), "--observations", str(observations_path), "--report", str(report_path)]) == 0
    assert '"baseline_ready": true' in capsys.readouterr().out
    assert json.loads(report_path.read_text(encoding="utf-8"))["baseline_ready"] is True


def test_skill_eval_reports_false_positive_and_cross_run_variance() -> None:
    root = make_workspace("skill-eval-variance")
    manifest_path, manifest = prepared_manifest(root)
    payload = complete_observations(manifest, root)
    payload["runs"][1]["observations"][8]["trigger"] = True
    observations_path = root / "observations.json"
    observations_path.write_text(json.dumps(payload), encoding="utf-8")

    report = evaluate(manifest_path, observations_path)

    assert report["status"] == "needs_evidence"
    assert report["aggregate"]["false_positive_count"] == 1
    assert report["variance"]["unstable_cases"] == ["zh-routine-bugfix"]


def test_skill_eval_rejects_missing_required_generated_artifacts() -> None:
    root = make_workspace("skill-eval-artifacts")
    manifest_path, manifest = prepared_manifest(root)
    payload = complete_observations(manifest, root)
    payload["runs"][0]["observations"][1]["artifact_paths"] = []
    observations_path = root / "observations.json"
    observations_path.write_text(json.dumps(payload), encoding="utf-8")

    report = evaluate(manifest_path, observations_path)

    assert report["baseline_ready"] is False
    assert report["runs"][0]["artifact_findings"][0]["case_id"] == "zh-standard-contract"


def test_skill_eval_without_observations_never_claims_a_semantic_baseline() -> None:
    root = make_workspace("skill-eval-awaiting")
    manifest_path, _ = prepared_manifest(root)

    report = evaluate(manifest_path)

    assert report["status"] == "awaiting_observations"
    assert report["baseline_ready"] is False


def test_empty_observation_template_is_awaiting_model_runs() -> None:
    root = make_workspace("skill-eval-empty-observations")
    manifest_path, manifest = prepared_manifest(root)
    observations = {
        "version": 1,
        "manifest_version": 1,
        "skill_sha256": manifest["skill"]["sha256"],
        "observation_source": "model_runtime",
        "runs": [],
    }
    observations_path = root / "observations.json"
    observations_path.write_text(json.dumps(observations), encoding="utf-8")

    report = evaluate(manifest_path, observations_path)

    assert report["status"] == "awaiting_observations"
    assert report["baseline_ready"] is False


def test_runtime_adapter_requires_explicit_model_execution_consent(capsys) -> None:
    root = make_workspace("skill-eval-runtime")
    manifest_path, manifest = prepared_manifest(root)

    assert len(plan_runs(manifest, 2)) == 32
    assert "Do not modify the supplied policy" in build_prompt("policy", "prompt")
    assert runtime_main(["--manifest", str(manifest_path), "--out", str(root / "run"), "--model", "gpt-5.6-terra", "--reasoning-effort", "high"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"
    assert runtime_main(["--manifest", str(manifest_path), "--out", str(root / "run"), "--execute"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "confirmation_required"
