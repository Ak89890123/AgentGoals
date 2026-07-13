from __future__ import annotations

from pathlib import Path
import importlib.util

import pytest


SKILL = Path(
    "goals/completed/single-approval-global-onboarding-registration/skill-package/ag-onboarding/SKILL.md"
)
MANIFEST = Path(
    "goals/completed/single-approval-global-onboarding-registration/skill-package/ag-onboarding/agents/openai.yaml"
)
HELPER = Path(
    "goals/completed/single-approval-global-onboarding-registration/skill-package/ag-onboarding/scripts/build_single_approval_invocation.py"
)
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (SKILL, MANIFEST, HELPER)),
    reason="local Goal Skill fixtures are intentionally outside the public checkout",
)


def load_helper():
    spec = importlib.util.spec_from_file_location("single_approval_invocation", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_staged_ag_onboarding_requires_one_exact_registration_authorization() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "name: ag-onboarding" in text
    assert "$ag-onboarding" in text
    assert "--apply --register --registration-plan-sha256 <registration.plan_sha256> --global-registry <absolute-registry> --json" in text
    assert text.count("one explicit approval") == 1
    assert "Do not ask a second question for registration" in text
    assert "recovery_required" in text


def test_staged_ag_onboarding_is_explicit_only_and_has_ui_metadata() -> None:
    skill_text = SKILL.read_text(encoding="utf-8")
    manifest_text = MANIFEST.read_text(encoding="utf-8")

    assert "allow_implicit_invocation: false" in manifest_text
    assert "display_name: \"AG Onboarding\"" in manifest_text
    assert "default_prompt: \"Use $ag-onboarding" in manifest_text
    assert "Never manually edit a global registry from this Skill" in skill_text


def test_single_approval_helper_emits_one_exact_bound_invocation() -> None:
    helper = load_helper()
    payload = {
        "version": 1,
        "outcome": "dry_run_ready",
        "target_repo": "C:\\repos\\repo with spaces",
        "registration": {
            "requested": False,
            "authorized": False,
            "status": "not_requested",
            "global_registry_path": "C:\\config\\REGISTRY.json",
            "before_sha256": "b" * 64,
            "plan_sha256": "a" * 64,
            "proposed_entry": {
                "id": "repo",
                "label": "Repo",
                "repo_root": "C:\\repos\\repo with spaces",
                "goal_root": "C:\\repos\\repo with spaces\\goals",
                "state_path": "C:\\repos\\repo with spaces\\outputs\\STATE.json",
                "scope": "repo",
                "project": "repo",
                "active": True,
                "added": "2026-07-13",
                "last_seen": None,
            },
            "planned_write_set": [
                "C:\\config\\REGISTRY.json",
                "C:\\config\\.REGISTRY.json.agentgoals.lock",
            ],
            "condition": "registration is published only after validation",
        },
    }

    result = helper.build_invocation(payload)

    assert result["human_authorization_requests"] == 1
    assert result["authorization_scope"]["plan_sha256"] == "a" * 64
    assert result["argv"] == [
        "onboard",
        "--repo",
        "C:\\repos\\repo with spaces",
        "--apply",
        "--register",
        "--registration-plan-sha256",
        "a" * 64,
        "--global-registry",
        "C:\\config\\REGISTRY.json",
        "--json",
    ]


def test_single_approval_helper_rejects_schema_incomplete_write_scope() -> None:
    helper = load_helper()
    payload = {
        "version": 1,
        "outcome": "dry_run_ready",
        "target_repo": "C:\\repos\\repo",
        "registration": {
            "requested": False,
            "authorized": False,
            "status": "not_requested",
            "global_registry_path": "C:\\config\\REGISTRY.json",
            "before_sha256": "b" * 64,
            "plan_sha256": "a" * 64,
            "proposed_entry": {"id": "repo"},
            "planned_write_set": ["C:\\config\\REGISTRY.json"],
            "condition": "registration is published only after validation",
        },
    }

    try:
        helper.build_invocation(payload)
    except ValueError as exc:
        assert "proposed global entry" in str(exc)
    else:
        raise AssertionError("schema-incomplete registration scope was accepted")
