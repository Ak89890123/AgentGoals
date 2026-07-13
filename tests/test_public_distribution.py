from __future__ import annotations

import re
from pathlib import Path


PUBLIC_TEXT_SURFACES = (
    Path("README.md"),
    Path("PACKAGE_README.md"),
    *sorted(Path("docs").rglob("*.md")),
)
FORBIDDEN_PUBLIC_PATH_PATTERNS = (
    re.compile(rb"(?i)\b[a-z]:[\\/](?:devhome|users|home|runner)[\\/]"),
    re.compile(rb"(?i)/(?:users|home|runner|workspaces)/"),
)
FORBIDDEN_CONCRETE_GOAL_PATH_PATTERN = re.compile(
    r"(?i)goals[\\/](?:active|completed)[\\/][a-z0-9][^`\s/\\]*[\\/]"
)


def test_readme_documents_path_free_cli_install_and_rollback() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "agentgoals onboard --repo" in readme
    assert "agentgoals doctor --json" in readme
    assert "uv tool install" in readme
    assert "pipx install" in readme
    assert "github.com/Ak89890123/AgentGoals.git@<TAG>" in readme
    assert "uv tool uninstall agentgoals" in readme
    assert "pipx uninstall agentgoals" in readme
    assert "goal-lifecycle" in readme
    assert "goals/completed/" not in readme


def test_onboarding_guide_uses_installed_cli_for_normal_workflow() -> None:
    guide = Path("docs/onboarding.md").read_text(encoding="utf-8")
    normal_commands = guide.split("## Developer Checkout Fallback", maxsplit=1)[0]

    assert "agentgoals doctor --json" in normal_commands
    assert "agentgoals onboard" in normal_commands
    assert "goal_lifecycle.onboard" not in normal_commands
    assert "PYTHONPATH" not in normal_commands


def test_public_documentation_contains_no_machine_local_paths() -> None:
    for path in PUBLIC_TEXT_SURFACES:
        payload = path.read_bytes()
        assert not any(pattern.search(payload) for pattern in FORBIDDEN_PUBLIC_PATH_PATTERNS), path


def test_public_documentation_contains_no_concrete_excluded_goal_paths() -> None:
    for path in PUBLIC_TEXT_SURFACES:
        text = path.read_text(encoding="utf-8")
        assert not FORBIDDEN_CONCRETE_GOAL_PATH_PATTERN.search(text), path


def test_package_ci_checks_build_metadata_and_isolated_tool_installers() -> None:
    workflow = Path(".github/workflows/package.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "python -m pytest" in workflow
    assert "python -m build" in workflow
    assert "twine check" in workflow
    assert "package-cross-platform:" in workflow
    assert "matrix.os" in workflow
    assert "scripts/package_smoke.py --dist-dir dist --artifact wheel" in workflow
    assert "scripts/package_smoke.py --dist-dir dist --artifact sdist" in workflow
    assert "pipx install" in workflow
    assert "uv tool install" in workflow
    assert "agentgoals --version" in workflow
    assert "agentgoals doctor --json" in workflow
    assert "goal-lifecycle --version" in workflow


def test_release_candidate_notes_and_artifact_verifier_are_wired() -> None:
    notes = Path("docs/releases/agentgoals-0.2.1.md").read_text(encoding="utf-8")
    verifier = Path("scripts/verify_package_artifacts.py").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/package.yml").read_text(encoding="utf-8")

    assert "repo-local candidate only" in notes
    assert "agentgoals-0.2.1-py3-none-any.whl" in notes
    assert "github.com/Ak89890123/AgentGoals.git@<TAG>" in notes
    assert "goal-lifecycle-toolkit" in notes
    assert "SECRET_PATTERNS" in verifier
    assert "scripts/verify_package_artifacts.py --dist-dir dist" in workflow
    assert "Install sdist in a disposable environment" in workflow
