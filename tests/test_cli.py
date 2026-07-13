from __future__ import annotations

import agentgoals.cli as cli_module


def test_root_cli_reports_stable_version(capsys) -> None:
    exit_code = cli_module.main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "agentgoals 0.2.1"


def test_root_cli_delegates_onboard_without_rewriting_arguments(monkeypatch) -> None:
    observed: list[str] = []

    def fake_onboard(argv):
        observed.extend(argv)
        return 2

    monkeypatch.setattr(cli_module.onboard, "main", fake_onboard)

    exit_code = cli_module.main(["onboard", "--repo", "C:/repo with spaces", "--json"])

    assert exit_code == 2
    assert observed == ["--repo", "C:/repo with spaces", "--json"]


def test_root_cli_delegates_doctor(monkeypatch) -> None:
    observed: list[str] = []

    def fake_doctor(argv):
        observed.extend(argv)
        return 0

    monkeypatch.setattr(cli_module.doctor, "main", fake_doctor)

    assert cli_module.main(["doctor", "--json"]) == 0
    assert observed == ["--json"]


def test_root_cli_delegates_refresh_without_semantic_routing(monkeypatch) -> None:
    observed: list[str] = []

    monkeypatch.setattr(cli_module.refresh, "main", lambda argv: observed.extend(argv) or 0)

    exit_code = cli_module.main(
        ["refresh", "--repo", "C:/repo", "--global-registry", "C:/config/REGISTRY.json", "--json"]
    )

    assert exit_code == 0
    assert observed == ["--repo", "C:/repo", "--global-registry", "C:/config/REGISTRY.json", "--json"]


def test_root_cli_delegates_complete_without_semantic_routing(monkeypatch) -> None:
    observed: list[str] = []
    monkeypatch.setattr(cli_module.complete, "main", lambda argv: observed.extend(argv) or 0)
    assert cli_module.main(["complete", "--repo", "C:/repo", "--goal-id", "done-goal"]) == 0
    assert observed == ["--repo", "C:/repo", "--goal-id", "done-goal"]


def test_root_cli_without_command_prints_help(capsys) -> None:
    assert cli_module.main([]) == 0
    output = capsys.readouterr().out
    assert "onboard" in output
    assert "refresh" in output
    assert "complete" in output


def test_launcher_compatibility_handshake_delegates_in_one_process(monkeypatch) -> None:
    observed = []
    monkeypatch.setattr(cli_module.onboard, "main", lambda argv: observed.extend(argv) or 0)

    assert cli_module.main(["--launcher-schema", "1", "--toolkit-major", "0", "onboard", "--repo", "/repo"]) == 0
    assert observed == ["--repo", "/repo"]


def test_launcher_compatibility_handshake_fails_closed() -> None:
    assert cli_module.main(["--launcher-schema", "2", "--toolkit-major", "0", "onboard"]) == 1
    assert cli_module.main(["--launcher-schema", "1", "--toolkit-major", "9", "onboard"]) == 1
