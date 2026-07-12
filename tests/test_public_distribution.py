from __future__ import annotations

from pathlib import Path


def test_readme_documents_path_free_cli_install_and_rollback() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "goal-lifecycle onboard --repo" in readme
    assert "goal-lifecycle doctor --json" in readme
    assert "uv tool install" in readme
    assert "pipx install" in readme
    assert "uv tool uninstall goal-lifecycle-toolkit" in readme
    assert "pipx uninstall goal-lifecycle-toolkit" in readme


def test_onboarding_guide_uses_installed_cli_for_normal_workflow() -> None:
    guide = Path("docs/onboarding.md").read_text(encoding="utf-8")
    normal_commands = guide.split("## Developer Checkout Fallback", maxsplit=1)[0]

    assert "goal-lifecycle doctor --json" in normal_commands
    assert "goal-lifecycle onboard" in normal_commands
    assert "goal_lifecycle.onboard" not in normal_commands
    assert "PYTHONPATH" not in normal_commands


def test_package_ci_checks_build_metadata_and_isolated_tool_installers() -> None:
    workflow = Path(".github/workflows/package.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "python -m pytest" in workflow
    assert "python -m build" in workflow
    assert "twine check" in workflow
    assert "pipx install" in workflow
    assert "uv tool install" in workflow
    assert "goal-lifecycle --version" in workflow
    assert "goal-lifecycle doctor --json" in workflow
