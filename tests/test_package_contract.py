from __future__ import annotations

import tomllib
from pathlib import Path


def load_pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_distribution_has_reproducible_setuptools_build_contract() -> None:
    payload = load_pyproject()

    assert payload["build-system"] == {
        "requires": ["setuptools>=77"],
        "build-backend": "setuptools.build_meta",
    }
    assert payload["project"]["name"] == "goal-lifecycle-toolkit"
    assert payload["project"]["readme"] == "PACKAGE_README.md"
    assert payload["project"]["scripts"] == {"goal-lifecycle": "goal_lifecycle.cli:main"}


def test_distribution_installs_all_json_schemas_to_standard_share_path() -> None:
    payload = load_pyproject()

    assert payload["tool"]["setuptools"]["data-files"] == {
        "share/goal-lifecycle/schemas": ["schemas/*.json"]
    }


def test_distribution_discovers_only_src_packages() -> None:
    payload = load_pyproject()

    assert payload["tool"]["setuptools"]["packages"]["find"] == {"where": ["src"]}


def test_sdist_manifest_excludes_machine_local_operator_docs() -> None:
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    assert "include PACKAGE_README.md" in manifest
    assert "exclude README.md" in manifest
    assert "prune tests" in manifest
