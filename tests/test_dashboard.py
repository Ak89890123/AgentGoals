from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import tkinter as tk
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from agentgoals.dashboard import (
    DashboardError,
    DashboardFilters,
    DashboardSession,
    build_dashboard,
    filter_dashboard_entries,
    group_dashboard_entries,
    lifecycle_folder,
    load_dashboard,
    resolve_entry_path,
)
from agentgoals.dashboard_app import (
    DashboardApplication,
    build_parser,
    build_smoke_result,
    dashboard_asset_path,
    discover_state_path,
    format_queue_position,
    parse_watch_interval,
    responsive_layout,
    state_file_signature,
    status_tone,
    translate,
)
from agentgoals.validate import resolve_schema_dir


@contextmanager
def dashboard_test_dir() -> Iterator[Path]:
    path = Path(".tmp") / "dashboard-test-data" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path.resolve()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_entry(
    goal_id: str,
    *,
    status: str = "draft",
    scheduling_status: str = "not_ready",
    queue_position: int | None = 1,
    project: str = "Harness",
    owner: str | None = "engineering",
    root_id: str = "repo-a",
    issues: list[str] | None = None,
    health_status: str = "healthy",
    goal_root: str = "C:/repo/goals",
    contract_path: str | None = None,
) -> dict[str, object]:
    key = f"{root_id}/{goal_id}"
    return {
        "id": goal_id,
        "title": goal_id.replace("-", " ").title(),
        "status": status,
        "project": project,
        "root_id": root_id,
        "goal_key": key,
        "goal_root": goal_root,
        "contract_path": contract_path or f"{goal_root}/{goal_id}/CONTRACT.md",
        "plan_path": f"{goal_root}/{goal_id}/PLAN.md",
        "evidence_path": f"{goal_root}/{goal_id}/EVIDENCE.md",
        "owner": owner,
        "updated": "2026-07-11",
        "completed": "2026-07-11" if status == "completed" else None,
        "review": {"required": status == "review_pending", "verdict": "pending"},
        "evidence": {"status": "complete" if status == "completed" else "pending"},
        "health": {
            "policy_version": 1,
            "status": health_status,
            "evaluated_on": "2026-07-11",
            "last_activity": "2026-07-11",
            "findings": [],
        },
        "scheduling": {
            "priority": 50,
            "depends_on": [],
            "status": scheduling_status,
            "queue_position": queue_position,
            "unmet_dependencies": [],
        },
        "next_action": None,
        "blocked_reason": "Waiting for approval" if status == "blocked" else None,
        "source_hash": "abc123",
        "last_seen": "2026-07-11T00:00:00+00:00",
        "issues": issues or [],
    }


def make_payload(entries: list[dict[str, object]]) -> dict[str, object]:
    open_entries = [entry for entry in entries if entry["status"] not in {"completed", "cancelled"}]
    runnable = [
        entry
        for entry in open_entries
        if entry["scheduling"]["status"] in {"runnable", "in_progress"}  # type: ignore[index]
    ]
    planned = sorted(
        open_entries,
        key=lambda entry: entry["scheduling"]["queue_position"] or 9999,  # type: ignore[index]
    )
    return {
        "version": 2,
        "generated_at": "2026-07-11T00:00:00+00:00",
        "queue": {
            "next_goal": runnable[0]["goal_key"] if runnable else None,
            "next_planned_goal": planned[0]["goal_key"] if planned else None,
            "open_count": len(open_entries),
            "runnable_count": len(runnable),
            "invalid_count": 0,
        },
        "entries": entries,
    }


def test_build_dashboard_summarizes_operational_states() -> None:
    payload = make_payload(
        [
            make_entry("current", status="in_progress", scheduling_status="in_progress"),
            make_entry("blocked", status="blocked", scheduling_status="blocked", queue_position=2),
            make_entry("review", status="review_pending", issues=["review_pending"], queue_position=3),
            make_entry("stale", issues=["health_stale"], health_status="issues", queue_position=4),
            make_entry("done", status="completed", scheduling_status="done", queue_position=None),
        ]
    )

    dashboard = build_dashboard(payload)

    assert dashboard.summary.total == 5
    assert dashboard.summary.open == 4
    assert dashboard.summary.runnable == 1
    assert dashboard.summary.blocked == 1
    assert dashboard.summary.review_pending == 1
    assert dashboard.summary.stale == 1
    assert dashboard.summary.completed == 1
    assert dashboard.next_goal == "repo-a/current"
    assert [entry.goal_key for entry in dashboard.entries[:2]] == ["repo-a/current", "repo-a/blocked"]


