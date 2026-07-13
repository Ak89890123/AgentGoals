from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


SKILL_ROOT_CANDIDATES = (
    Path("goals/active/agentgoals-product-rename/skill-package"),
    Path("goals/completed/agentgoals-product-rename/skill-package"),
)
SKILL_FIXTURES_AVAILABLE = any(path.is_dir() for path in SKILL_ROOT_CANDIDATES)


def agentgoals_skill_root() -> Path:
    return next(path for path in SKILL_ROOT_CANDIDATES if path.is_dir())


def test_distribution_uses_agentgoals_with_one_legacy_cli_alias() -> None:
    # Given: the package metadata after the public rename.
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    # When: distribution and console entry points are inspected.
    project = payload["project"]

    # Then: AgentGoals is canonical and the old executable delegates to it.
    assert project["name"] == "agentgoals"
    assert project["scripts"] == {
        "agentgoals": "agentgoals.cli:main",
        "goal-lifecycle": "agentgoals.cli:main",
    }


def test_agentgoals_is_the_implementation_and_legacy_import_is_an_alias() -> None:
    # Given: both public import paths during the compatibility window.
    canonical = importlib.import_module("agentgoals")
    legacy = importlib.import_module("goal_lifecycle")

    # When: their package identity and version are inspected.
    canonical_version = canonical.__version__

    # Then: the legacy package delegates to the canonical implementation.
    assert legacy.__version__ == canonical_version == "0.2.1"
    assert canonical.__file__ is not None
    assert Path(canonical.__file__).parent.name == "agentgoals"


def test_agentgoals_cli_reports_new_brand_and_legacy_program_name_is_optional(capsys) -> None:
    # Given: the canonical root CLI module.
    cli = importlib.import_module("agentgoals.cli")

    # When: the canonical version command runs.
    exit_code = cli.main(["--version"])

    # Then: output uses only the new public product name.
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "agentgoals 0.2.1"


@pytest.mark.skipif(
    not SKILL_FIXTURES_AVAILABLE,
    reason="local Goal Skill fixtures are intentionally outside the public checkout",
)
def test_agentgoals_skill_directories_are_staged_with_matching_frontmatter() -> None:
    # Given: the four accepted product-owned Skill capabilities.
    skill_root = agentgoals_skill_root()
    expected = ("ag-contract", "ag-onboarding", "ag-continue", "ag-end")

    # When: staged canonical Skill files are read.
    frontmatter_names = {
        name: f"name: {name}" in (skill_root / name / "SKILL.md").read_text(encoding="utf-8")
        for name in expected
    }

    # Then: physical directories and declared names agree.
    assert frontmatter_names == {name: True for name in expected}


@pytest.mark.skipif(
    not SKILL_FIXTURES_AVAILABLE,
    reason="local Goal Skill fixtures are intentionally outside the public checkout",
)
def test_agentgoals_skill_manifests_route_to_canonical_skill_names() -> None:
    # Given: the four canonical AgentGoals Skill packages.
    skill_root = agentgoals_skill_root()
    expected = ("ag-contract", "ag-onboarding", "ag-continue", "ag-end")

    # When: their agent manifests are inspected.
    manifests = {
        name: (skill_root / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
        for name in expected
    }

    # Then: every package exposes its canonical invocation name.
    assert all(f"${name}" in manifest for name, manifest in manifests.items())


def test_legacy_submodule_invocations_delegate_to_canonical_implementation() -> None:
    # Given: the bounded legacy module invocation routes.
    commands = (
        ("goal_lifecycle.cli", "--version"),
        ("goal_lifecycle.onboard", "--help"),
    )

    # When: each legacy submodule is launched through the current interpreter.
    results = [
        subprocess.run(
            [sys.executable, "-m", module, argument],
            check=False,
            capture_output=True,
            text=True,
        )
        for module, argument in commands
    ]

    # Then: runpy executes the compatibility route without a loader mismatch.
    assert [result.returncode for result in results] == [0, 0]
    assert results[0].stdout.strip() == "agentgoals 0.2.1"
