from __future__ import annotations


def gate_for_status(status: str, review_required: bool, review_verdict: str | None) -> str:
    if status == "draft":
        return "accept_contract"
    if status == "review_pending":
        return "obtain_review"
    if status == "ready":
        return "start_execution"
    if status == "in_progress":
        if review_required and review_verdict != "PASS":
            return "continue_before_review_gate"
        return "continue_execution"
    if status == "blocked":
        return "resolve_blocker"
    return "inspect_lifecycle_state"