def test_filters_search_across_goal_fields_and_combine_dimensions() -> None:
    dashboard = build_dashboard(
        make_payload(
            [
                make_entry("alpha-api", project="Platform", owner="alex"),
                make_entry(
                    "beta-ui",
                    project="Desktop",
                    owner="bea",
                    issues=["health_stale"],
                    health_status="issues",
                    root_id="repo-b",
                ),
            ]
        )
    )

    assert [entry.id for entry in filter_dashboard_entries(dashboard.entries, DashboardFilters(query="beta"))] == [
        "beta-ui"
    ]
    assert [
        entry.id
        for entry in filter_dashboard_entries(
            dashboard.entries,
            DashboardFilters(project="Desktop", owner="bea", root_id="repo-b", health="issues"),
        )
    ] == ["beta-ui"]
    assert filter_dashboard_entries(dashboard.entries, DashboardFilters(status="completed")) == []


def test_filter_options_are_unique_sorted_and_include_unassigned_owner() -> None:
    dashboard = build_dashboard(
        make_payload(
            [
                make_entry("one", project="Zeta", owner=None),
                make_entry("two", project="Alpha", owner="engineering", root_id="repo-b"),
            ]
        )
    )

    assert dashboard.options.projects == ("Alpha", "Zeta")
    assert dashboard.options.owners == ("engineering", "Unassigned")
    assert dashboard.options.roots == ("repo-a", "repo-b")


def test_dashboard_groups_goals_by_repository_without_losing_queue_order() -> None:
    dashboard = build_dashboard(
        make_payload(
            [
                make_entry(
                    "a-second",
                    root_id="repo-a",
                    queue_position=4,
                    status="blocked",
                    scheduling_status="blocked",
                ),
                make_entry("b-first", root_id="repo-b", queue_position=1, scheduling_status="runnable"),
                make_entry(
                    "a-first",
                    root_id="repo-a",
                    queue_position=2,
                    status="in_progress",
                    scheduling_status="in_progress",
                ),
                make_entry(
                    "b-done",
                    root_id="repo-b",
                    queue_position=None,
                    status="completed",
                    scheduling_status="done",
                ),
            ]
        )
    )

    groups = group_dashboard_entries(dashboard.entries)

    assert [group.root_id for group in groups] == ["repo-b", "repo-a"]
    assert [entry.goal_key for entry in groups[0].entries] == ["repo-b/b-first", "repo-b/b-done"]
    assert [entry.goal_key for entry in groups[1].entries] == ["repo-a/a-first", "repo-a/a-second"]
    assert (groups[0].total, groups[0].open, groups[0].runnable, groups[0].blocked) == (2, 1, 1, 0)
    assert (groups[1].total, groups[1].open, groups[1].runnable, groups[1].blocked) == (2, 2, 1, 1)


def test_dashboard_groups_each_repository_by_existing_lifecycle_folders() -> None:
    dashboard = build_dashboard(
        make_payload(
            [
                make_entry("active-goal", contract_path="C:/repo/goals/active/active-goal/CONTRACT.md"),
                make_entry(
                    "done-goal",
                    status="completed",
                    scheduling_status="done",
                    queue_position=None,
                    contract_path="C:/repo/goals/completed/done-goal/CONTRACT.md",
                ),
                make_entry(
                    "cold-goal",
                    status="draft",
                    contract_path="C:/repo/goals/frozen/cold-goal/CONTRACT.md",
                ),
            ]
        )
    )

    group = group_dashboard_entries(dashboard.entries)[0]

    assert [item.name for item in group.lifecycle_groups] == ["active", "completed", "frozen"]
    assert [[entry.id for entry in item.entries] for item in group.lifecycle_groups] == [
        ["active-goal"],
        ["done-goal"],
        ["cold-goal"],
    ]
    assert lifecycle_folder(group.lifecycle_groups[2].entries[0]) == "frozen"


