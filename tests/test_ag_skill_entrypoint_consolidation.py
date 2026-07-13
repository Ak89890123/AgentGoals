from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

GOAL = Path("goals/active/ag-skill-entrypoint-consolidation")
BACKUP = GOAL / "installation-backup"
PERSONAL_BACKUP = Path(".goal-lifecycle/private/ag-skill-entrypoint-consolidation/pre-consolidation")
pytestmark = pytest.mark.skipif(
    not GOAL.is_dir() or not PERSONAL_BACKUP.is_dir(),
    reason="local public/private Skill fixtures are intentionally outside the public checkout",
)

LEGACY_NAMES = ("goal-preflight", "goal-onboarding", "aab-jixu", "aaa-shougong")
CANONICAL_NAMES = ("ag-contract", "ag-onboarding", "ag-continue", "ag-end")

DEPENDENT_REPLACEMENTS = {
    "ceo-agent/SKILL.md": (("goal-preflight", "ag-contract"), ("aaa-shougong", "ag-end")),
    "ceo-agent/agents/openai.yaml": (("goal-preflight", "ag-contract"),),
    "global-dev-team/SKILL.md": (("goal-preflight", "ag-contract"),),
    "aac-worktree/SKILL.md": (("aaa-shougong", "ag-end"),),
    "second-brain-agent/SKILL.md": (("aaa-shougong", "ag-end"),),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_canonical_core_candidates_use_only_ag_names() -> None:
    for name in CANONICAL_NAMES:
        text = read(GOAL / "skill-package" / name / "SKILL.md")
        assert f"name: {name}" in text
        assert not any(legacy in text for legacy in LEGACY_NAMES)


def test_dependent_candidates_are_name_only_rewrites() -> None:
    for relative, replacements in DEPENDENT_REPLACEMENTS.items():
        expected = (BACKUP / "dependents" / relative).read_bytes()
        for old, new in replacements:
            old_bytes = old.encode("utf-8")
            new_bytes = new.encode("utf-8")
            assert old_bytes in expected
            expected = expected.replace(old_bytes, new_bytes)

        candidate = (GOAL / "routing-candidates" / relative).read_bytes()
        assert candidate == expected
        assert not any(legacy.encode("utf-8") in candidate for legacy in LEGACY_NAMES)


def test_rtk_candidate_is_one_exact_name_rewrite() -> None:
    baseline = (BACKUP / "pre-consolidation" / "RTK.md").read_bytes()
    assert baseline.count(b"goal-preflight") == 1
    candidate = (GOAL / "rtk-candidate" / "RTK.md").read_bytes()
    assert candidate == baseline.replace(b"goal-preflight", b"ag-contract")


def test_agents_candidate_preserves_gate_for_all_canonical_core_skills() -> None:
    baseline = (BACKUP / "repository" / "AGENTS.md").read_bytes()
    old = br"- Do not edit `C:\Users\jimmy0302\.codex\skills\goal-preflight` from this harness until there is a proposal, independent review, explicit approval, patch, and verification."
    new = br"- Do not edit the global AgentGoals core Skills (`C:\Users\jimmy0302\.codex\skills\ag-contract`, `C:\Users\jimmy0302\.codex\skills\ag-onboarding`, `C:\Users\jimmy0302\.codex\skills\ag-continue`, or `C:\Users\jimmy0302\.codex\skills\ag-end`) from this harness until there is a proposal, independent review, explicit approval, patch, and verification."
    assert baseline.count(old) == 1
    candidate = (GOAL / "policy-candidate" / "AGENTS.md").read_bytes()
    assert candidate == baseline.replace(old, new)


def test_ag_onboarding_public_candidate_is_byte_identical_to_baseline() -> None:
    baseline = (BACKUP / "pre-consolidation" / "ag-onboarding" / "SKILL.md").read_bytes()
    candidate = (GOAL / "skill-package" / "ag-onboarding" / "SKILL.md").read_bytes()
    assert candidate == baseline


def test_operation_ledger_is_bounded_and_non_recursive() -> None:
    ledger = read(GOAL / "reviews" / "OPERATION-LEDGER.md")
    assert "SUPERSEDED Operation Ledger" in ledger
    assert "DO NOT APPLY" in ledger
    assert "43 legacy files" in ledger
    assert "10 verified-empty directories" in read(GOAL / "reviews" / "INSTALL-REVIEW.md")
    assert "Never use recursive deletion" in ledger
    assert "Section B: Separate RTK Approval" in ledger
    assert "The old `reviews/OPERATION-LEDGER.md` is superseded" in read(GOAL / "CONTRACT.md")

    legacy_sources = {
        name: (PERSONAL_BACKUP / name if name in {"goal-preflight", "aab-jixu", "aaa-shougong"} else BACKUP / "pre-consolidation" / name)
        for name in LEGACY_NAMES
    }
    legacy_files = [
        path
        for name in LEGACY_NAMES
        for path in legacy_sources[name].rglob("*")
        if path.is_file()
    ]
    assert len(legacy_files) == 43
    for skill in LEGACY_NAMES:
        for path in legacy_sources[skill].rglob("*"):
            if path.is_file():
                relative = path.relative_to(legacy_sources[skill])
                assert str(relative).replace("/", "\\") in ledger

    expected_removed_dirs = (
        "goal-preflight\\agents",
        "goal-preflight\\backups",
        "goal-preflight\\references",
        "goal-preflight",
        "goal-onboarding\\agents",
        "goal-onboarding",
        "aab-jixu\\agents",
        "aab-jixu",
        "aaa-shougong\\agents",
        "aaa-shougong",
    )
    for relative in expected_removed_dirs:
        assert f"skills\\{relative}`" in ledger


def test_candidate_hashes_are_recorded_in_inventory_and_ledger() -> None:
    inventory = read(GOAL / "reviews" / "INVENTORY.md")
    ledger = read(GOAL / "reviews" / "OPERATION-LEDGER.md")
    candidates = (
        GOAL / "skill-package" / "ag-onboarding" / "SKILL.md",
        *(GOAL / "routing-candidates" / relative for relative in DEPENDENT_REPLACEMENTS),
        GOAL / "rtk-candidate" / "RTK.md",
        GOAL / "policy-candidate" / "AGENTS.md",
    )
    for candidate in candidates:
        digest = sha256(candidate)
        assert digest in inventory
        assert digest in ledger


def test_policy_candidate_scopes_supersession_to_skill_directories() -> None:
    policy = read(GOAL / "policy-candidate" / "docs" / "migration-agentgoals.md")
    assert "SUPERSEDED CANDIDATE" in policy
    assert "the only active AgentGoals core Skill entry points" in policy
    assert "no forwarding Skill remains active" in policy
    assert "legacy executable and import aliases retain the compatibility schedule" in policy


def test_contract_separates_public_core_from_private_three_skill_pack() -> None:
    contract = read(GOAL / "CONTRACT.md")
    assert "generic, GitHub-ready AgentGoals core" in contract
    assert "private Desktop package" in contract
    assert "Expected legacy payload: 41 source files" in contract
    assert "PERSONAL / NOT FOR PUBLIC RELEASE" in contract
    assert "The old `goal-onboarding` Skill is not part" in contract
    assert "same behavior" in contract
    assert "Do not retain optional integration hooks" in contract
    assert "confirmed for retirement" in contract
    assert "separate future Goal" in contract
    assert "`ag-continue` reads the root and nearest applicable `AGENTS.md`" in contract
    assert "`ag-end` may update the applicable `AGENTS.md`" in contract
    assert "`AGENTS.md` is repository policy, not a Memory store" in contract

    personal_sources = sum(
        1
        for name in ("goal-preflight", "aab-jixu", "aaa-shougong")
        for path in (PERSONAL_BACKUP / name).rglob("*")
        if path.is_file()
    )
    assert personal_sources == 41
