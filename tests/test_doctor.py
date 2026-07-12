from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from goal_lifecycle.doctor import build_doctor_result, main, redact_origin


def load_schema() -> dict:
    return json.loads(Path("schemas/doctor-result.schema.json").read_text(encoding="utf-8"))


def test_ready_doctor_result_is_schema_valid() -> None:
    payload, exit_code = build_doctor_result(
        route="console_script",
        origin=Path.home() / ".local" / "bin" / "goal-lifecycle",
        python_version=(3, 11, 9),
        toolkit_version="0.1.0",
        schemas_available=True,
    )

    Draft202012Validator(load_schema()).validate(payload)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["failure_code"] is None
    assert payload["remediation"] is None
    assert payload["origin"].startswith("<home>")


def test_unsupported_python_returns_one_structured_remediation() -> None:
    payload, exit_code = build_doctor_result(
        route="module",
        origin=Path("C:/tool/goal_lifecycle/__init__.py"),
        python_version=(3, 10, 14),
        toolkit_version="0.1.0",
        schemas_available=True,
    )

    Draft202012Validator(load_schema()).validate(payload)
    assert exit_code == 2
    assert payload["status"] == "action_required"
    assert payload["failure_code"] == "unsupported_python"
    assert payload["remediation"] == {
        "action": "provide_release_coordinates",
        "argv": ["OWNER", "REPO", "TAG", "PYTHON>=3.11"],
    }


def test_missing_schemas_returns_invalid_reinstall_action() -> None:
    payload, exit_code = build_doctor_result(
        route="console_script",
        origin=Path("C:/tool/goal-lifecycle.exe"),
        python_version=(3, 11, 9),
        toolkit_version="0.1.0",
        schemas_available=False,
    )

    Draft202012Validator(load_schema()).validate(payload)
    assert exit_code == 1
    assert payload["status"] == "invalid"
    assert payload["failure_code"] == "schemas_missing"
    assert payload["remediation"]["action"] == "provide_release_coordinates"


def test_doctor_json_writes_only_one_json_object(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    Draft202012Validator(load_schema()).validate(payload)
    assert exit_code in {0, 1, 2}
    assert captured.err == ""


def test_redact_origin_hides_user_home() -> None:
    value = redact_origin(Path.home() / "private" / "goal-lifecycle.exe")

    assert str(Path.home()) not in value
    assert value.startswith("<home>")
