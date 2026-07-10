from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


ACTIVE_STATUSES = {"draft", "review_pending", "ready", "in_progress", "blocked"}
DEFAULT_THRESHOLDS = {
    "draft": 30,
    "review_pending": 7,
    "ready": 14,
    "in_progress": 14,
    "blocked": 7,
}
STALE_SEVERITY = {
    "draft": "info",
    "review_pending": "warning",
    "ready": "warning",
    "in_progress": "warning",
    "blocked": "info",
}


@dataclass(frozen=True)
class HealthPolicy:
    version: int | None
    enabled: bool
    thresholds: dict[str, int]


def disabled_policy() -> HealthPolicy:
    return HealthPolicy(version=None, enabled=False, thresholds=dict(DEFAULT_THRESHOLDS))


def disabled_health() -> dict[str, Any]:
    return {
        "policy_version": None,
        "status": "disabled",
        "evaluated_on": None,
        "last_activity": None,
        "findings": [],
    }


def normalize_health_policy(value: Any) -> HealthPolicy:
    if value is None:
        return disabled_policy()
    if not isinstance(value, dict):
        raise ValueError("health_policy must be an object")

    unknown = set(value) - {"version", "enabled", "thresholds"}
    if unknown:
        raise ValueError(f"health_policy has unknown fields: {sorted(unknown)}")
    if value.get("version") != 1:
        raise ValueError("health_policy.version must be 1")
    if not isinstance(value.get("enabled"), bool):
        raise ValueError("health_policy.enabled must be a boolean")

    overrides = value.get("thresholds", {})
    if not isinstance(overrides, dict):
        raise ValueError("health_policy.thresholds must be an object")
    unknown_statuses = set(overrides) - set(DEFAULT_THRESHOLDS)
    if unknown_statuses:
        raise ValueError(f"health_policy has unknown thresholds: {sorted(unknown_statuses)}")

    thresholds = dict(DEFAULT_THRESHOLDS)
    for status, threshold in overrides.items():
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
            raise ValueError(f"health_policy threshold for {status} must be a non-negative integer")
        thresholds[status] = threshold
    return HealthPolicy(version=1, enabled=value["enabled"], thresholds=thresholds)


def evaluate_health(
    status: str,
    contract_metadata: dict[str, Any],
    plan_metadata: dict[str, Any],
    evidence_metadata: dict[str, Any],
    policy: HealthPolicy,
    evaluated_on: date,
) -> dict[str, Any]:
    if not policy.enabled:
        return disabled_health()

    findings: list[dict[str, Any]] = []
    parsed: dict[str, date] = {}
    date_inputs = [
        ("created", contract_metadata, "created", True),
        ("contract_updated", contract_metadata, "updated", True),
        ("plan_updated", plan_metadata, "updated", bool(plan_metadata)),
        ("evidence_updated", evidence_metadata, "updated", bool(evidence_metadata)),
        ("completed", contract_metadata, "completed", status == "completed"),
    ]

    for name, metadata, field, required in date_inputs:
        raw = metadata.get(field)
        if raw is None or raw == "":
            if required:
                add_finding(findings, "health_date_missing", f"dates.{name}_present", "warning", name)
            continue
        parsed_date = parse_date(raw)
        if parsed_date is None:
            add_finding(
                findings,
                "health_date_invalid",
                f"dates.{name}_valid",
                "warning",
                name,
                observed=str(raw),
            )
            continue
        parsed[name] = parsed_date
        if parsed_date > evaluated_on:
            add_finding(
                findings,
                "health_date_future",
                f"dates.{name}_not_future",
                "warning",
                name,
                observed=parsed_date.isoformat(),
            )

    created = parsed.get("created")
    if created is not None:
        for name in ("contract_updated", "plan_updated", "evidence_updated", "completed"):
            candidate = parsed.get(name)
            if candidate is not None and candidate < created:
                add_finding(
                    findings,
                    "health_date_order",
                    f"dates.{name}_not_before_created",
                    "error",
                    name,
                    observed=candidate.isoformat(),
                )

    completed_raw = contract_metadata.get("completed")
    if status in ACTIVE_STATUSES and completed_raw is not None and completed_raw != "":
        add_finding(
            findings,
            "health_completion_inconsistent",
            "completion.active_has_no_completed_date",
            "warning",
            "completed",
            observed=str(completed_raw),
        )
    if status == "completed" and evidence_metadata.get("status") != "complete":
        add_finding(
            findings,
            "health_evidence_incomplete",
            "completion.evidence_complete",
            "warning",
            "evidence.status",
            observed=str(evidence_metadata.get("status")),
        )

    activity_dates = [
        value
        for name, value in parsed.items()
        if name.endswith("updated") and value <= evaluated_on
    ]
    last_activity = max(activity_dates) if activity_dates else None
    if status in ACTIVE_STATUSES and last_activity is not None:
        threshold = policy.thresholds[status]
        age_days = (evaluated_on - last_activity).days
        if age_days > threshold:
            add_finding(
                findings,
                "health_stale",
                f"freshness.{status}",
                STALE_SEVERITY[status],
                "last_activity",
                observed=last_activity.isoformat(),
                age_days=age_days,
                threshold_days=threshold,
            )

    return {
        "policy_version": policy.version,
        "status": "issues" if findings else "healthy",
        "evaluated_on": evaluated_on.isoformat(),
        "last_activity": last_activity.isoformat() if last_activity else None,
        "findings": findings,
    }


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def add_finding(
    findings: list[dict[str, Any]],
    code: str,
    rule: str,
    severity: str,
    field: str,
    observed: str | None = None,
    age_days: int | None = None,
    threshold_days: int | None = None,
) -> None:
    findings.append(
        {
            "code": code,
            "rule": rule,
            "severity": severity,
            "field": field,
            "date": observed,
            "age_days": age_days,
            "threshold_days": threshold_days,
        }
    )