def test_lifecycle_folder_uses_location_before_status_and_falls_back_for_legacy_paths() -> None:
    dashboard = build_dashboard(
        make_payload(
            [
                make_entry(
                    "misfiled",
                    status="completed",
                    scheduling_status="done",
                    queue_position=None,
                    contract_path="C:/repo/goals/active/misfiled/CONTRACT.md",
                ),
                make_entry("legacy-done", status="completed", scheduling_status="done", queue_position=None),
            ]
        )
    )

    entries = {entry.id: entry for entry in dashboard.entries}
    assert lifecycle_folder(entries["misfiled"]) == "active"
    assert lifecycle_folder(entries["legacy-done"]) == "completed"


def test_resolve_entry_path_accepts_only_existing_file_under_goal_root() -> None:
    with dashboard_test_dir() as temp_dir:
        goal_root = temp_dir / "goals"
        contract = goal_root / "active" / "demo" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("---\n", encoding="utf-8")
        dashboard = build_dashboard(
            make_payload(
                [
                    make_entry(
                        "demo",
                        goal_root=str(goal_root),
                        contract_path=str(contract),
                    )
                ]
            )
        )

        assert resolve_entry_path(dashboard.entries[0], "contract_path") == contract.resolve()

        outside = temp_dir / "outside.md"
        outside.write_text("no", encoding="utf-8")
        escaped = dashboard.entries[0].with_path("contract_path", str(outside))
        with pytest.raises(DashboardError, match="outside registered goal root"):
            resolve_entry_path(escaped, "contract_path")

        relative = dashboard.entries[0].with_path("contract_path", "relative/CONTRACT.md")
        with pytest.raises(DashboardError, match="must be absolute"):
            resolve_entry_path(relative, "contract_path")


def test_load_dashboard_validates_schema_and_reports_context() -> None:
    with dashboard_test_dir() as temp_dir:
        valid_path = temp_dir / "STATE.json"
        valid_path.write_text(
            json.dumps(make_payload([make_entry("demo")]), ensure_ascii=False), encoding="utf-8-sig"
        )

        assert load_dashboard(valid_path).summary.total == 1

        malformed_path = temp_dir / "broken.json"
        malformed_path.write_text('{"version": 2}', encoding="utf-8")
        with pytest.raises(DashboardError, match="Invalid Goal STATE"):
            load_dashboard(malformed_path)


