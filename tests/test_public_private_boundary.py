from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml
import pytest


VERIFY_PATH = Path("goals/active/ag-skill-entrypoint-consolidation/scripts/verify_public_private_boundary.py")
if not VERIFY_PATH.is_file():
    pytest.skip("local public/private Skill fixtures are intentionally outside the public checkout", allow_module_level=True)
VERIFY_SPEC = spec_from_file_location("verify_public_private_boundary", VERIFY_PATH)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY_MODULE = module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY_MODULE)


def test_public_private_boundary_verifier_passes() -> None:
    result = VERIFY_MODULE.verify()

    assert result["status"] == "passed"
    assert result["public"]["file_count"] == 13
    assert result["public"]["manifest_sha256"]
    assert result["personal"]["source_file_count"] == 41
    assert result["personal"]["package_file_count"] == 43


def test_clean_core_keeps_repository_policy_without_private_surfaces() -> None:
    root = Path("goals/active/ag-skill-entrypoint-consolidation/skill-package")
    continue_text = (root / "ag-continue/SKILL.md").read_text(encoding="utf-8")
    end_text = (root / "ag-end/SKILL.md").read_text(encoding="utf-8")

    assert "AGENTS.md" in continue_text
    assert "AGENTS.md" in end_text
    for forbidden in (
        "AgentMemory",
        "Second Brain",
        "Obsidian",
        "Codebase Memory",
        "ai-company-os-routing",
        "goal-preflight",
        "aab-jixu",
        "aaa-shougong",
    ):
        assert forbidden not in continue_text
        assert forbidden not in end_text


def test_continue_and_end_behavior_contract_is_explicit() -> None:
    root = Path("goals/active/ag-skill-entrypoint-consolidation/skill-package")
    continue_text = (root / "ag-continue/SKILL.md").read_text(encoding="utf-8")
    end_text = (root / "ag-end/SKILL.md").read_text(encoding="utf-8")
    continue_normalized = " ".join(continue_text.split())
    end_normalized = " ".join(end_text.split()).lower()

    assert "root `AGENTS.md` and any applicable module-level `AGENTS.md`" in continue_text
    assert "nearest module guide supplies more local rules without replacing the root guide" in continue_normalized
    assert "read-only assessment" in continue_text
    assert "preserve unrelated edits" in end_normalized
    assert "no-op" in end_text
    for forbidden_handoff_detail in (
        "do not add raw logs",
        "temporary wip",
        "session summaries",
        "personal preferences",
    ):
        assert forbidden_handoff_detail in end_normalized
    assert "does not call external knowledge stores" in end_text


def test_public_skill_metadata_is_valid_and_explicitly_named() -> None:
    root = Path("goals/active/ag-skill-entrypoint-consolidation/skill-package")
    expected = ("ag-contract", "ag-onboarding", "ag-continue", "ag-end")

    for skill in expected:
        skill_path = root / skill / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        _, raw_frontmatter, _ = text.split("---\n", 2)
        frontmatter = yaml.safe_load(raw_frontmatter)
        assert frontmatter["name"] == skill
        assert frontmatter["description"]

        metadata_path = root / skill / "agents/openai.yaml"
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        assert metadata["interface"]["display_name"]


def test_desktop_preview_is_read_only_and_exact() -> None:
    preview = Path(
        "goals/active/ag-skill-entrypoint-consolidation/reviews/DESKTOP-DESTINATION-PREVIEW.md"
    ).read_text(encoding="utf-8")

    assert "Status: `preview_only`" in preview
    assert "C:\\Users\\jimmy0302\\Desktop" in preview
    assert "Target directory already exists: `False`" in preview
    assert "Target ZIP already exists: `False`" in preview
    assert "`45` filesystem writes" in preview


def test_public_release_preview_contains_only_the_reviewed_core() -> None:
    root = Path(".goal-lifecycle/public-release-preview/AgentGoals-Core-Skills-2026-07-13")
    files = {path.relative_to(root / "skills").as_posix() for path in (root / "skills").rglob("*") if path.is_file()}

    assert len(files) == 13
    assert (root / "MANIFEST.sha256").is_file()
    assert not any("goal-preflight" in path or "aaa-shougong" in path for path in files)
