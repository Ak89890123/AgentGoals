from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentgoals.session_eval import apply_patch_in_memory, contract_frontmatter, evaluate_instruction_preservation, materialize_patch_target, proposed_additions, utf8_stats, verify_patch_contexts
from tests.test_reconcile import make_workspace


def test_utf8_stats_are_byte_and_hash_stable() -> None:
    assert utf8_stats("Goal 交接") == {
        "bytes": 11,
        "sha256": "71fab1c083a9fb46ca6098055b4d1e4006062bd3534bae020a9f53b070966e8b",
    }


def test_contract_frontmatter_returns_only_authoritative_metadata() -> None:
    contract = make_workspace("session-eval-frontmatter") / "CONTRACT.md"
    contract.write_text("---\nid: focus\nstatus: draft\n---\n\n# Body\nsecret body\n", encoding="utf-8")

    assert contract_frontmatter(contract) == "---\nid: focus\nstatus: draft\n---\n"


def test_proposed_additions_extracts_only_named_target() -> None:
    patch = make_workspace("session-eval-patch") / "proposal.patch"
    patch.write_text(
        "*** Begin Patch\n"
        "*** Update File: first/SKILL.md\n"
        "@@\n"
        "+first addition\n"
        "*** Update File: second/SKILL.md\n"
        "@@\n"
        "+second addition\n"
        "*** End Patch\n",
        encoding="utf-8",
    )

    assert proposed_additions(patch, "first/SKILL.md") == "first addition\n"
    assert proposed_additions(patch, "second/SKILL.md") == "second addition\n"


def test_contract_frontmatter_rejects_unclosed_metadata() -> None:
    contract = make_workspace("session-eval-unclosed") / "CONTRACT.md"
    contract.write_text("---\nid: focus\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not closed"):
        contract_frontmatter(contract)


def test_patch_context_verification_detects_matching_and_drifted_targets() -> None:
    root = make_workspace("session-eval-contexts")
    target = (root / "SKILL.md").resolve()
    target.write_text("---\nname: test\ndescription: test\n---\n\n# Skill\n\n## Rules\n\n- Keep this.\n", encoding="utf-8")
    patch = root / "proposal.patch"
    patch.write_text(
        "*** Begin Patch\n"
        f"*** Update File: {target}\n"
        "@@\n"
        " ## Rules\n"
        " \n"
        " - Keep this.\n"
        "+- Add this.\n"
        "*** End Patch\n",
        encoding="utf-8",
    )

    assert verify_patch_contexts(patch)["valid"] is True
    assert "- Add this." in apply_patch_in_memory(patch, str(target))
    assert materialize_patch_target(patch, str(target))[1] == "applicable"
    target.write_text(apply_patch_in_memory(patch, str(target)), encoding="utf-8")
    assert materialize_patch_target(patch, str(target))[1] == "already_applied"
    target.write_text("# Drifted\n", encoding="utf-8")
    assert verify_patch_contexts(patch)["valid"] is False


def test_patch_application_rejects_ambiguous_context() -> None:
    root = make_workspace("session-eval-ambiguous")
    target = (root / "SKILL.md").resolve()
    target.write_text("---\nname: test\ndescription: test\n---\n\n## Rules\n\n## Rules\n", encoding="utf-8")
    patch = root / "proposal.patch"
    patch.write_text(
        "*** Begin Patch\n"
        f"*** Update File: {target}\n"
        "@@\n"
        " ## Rules\n"
        "+added\n"
        "*** End Patch\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="matched 2 locations"):
        apply_patch_in_memory(patch, str(target))


def test_patch_verification_rejects_frontmatter_changes() -> None:
    root = make_workspace("session-eval-frontmatter-change")
    target = (root / "SKILL.md").resolve()
    target.write_text("---\nname: old\ndescription: test\n---\n\n# Skill\n", encoding="utf-8")
    patch = root / "proposal.patch"
    patch.write_text(
        "*** Begin Patch\n"
        f"*** Update File: {target}\n"
        "@@\n"
        "-name: old\n"
        "+name: new\n"
        "*** End Patch\n",
        encoding="utf-8",
    )

    result = verify_patch_contexts(patch)
    assert result["valid"] is False
    assert result["targets"][0]["frontmatter_unchanged"] is False


@pytest.mark.skipif(
    not Path("goals/completed/goal-session-handoff-integration/patches/END-aab-jixu.apply_patch").is_file(),
    reason="local historical Skill fixtures are intentionally outside the public checkout",
)
def test_versioned_skill_instruction_preservation_cases_pass_against_exact_proposal() -> None:
    # Given: immutable pre-install Skill backups and the exact reviewed patch.
    root = make_workspace("session-eval-versioned-proposal")
    patch_source = Path("goals/completed/goal-session-handoff-integration/patches/END-aab-jixu.apply_patch")
    fixture_source = Path("fixtures/session_handoff/skill-behavior-cases.json")
    replacements = {
        r"C:\Users\jimmy0302\.codex\skills\aab-jixu\SKILL.md": str(
            Path("goals/completed/goal-session-handoff-integration/backups/2026-07-11-beb39c40/aab-jixu.SKILL.md").resolve()
        ),
        r"C:\Users\jimmy0302\.codex\skills\aaa-shougong\SKILL.md": str(
            Path("goals/completed/goal-session-handoff-integration/backups/2026-07-11-beb39c40/aaa-shougong.SKILL.md").resolve()
        ),
    }
    patch_text = patch_source.read_text(encoding="utf-8")
    fixture = json.loads(fixture_source.read_text(encoding="utf-8"))
    for installed_path, backup_path in replacements.items():
        patch_text = patch_text.replace(installed_path, backup_path)
        for case in fixture["cases"]:
            if case["skill_target"] == installed_path:
                case["skill_target"] = backup_path
    patch_path = root / "proposal.patch"
    cases_path = root / "cases.json"
    patch_path.write_text(patch_text, encoding="utf-8")
    cases_path.write_text(json.dumps(fixture), encoding="utf-8")

    # When: instruction preservation is evaluated without reading mutable global Skills.
    result = evaluate_instruction_preservation(
        patch_path,
        cases_path,
    )

    # Then: the immutable proposal still satisfies every versioned behavior case.
    assert result["version"] == 1
    assert result["case_count"] == 6
    assert result["passed"] is True


def test_immutable_context_transcript_meets_efficiency_target() -> None:
    baseline = Path("fixtures/session_handoff/baseline-context.txt").read_text(encoding="utf-8")
    candidate = Path("fixtures/session_handoff/candidate-context.txt").read_text(encoding="utf-8")

    baseline_stats = utf8_stats(baseline)
    candidate_stats = utf8_stats(candidate)
    assert baseline_stats == {
        "bytes": 3030,
        "sha256": "36f3fcf2cddc6e35ff1ab3079cf1d213384c470cf0d46375eee0f9afb9bd2fb0",
    }
    assert candidate_stats == {
        "bytes": 1130,
        "sha256": "fd39c6d47469e2d38b91722fdf4be3f5c8e8f8ecdbe7f48af3c9e4a748dd91a8",
    }
    assert candidate_stats["bytes"] <= baseline_stats["bytes"] * 0.5
