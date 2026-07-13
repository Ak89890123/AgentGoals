from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_reconcile import make_workspace, write_registry


def run_module(repo: Path, module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path("src").resolve())
    environment["TEMP"] = str(Path(".tmp").resolve())
    environment["TMP"] = environment["TEMP"]
    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_artifact_cli_smoke_runs_preview_apply_audit_and_lifecycle_validation() -> None:
    repo = make_workspace("artifact-e2e-smoke")
    artifact_root = repo / "goals" / "active"
    decision_path = repo / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "version": 1,
                "goal_id": "smoke-goal",
                "title": "Smoke Goal",
                "project": "smoke",
                "owner": "engineering",
                "date": "2026-07-12",
                "size": "standard",
                "layout": "single_file",
                "file_write": True,
                "review_required": False,
            }
        ),
        encoding="utf-8",
    )

    preview = run_module(repo, "agentgoals.artifact_tool", "--repo-root", str(repo.resolve()), "--artifact-root", str(artifact_root.resolve()), "--decision", str(decision_path.resolve()))
    assert preview.returncode == 0, preview.stderr
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["status"] == "preview"
    assert not (artifact_root / "smoke-goal-goal-contract.md").exists()

    applied = run_module(repo, "agentgoals.artifact_tool", "--repo-root", str(repo.resolve()), "--artifact-root", str(artifact_root.resolve()), "--decision", str(decision_path.resolve()), "--apply", "--audit")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["status"] == "applied"
    assert (artifact_root / "smoke-goal-goal-contract.md").is_file()

    listed = run_module(repo, "agentgoals.artifact_audit", "--repo-root", str(repo.resolve()), "--list-receipts", "--goal-id", "smoke-goal")
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout)["receipts"][0]["status"] == "applied"

    registry = repo / "registry" / "REGISTRY.json"
    write_registry(registry, repo / "goals")
    reconciled = run_module(repo, "agentgoals.reconcile", "--registry", str(registry.resolve()), "--out", str((repo / "outputs").resolve()))
    assert reconciled.returncode == 0, reconciled.stderr
    validated = run_module(repo, "agentgoals.validate", "--registry", str(registry.resolve()), "--state", str((repo / "outputs" / "STATE.json").resolve()))
    assert validated.returncode == 0, validated.stderr
