from __future__ import annotations

import json
from pathlib import Path

import agentgoals.refresh as refresh_module
from agentgoals.run import RunSummary
from tests.test_reconcile import make_workspace


def prepare_repo(tmp_path: Path, *, local_out: str = "outputs/goal-lifecycle") -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "registry").mkdir(parents=True)
    (repo / "goals").mkdir()
    (repo / "registry" / "REGISTRY.json").write_text(
        json.dumps({"version": 1, "updated": "2026-07-13", "roots": []}), encoding="utf-8"
    )
    global_registry = tmp_path / "config" / "REGISTRY.json"
    global_registry.parent.mkdir()
    state_path = repo / local_out / "STATE.json"
    global_registry.write_text(json.dumps({
        "version": 1,
        "updated": "2026-07-13",
        "roots": [{
            "id": "repo", "label": "repo", "repo_root": repo.resolve().as_posix(),
            "goal_root": (repo / "goals").resolve().as_posix(),
            "state_path": state_path.resolve().as_posix(), "scope": "repo",
            "project": "test", "active": True, "added": "2026-07-13", "last_seen": None,
        }],
    }), encoding="utf-8")
    return repo.resolve(), global_registry.resolve()


def test_refresh_derives_onboarded_state_path_and_requires_global_visibility(monkeypatch, capsys) -> None:
    repo, global_registry = prepare_repo(make_workspace("refresh-onboarded"))
    observed: dict[str, object] = {}

    def fake_run_pipeline(**kwargs):
        observed.update(kwargs)
        return RunSummary(version=1, status="passed", exit_code=0, stages=[], operation_id="refresh-op")

    monkeypatch.setattr(refresh_module, "run_pipeline", fake_run_pipeline)
    exit_code = refresh_module.main([
        "--repo", str(repo), "--global-registry", str(global_registry), "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert observed == {
        "registry_path": repo / "registry" / "REGISTRY.json",
        "out_dir": repo / "outputs" / "goal-lifecycle",
        "global_registry_path": global_registry,
        "global_out_dir": repo / "outputs" / "global",
        "require_global": True,
    }
    assert payload["operation_id"] == "refresh-op"


def test_refresh_accepts_legacy_local_output_with_global_child(monkeypatch, capsys) -> None:
    repo, global_registry = prepare_repo(make_workspace("refresh-legacy"), local_out="outputs")
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        refresh_module,
        "run_pipeline",
        lambda **kwargs: observed.update(kwargs)
        or RunSummary(version=1, status="passed", exit_code=0, stages=[], operation_id="legacy-op"),
    )
    assert refresh_module.main(["--repo", str(repo), "--global-registry", str(global_registry)]) == 0
    assert observed["out_dir"] == repo / "outputs"
    assert observed["global_out_dir"] == repo / "outputs" / "global"


def test_refresh_requires_explicit_global_registry(capsys) -> None:
    exit_code = refresh_module.main(["--repo", "relative", "--json"])
    assert exit_code == 1
    assert "--global-registry" in capsys.readouterr().err


def test_refresh_rejects_relative_paths_before_pipeline(monkeypatch, capsys) -> None:
    monkeypatch.setattr(refresh_module, "run_pipeline", lambda **_: (_ for _ in ()).throw(AssertionError()))
    assert refresh_module.main(["--repo", "relative", "--global-registry", "relative.json"]) == 1
    assert "absolute" in capsys.readouterr().err


def test_refresh_rejects_global_registry_inside_outputs(monkeypatch, capsys) -> None:
    repo, _ = prepare_repo(make_workspace("refresh-collision"))
    registry = repo / "outputs" / "REGISTRY.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    state = repo / "outputs" / "goal-lifecycle" / "STATE.json"
    registry.write_text(json.dumps({"version": 1, "updated": "2026-07-13", "roots": [{
        "id": "repo", "label": "repo", "repo_root": repo.as_posix(),
        "goal_root": (repo / "goals").as_posix(), "state_path": state.as_posix(),
        "scope": "repo", "project": "test", "active": True,
        "added": "2026-07-13", "last_seen": None,
    }]}), encoding="utf-8")
    monkeypatch.setattr(refresh_module, "run_pipeline", lambda **_: (_ for _ in ()).throw(AssertionError()))
    assert refresh_module.main(["--repo", str(repo), "--global-registry", str(registry)]) == 1
    assert "derived outputs" in capsys.readouterr().err


def test_refresh_rejects_registered_state_outside_outputs(monkeypatch, capsys) -> None:
    root = make_workspace("refresh-state-outside-outputs")
    repo, global_registry = prepare_repo(root, local_out="registry/local-state")
    monkeypatch.setattr(refresh_module, "run_pipeline", lambda **_: (_ for _ in ()).throw(AssertionError()))
    assert refresh_module.main(["--repo", str(repo), "--global-registry", str(global_registry)]) == 1
    assert "registered local output" in capsys.readouterr().err