def test_session_refresh_and_open_use_injected_read_only_opener() -> None:
    with dashboard_test_dir() as temp_dir:
        goal_root = temp_dir / "goals"
        contract = goal_root / "demo" / "CONTRACT.md"
        contract.parent.mkdir(parents=True)
        contract.write_text("goal", encoding="utf-8")
        state_path = temp_dir / "STATE.json"
        state_path.write_text(
            json.dumps(
                make_payload([make_entry("demo", goal_root=str(goal_root), contract_path=str(contract))]),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        opened: list[Path] = []
        session = DashboardSession(state_path, opener=opened.append)

        model = session.refresh()
        opened_path = session.open_source(model.entries[0].goal_key, "contract_path")

        assert opened_path == contract.resolve()
        assert opened == [contract.resolve()]


def test_large_state_build_and_filter_stay_below_contract_budget() -> None:
    payload = make_payload(
        [
            make_entry(
                f"goal-{index:04d}",
                project=f"Project {index % 12}",
                owner=f"owner-{index % 8}",
                root_id=f"repo-{index % 6}",
                queue_position=index + 1,
            )
            for index in range(1000)
        ]
    )

    started = time.perf_counter()
    dashboard = build_dashboard(payload)
    filtered = filter_dashboard_entries(dashboard.entries, DashboardFilters(query="goal-09", project="Project 9"))
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert dashboard.summary.total == 1000
    assert filtered
    assert elapsed_ms < 500


def test_desktop_shell_helpers_keep_status_and_cli_semantics_stable() -> None:
    assert status_tone("in_progress") == "active"
    assert status_tone("blocked") == "critical"
    assert status_tone("review_pending") == "warning"
    assert status_tone("completed") == "complete"
    assert status_tone("unknown") == "neutral"
    assert format_queue_position(None) == "—"
    assert format_queue_position(7) == "07"
    assert build_parser().parse_args([]).state == Path("outputs/global/STATE.json")
    assert build_parser().parse_args([]).watch_interval_ms == 1000
    assert build_parser().parse_args(["--probe-output", "probe.json"]).probe_output == Path("probe.json")
    args = build_parser().parse_args(["--watch", "--watch-interval-ms", "750"])
    assert args.watch is True
    assert args.watch_interval_ms == 750


def test_watch_interval_and_state_signature_are_deterministic() -> None:
    assert parse_watch_interval("50") == 50
    assert parse_watch_interval("60000") == 60000
    with pytest.raises(argparse.ArgumentTypeError):
        parse_watch_interval("49")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_watch_interval("not-a-number")

    with dashboard_test_dir() as temp_dir:
        state_path = temp_dir / "STATE.json"
        assert state_file_signature(state_path) is None
        state_path.write_text("{}", encoding="utf-8")
        first = state_file_signature(state_path)
        assert first is not None
        state_path.write_text("{\"changed\": true}", encoding="utf-8")
        assert state_file_signature(state_path) != first


def test_dashboard_translations_cover_traditional_chinese_and_fallback_to_english() -> None:
    assert translate("zh_TW", "refresh") == "重新整理"
    assert translate("zh_TW", "repository") == "儲存庫"
    assert translate("en", "open") == "Open"
    assert translate("unknown", "refresh") == "Refresh"


def test_dashboard_icon_assets_are_available_from_the_source_tree() -> None:
    assert dashboard_asset_path("agentgoals-target.ico").is_file()
    assert dashboard_asset_path("agentgoals-target.png").is_file()


def test_packaged_app_discovers_repo_state_from_executable_ancestors() -> None:
    with dashboard_test_dir() as temp_dir:
        repo = temp_dir / "repo"
        state = repo / "outputs" / "global" / "STATE.json"
        executable = repo / "dist" / "AgentGoals.exe"
        state.parent.mkdir(parents=True)
        state.write_text("{}", encoding="utf-8")
        executable.parent.mkdir(parents=True)

        assert discover_state_path(
            Path("outputs/global/STATE.json"),
            cwd=temp_dir / "elsewhere",
            executable=executable,
        ) == state.resolve()


def test_packaged_validator_discovers_schema_under_runtime_root() -> None:
    with dashboard_test_dir() as temp_dir:
        schema_dir = temp_dir / "schemas"
        schema_dir.mkdir()
        (schema_dir / "goal-state.schema.json").write_text("{}", encoding="utf-8")

        assert resolve_schema_dir(temp_dir) == schema_dir.resolve()


def test_smoke_result_fails_process_when_dashboard_state_cannot_load() -> None:
    payload, exit_code = build_smoke_result(
        entries=None,
        geometry="1x1+0+0",
        state="C:/repo/outputs/global/STATE.json",
        error="schema mismatch",
    )

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["entries"] == 0
    assert payload["error"] == "schema mismatch"


def test_smoke_result_passes_only_after_dashboard_state_loads() -> None:
    payload, exit_code = build_smoke_result(
        entries=15,
        geometry="1600x900+0+0",
        state="C:/repo/outputs/global/STATE.json",
        error=None,
    )

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["entries"] == 15
    assert payload["error"] is None


def test_responsive_layout_preserves_detail_width_on_compact_desktop() -> None:
    compact = responsive_layout(1080)
    standard = responsive_layout(1280)
    wide = responsive_layout(1440)

    assert compact.detail_width == 310
    assert compact.detail_wrap == 260
    assert compact.columns["project"] == 0
    assert compact.columns["owner"] == 0
    assert compact.columns["title"] > standard.columns["title"]
    assert standard.detail_width == 330
    assert wide.detail_width == 360


@pytest.mark.skipif(os.name != "nt", reason="First release is Windows-only")
def test_desktop_window_constructs_and_loads_state_without_render_exception() -> None:
    with dashboard_test_dir() as temp_dir:
        state_path = temp_dir / "STATE.json"
        state_path.write_text(json.dumps(make_payload([make_entry("demo")]), ensure_ascii=False), encoding="utf-8")
        root = tk.Tk()
        root.withdraw()
        try:
            app = DashboardApplication(root, state_path)
            root.update_idletasks()
            assert app.model is not None
            assert app.model.summary.total == 1
            repo_row = app.tree.get_children()[0]
            assert repo_row == "repo::repo-a"
            lifecycle_row = app.tree.get_children(repo_row)[0]
            assert lifecycle_row == "folder::repo-a::active"
            assert app.tree.get_children(lifecycle_row) == ("repo-a/demo",)
            assert not app.tree.item(repo_row, "open")
            assert not app.tree.item(lifecycle_row, "open")
            assert app.tree.selection() == ()
            app.tree.item(repo_row, open=True)
            app.tree.item(lifecycle_row, open=True)
            app.tree.selection_set("repo-a/demo")
            app.refresh()
            refreshed_repo_row = app.tree.get_children()[0]
            refreshed_lifecycle_row = app.tree.get_children(refreshed_repo_row)[0]
            assert app.tree.item(refreshed_repo_row, "open")
            assert app.tree.item(refreshed_lifecycle_row, "open")
            assert app.tree.selection() == ("repo-a/demo",)
            app.tree.item(refreshed_lifecycle_row, open=False)
            app.refresh()
            refreshed_repo_row = app.tree.get_children()[0]
            refreshed_lifecycle_row = app.tree.get_children(refreshed_repo_row)[0]
            assert app.tree.item(refreshed_repo_row, "open")
            assert not app.tree.item(refreshed_lifecycle_row, "open")
            assert app.root.title() == "AgentGoals — 本機儀表板"
            assert hasattr(app, "window_icon")
            assert app.tree.heading("status")["text"] == "狀態"
            app._manual_column_widths["title"] = 412
            app._apply_responsive_layout()
            assert int(app.tree.column("title", "width")) == 412
            app._autofit_tree_column("title")
            assert int(app.tree.column("title", "width")) >= 38
            assert "title" in app._manual_column_widths
            app.language_var.set("English")
            app._change_language()
            assert app.root.title() == "AgentGoals — Local Dashboard"
            assert app.tree.heading("status")["text"] == "STATUS"
        finally:
            root.destroy()


@pytest.mark.skipif(os.name != "nt", reason="First release is Windows-only")
def test_development_watch_reloads_state_and_preserves_selected_goal() -> None:
    with dashboard_test_dir() as temp_dir:
        state_path = temp_dir / "STATE.json"
        state_path.write_text(json.dumps(make_payload([make_entry("demo")]), ensure_ascii=False), encoding="utf-8")
        root = tk.Tk()
        root.withdraw()
        try:
            app = DashboardApplication(root, state_path, watch=True, watch_interval_ms=50)
            root.update_idletasks()
            repo_row = app.tree.get_children()[0]
            lifecycle_row = app.tree.get_children(repo_row)[0]
            app.tree.item(repo_row, open=True)
            app.tree.item(lifecycle_row, open=True)
            app.tree.selection_set("repo-a/demo")

            state_path.write_text(
                json.dumps(make_payload([make_entry("demo"), make_entry("next", queue_position=2)]), ensure_ascii=False),
                encoding="utf-8",
            )
            root.after(250, root.quit)
            root.mainloop()

            assert app.model is not None
            assert app.model.summary.total == 2
            assert app.tree.selection() == ("repo-a/demo",)
            refreshed_repo_row = app.tree.get_children()[0]
            refreshed_lifecycle_row = app.tree.get_children(refreshed_repo_row)[0]
            assert app.tree.item(refreshed_repo_row, "open")
            assert app.tree.item(refreshed_lifecycle_row, "open")
            assert "即時重新整理" in app.status_line.get()
            assert "即時重新整理已啟用" in app.footer_label.cget("text")
        finally:
            root.destroy()
