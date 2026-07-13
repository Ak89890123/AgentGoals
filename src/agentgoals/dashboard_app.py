from __future__ import annotations

import argparse
import json
import sys
import time
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Literal

from agentgoals.dashboard import (
    DashboardEntry,
    DashboardError,
    DashboardFilters,
    DashboardModel,
    DashboardSession,
    RepositoryGroup,
    filter_dashboard_entries,
    group_dashboard_entries,
)


COLORS = {
    "bg": "#090D12",
    "panel": "#101720",
    "panel_alt": "#151E29",
    "panel_high": "#1A2532",
    "border": "#263445",
    "border_soft": "#1C2733",
    "text": "#EAF0F6",
    "muted": "#8795A8",
    "faint": "#5D6A7A",
    "accent": "#55D6BE",
    "accent_dark": "#173E3A",
    "blue": "#72A7FF",
    "blue_dark": "#172A46",
    "warning": "#F4BD61",
    "warning_dark": "#44341A",
    "critical": "#FF7A7A",
    "critical_dark": "#461F26",
    "complete": "#87C978",
    "complete_dark": "#213A24",
}

# A content fit should remain useful in the dashboard rather than allowing one
# unusually long value to consume the entire table.
COLUMN_AUTOFIT_MAX_WIDTH = 640
COLUMN_AUTOFIT_PADDING = 24
DASHBOARD_ICON_NAME = "agentgoals-target"


def dashboard_asset_path(filename: str) -> Path:
    """Resolve a bundled dashboard asset in source and PyInstaller builds."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "assets" / filename
    return Path(__file__).resolve().parents[2] / "assets" / filename

TRANSLATIONS = {
    "en": {
        "app_title": "AgentGoals — Local Dashboard",
        "brand": "GOAL / CONTROL",
        "observatory": "LOCAL LIFECYCLE OBSERVATORY",
        "language": "Language",
        "refresh": "Refresh",
        "open": "Open",
        "runnable": "Runnable",
        "blocked": "Blocked",
        "review": "Review",
        "stale": "Stale",
        "completed": "Completed",
        "status": "Status",
        "project": "Project",
        "owner": "Owner",
        "repository": "Repository",
        "health": "Health",
        "goal": "Goal",
        "updated": "Updated",
        "queue": "Queue",
        "all": "all",
        "goal_dossier": "GOAL DOSSIER",
        "source_artifacts": "SOURCE ARTIFACTS",
        "contract": "Contract",
        "plan": "Plan",
        "evidence": "Evidence",
        "lifecycle": "Lifecycle",
        "exact_gate": "Exact Gate",
        "issues": "Issues",
        "read_only": "READ ONLY  •  CTRL+R REFRESH  •  CTRL+F SEARCH",
        "select_goal": "Select a Goal",
        "no_source": "No source selected",
        "no_matching_goal": "No matching Goal",
        "adjust_filters": "Adjust filters or refresh the source STATE",
        "repository_summary": "Repository  ·  {total} Goals",
        "repository_meta": "{open} OPEN  ·  {runnable} RUNNABLE  ·  {blocked} BLOCKED",
        "next_in_repository": "Next in repository: {title}",
        "no_runnable_repository": "No runnable Goal in this repository",
        "repository_health": "Repository summary derived from its registered Goals",
        "repository_issues": "Select a Goal to inspect source artifacts and exact lifecycle gates",
        "priority_queue_owner": "Priority {priority}  ·  Queue {queue}  ·  {owner}",
        "no_next_action": "No explicit next action recorded",
        "waiting_on": "Waiting on {dependencies}",
        "showing": "showing {count}",
        "goals_refreshed": "{count} Goals  •  refreshed {elapsed:.1f} ms  •  generated {generated}",
        "startup": "startup {elapsed:.1f} ms",
        "load_error": "LOAD ERROR",
        "open_error": "OPEN ERROR",
        "opened": "Opened {source} for {goal}",
        "draft": "Draft",
        "review_pending": "Review Pending",
        "ready": "Ready",
        "in_progress": "In Progress",
        "not_ready": "Not Ready",
        "dependency_blocked": "Dependency Blocked",
        "healthy": "Healthy",
        "issues_status": "Issues",
        "disabled": "Disabled",
        "invalid": "Invalid",
        "unassigned": "Unassigned",
    },
    "zh_TW": {
        "app_title": "AgentGoals — 本機儀表板",
        "brand": "AgentGoals",
        "observatory": "本機 AgentGoals 觀測站",
        "language": "語言",
        "refresh": "重新整理",
        "open": "開放中",
        "runnable": "可執行",
        "blocked": "受阻",
        "review": "待審查",
        "stale": "過期",
        "completed": "已完成",
        "status": "狀態",
        "project": "專案",
        "owner": "負責人",
        "repository": "儲存庫",
        "health": "健康度",
        "goal": "目標",
        "updated": "更新日期",
        "queue": "佇列",
        "all": "全部",
        "goal_dossier": "目標詳情",
        "source_artifacts": "來源文件",
        "contract": "合約",
        "plan": "計畫",
        "evidence": "證據",
        "lifecycle": "生命週期",
        "exact_gate": "目前關卡",
        "issues": "問題",
        "read_only": "唯讀  •  CTRL+R 重新整理  •  CTRL+F 搜尋",
        "select_goal": "選取一個目標",
        "no_source": "尚未選取來源",
        "no_matching_goal": "沒有符合的目標",
        "adjust_filters": "請調整篩選條件或重新整理來源 STATE",
        "repository_summary": "儲存庫  ·  共 {total} 個目標",
        "repository_meta": "{open} 個開放中  ·  {runnable} 個可執行  ·  {blocked} 個受阻",
        "next_in_repository": "此儲存庫下一項：{title}",
        "no_runnable_repository": "此儲存庫目前沒有可執行目標",
        "repository_health": "此摘要由已註冊目標的健康狀態彙整而成",
        "repository_issues": "請選取目標以檢視來源文件與目前關卡",
        "priority_queue_owner": "優先度 {priority}  ·  佇列 {queue}  ·  {owner}",
        "no_next_action": "尚未記錄明確的下一步",
        "waiting_on": "等待：{dependencies}",
        "showing": "顯示 {count} 項",
        "goals_refreshed": "{count} 個目標  •  已重新整理 {elapsed:.1f} ms  •  產生於 {generated}",
        "startup": "啟動 {elapsed:.1f} ms",
        "load_error": "載入錯誤",
        "open_error": "開啟錯誤",
        "opened": "已開啟 {goal} 的{source}",
        "draft": "草稿",
        "review_pending": "待審查",
        "ready": "已就緒",
        "in_progress": "進行中",
        "not_ready": "尚未就緒",
        "dependency_blocked": "相依項目受阻",
        "healthy": "健康",
        "issues_status": "有問題",
        "disabled": "未啟用",
        "invalid": "無效",
        "unassigned": "未指派",
    },
}


def translate(language: str, key: str, **values: object) -> str:
    template = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
    return template.format(**values)


@dataclass(frozen=True)
class ResponsiveLayout:
    detail_width: int
    detail_wrap: int
    columns: dict[str, int]


def responsive_layout(window_width: int) -> ResponsiveLayout:
    if window_width < 1200:
        return ResponsiveLayout(
            detail_width=310,
            detail_wrap=260,
            columns={"queue": 42, "title": 275, "status": 110, "project": 0, "owner": 0, "health": 85, "updated": 90},
        )
    if window_width < 1400:
        return ResponsiveLayout(
            detail_width=330,
            detail_wrap=280,
            columns={"queue": 45, "title": 260, "status": 110, "project": 125, "owner": 105, "health": 90, "updated": 88},
        )
    return ResponsiveLayout(
        detail_width=360,
        detail_wrap=310,
        columns={"queue": 48, "title": 290, "status": 120, "project": 150, "owner": 120, "health": 100, "updated": 96},
    )


def status_tone(status: str) -> str:
    if status in {"in_progress", "ready"}:
        return "active"
    if status in {"blocked", "parse_error", "missing"}:
        return "critical"
    if status in {"review_pending", "draft"}:
        return "warning"
    if status in {"completed", "cancelled"}:
        return "complete"
    return "neutral"


def format_queue_position(value: int | None) -> str:
    return f"{value:02d}" if value is not None else "—"


class MetricCard(tk.Frame):
    def __init__(self, parent: tk.Misc, label: str, accent: str) -> None:
        super().__init__(parent, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border_soft"])
        self.configure(padx=16, pady=12)
        tk.Frame(self, bg=accent, height=3).pack(fill="x", side="top")
        self.value = tk.Label(
            self,
            text="—",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Bahnschrift SemiBold", 25),
            anchor="w",
        )
        self.value.pack(fill="x", pady=(8, 0))
        self.label = tk.Label(
            self,
            text=label.upper(),
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Cascadia Mono", 9, "bold"),
            anchor="w",
        )
        self.label.pack(fill="x", pady=(1, 0))

    def set(self, value: int) -> None:
        self.value.configure(text=str(value))

    def set_label(self, label: str) -> None:
        self.label.configure(text=label.upper())


class DashboardApplication:
    def __init__(self, root: tk.Tk, state_path: Path, *, startup_started: float | None = None) -> None:
        self.root = root
        self.state_path = state_path.resolve()
        self.session = DashboardSession(self.state_path)
        self.model: DashboardModel | None = None
        self.visible_entries: list[DashboardEntry] = []
        self.entry_by_key: dict[str, DashboardEntry] = {}
        self.repository_by_iid: dict[str, RepositoryGroup] = {}
        self._filter_job: str | None = None
        self._resize_job: str | None = None
        self._resizing_column: str | None = None
        self._manual_column_widths: dict[str, int] = {}
        self._startup_started = startup_started or time.perf_counter()
        self.last_error: str | None = None
        self.detail_wrapped_labels: list[tk.Label] = []

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="all")
        self.project_var = tk.StringVar(value="all")
        self.owner_var = tk.StringVar(value="all")
        self.root_var = tk.StringVar(value="all")
        self.health_var = tk.StringVar(value="all")
        self.status_line = tk.StringVar(value="Initializing local read-only dashboard…")
        self.language_var = tk.StringVar(value="繁體中文")
        self.detail_title = tk.StringVar(value=self._t("select_goal"))
        self.detail_key = tk.StringVar(value=self._t("no_source"))
        self.detail_meta = tk.StringVar(value="")
        self.detail_gate = tk.StringVar(value="")
        self.detail_health = tk.StringVar(value="")
        self.detail_issues = tk.StringVar(value="")

        self._configure_window()
        self._configure_styles()
        self._build_layout()
        self._bind_shortcuts()
        self.root.after_idle(self._apply_responsive_layout)
        self.refresh(initial=True)

    def _t(self, key: str, **values: object) -> str:
        language = {"繁體中文": "zh_TW", "English": "en"}.get(self.language_var.get(), "en")
        return translate(language, key, **values)

    def _localize_value(self, value: str) -> str:
        key = "issues_status" if value == "issues" else value
        return self._t(key).upper()

    def _display_filter_value(self, value: str) -> str:
        return self._t("unassigned") if value == "Unassigned" else self._localize_value(value) if value in {
            "all", "draft", "review_pending", "ready", "in_progress", "blocked", "completed",
            "cancelled", "healthy", "issues", "disabled", "invalid",
        } else value

    def _filter_choice(self, value: str) -> str:
        for raw in (
            "all", "draft", "review_pending", "ready", "in_progress", "blocked", "completed",
            "cancelled", "healthy", "issues", "disabled", "invalid",
        ):
            if value == self._display_filter_value(raw):
                return raw
        return "Unassigned" if value == self._t("unassigned") else value

    def _change_language(self, _event: object | None = None) -> None:
        selected = self.tree.selection()
        current_filters = {
            "status": self._filter_choice(self.status_var.get()),
            "project": self.project_var.get(),
            "owner": self._filter_choice(self.owner_var.get()),
            "root": self.root_var.get(),
            "health": self._filter_choice(self.health_var.get()),
        }
        self.root.title(self._t("app_title"))
        self.observatory_label.configure(text=self._t("observatory"))
        self.language_label.configure(text=self._t("language").upper())
        self.refresh_button.configure(text=f"↻  {self._t('refresh').upper()}")
        self.footer_label.configure(text=self._t("read_only"))
        for key, card in self.metric_cards.items():
            card.set_label(self._t("review") if key == "review_pending" else self._t(key))
        for key, label in self.filter_labels.items():
            label.configure(text=self._t("repository" if key == "root" else key).upper())
        for column, (label_key, _anchor) in self.heading_specs.items():
            self.tree.heading(column, text=self._t(label_key).upper())
        self.dossier_label.configure(text=self._t("goal_dossier").upper())
        self.source_label.configure(text=self._t("source_artifacts").upper())
        for key, label in self.detail_section_labels.items():
            label.configure(text=self._t(key).upper())
        for field_name, button in self.path_buttons.items():
            button.configure(text=self._t(self.path_button_labels[field_name]).upper())
        self._update_filter_options()
        self.status_var.set(self._display_filter_value(current_filters["status"]))
        self.project_var.set(current_filters["project"])
        self.owner_var.set(self._display_filter_value(current_filters["owner"]))
        self.root_var.set(current_filters["root"])
        self.health_var.set(self._display_filter_value(current_filters["health"]))
        self.apply_filters(select_goal=selected[0] if selected and selected[0] in self.entry_by_key else None)

    def _configure_window(self) -> None:
        self.root.title(self._t("app_title"))
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1440x860")
        self.root.minsize(1080, 680)
        self._set_window_icon()

    def _set_window_icon(self) -> None:
        icon_path = dashboard_asset_path(f"{DASHBOARD_ICON_NAME}.ico")
        if not icon_path.is_file():
            return
        try:
            self.root.iconbitmap(default=str(icon_path))
            png_path = dashboard_asset_path(f"{DASHBOARD_ICON_NAME}.png")
            if png_path.is_file():
                self.window_icon = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self.window_icon)
        except tk.TclError:
            # The dashboard remains usable on platforms that do not support
            # Windows icon resources.
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Dashboard.Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border_soft"],
            rowheight=38,
            font=(self._font("Segoe UI", "TkDefaultFont"), 10),
        )
        style.map(
            "Dashboard.Treeview",
            background=[("selected", COLORS["accent_dark"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure(
            "Dashboard.Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["muted"],
            bordercolor=COLORS["border"],
            relief="flat",
            font=(self._font("Cascadia Mono", "TkFixedFont"), 9, "bold"),
            padding=(8, 10),
        )
        style.map("Dashboard.Treeview.Heading", background=[("active", COLORS["panel_high"])])
        style.configure(
            "Dashboard.TCombobox",
            fieldbackground=COLORS["panel_alt"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["accent"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=(9, 7),
        )
        style.map(
            "Dashboard.TCombobox",
            fieldbackground=[("readonly", COLORS["panel_alt"])],
            foreground=[("readonly", COLORS["text"])],
        )
        style.configure("Dashboard.TPanedwindow", background=COLORS["bg"], sashwidth=8)

    def _font(self, preferred: str, fallback: str) -> str:
        available = set(tkfont.families(self.root))
        return preferred if preferred in available else tkfont.nametofont(fallback).actual("family")

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["bg"], padx=24, pady=20)
        shell.pack(fill="both", expand=True)

        self._build_header(shell)
        self._build_metrics(shell)
        self._build_filters(shell)
        self._build_workspace(shell)

        status = tk.Frame(shell, bg=COLORS["bg"], pady=10)
        status.pack(fill="x", side="bottom")
        tk.Label(
            status,
            textvariable=self.status_line,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 9),
            anchor="w",
        ).pack(side="left")
        self.footer_label = tk.Label(
            status,
            text=self._t("read_only"),
            bg=COLORS["bg"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )
        self.footer_label.pack(side="right")

    def _build_header(self, parent: tk.Misc) -> None:
        header = tk.Frame(parent, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 16))

        brand = tk.Frame(header, bg=COLORS["bg"])
        brand.pack(side="left")
        self.brand_label = tk.Label(
            brand,
            text=self._t("brand"),
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=(self._font("Bahnschrift SemiBold", "TkHeadingFont"), 24),
        )
        self.brand_label.pack(anchor="w")
        self.observatory_label = tk.Label(
            brand,
            text=self._t("observatory"),
            bg=COLORS["bg"],
            fg=COLORS["accent"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 9, "bold"),
        )
        self.observatory_label.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, bg=COLORS["bg"])
        actions.pack(side="right")
        tk.Label(
            actions,
            text=str(self.state_path),
            bg=COLORS["bg"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8),
        ).pack(anchor="e", pady=(0, 6))
        language_row = tk.Frame(actions, bg=COLORS["bg"])
        language_row.pack(anchor="e", pady=(0, 6))
        self.language_label = tk.Label(
            language_row,
            text=self._t("language").upper(),
            bg=COLORS["bg"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )
        self.language_label.pack(side="left", padx=(0, 6))
        self.language_combo = ttk.Combobox(
            language_row,
            textvariable=self.language_var,
            state="readonly",
            width=11,
            style="Dashboard.TCombobox",
            values=("繁體中文", "English"),
        )
        self.language_combo.bind("<<ComboboxSelected>>", self._change_language)
        self.language_combo.pack(side="left")
        self.refresh_button = self._button(actions, f"↻  {self._t('refresh').upper()}", self.refresh, accent=True)
        self.refresh_button.pack(anchor="e")

    def _build_metrics(self, parent: tk.Misc) -> None:
        metrics = tk.Frame(parent, bg=COLORS["bg"])
        metrics.pack(fill="x", pady=(0, 14))
        self.metric_cards: dict[str, MetricCard] = {}
        specs = (
            ("open", COLORS["blue"]),
            ("runnable", COLORS["accent"]),
            ("blocked", COLORS["critical"]),
            ("review_pending", COLORS["warning"]),
            ("stale", "#C58BFF"),
            ("completed", COLORS["complete"]),
        )
        for index, (key, accent) in enumerate(specs):
            card = MetricCard(metrics, self._t(key), accent)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 5, 0 if index == 5 else 5))
            metrics.grid_columnconfigure(index, weight=1)
            self.metric_cards[key] = card

    def _build_filters(self, parent: tk.Misc) -> None:
        bar = tk.Frame(
            parent,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
            padx=12,
            pady=11,
        )
        bar.pack(fill="x", pady=(0, 14))

        search_wrap = tk.Frame(bar, bg=COLORS["panel_alt"], highlightthickness=1, highlightbackground=COLORS["border"])
        search_wrap.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(
            search_wrap,
            text="⌕",
            bg=COLORS["panel_alt"],
            fg=COLORS["accent"],
            font=(self._font("Segoe UI Symbol", "TkDefaultFont"), 14),
            padx=9,
        ).pack(side="left")
        self.search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search_var,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat",
            borderwidth=0,
            font=(self._font("Segoe UI", "TkDefaultFont"), 10),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))

        self.combos: dict[str, ttk.Combobox] = {}
        self.filter_labels: dict[str, tk.Label] = {}
        for key, variable, width in (
            ("status", self.status_var, 15),
            ("project", self.project_var, 18),
            ("owner", self.owner_var, 15),
            ("root", self.root_var, 15),
            ("health", self.health_var, 12),
        ):
            block = tk.Frame(bar, bg=COLORS["panel"])
            block.pack(side="left", padx=(0, 8))
            label = tk.Label(
                block,
                text=self._t("repository" if key == "root" else key).upper(),
                bg=COLORS["panel"],
                fg=COLORS["faint"],
                font=(self._font("Cascadia Mono", "TkFixedFont"), 7, "bold"),
            )
            label.pack(anchor="w")
            self.filter_labels[key] = label
            combo = ttk.Combobox(
                block,
                textvariable=variable,
                state="readonly",
                width=width,
                style="Dashboard.TCombobox",
                values=("all",),
            )
            combo.pack(pady=(2, 0))
            combo.bind("<<ComboboxSelected>>", self._schedule_filter)
            self.combos[key] = combo

        self.search_var.trace_add("write", self._schedule_filter)

    def _build_workspace(self, parent: tk.Misc) -> None:
        pane = ttk.Panedwindow(parent, orient="horizontal", style="Dashboard.TPanedwindow")
        pane.pack(fill="both", expand=True)
        self.workspace_pane = pane

        list_panel = tk.Frame(
            pane,
            bg=COLORS["panel"],
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
        )
        detail_panel = tk.Frame(
            pane,
            bg=COLORS["panel"],
            width=380,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
        )
        pane.add(list_panel, weight=4)
        pane.add(detail_panel, weight=2)
        self.list_panel = list_panel
        self.detail_panel = detail_panel

        columns = ("queue", "title", "status", "project", "owner", "health", "updated")
        self.tree = ttk.Treeview(list_panel, columns=columns, show="tree headings", style="Dashboard.Treeview")
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=34, minwidth=34, stretch=False)
        self.heading_specs: dict[str, tuple[str, Literal["center", "w"]]] = {
            "queue": ("queue", "center"),
            "title": ("goal", "w"),
            "status": ("status", "w"),
            "project": ("project", "w"),
            "owner": ("owner", "w"),
            "health": ("health", "w"),
            "updated": ("updated", "center"),
        }
        initial_columns = responsive_layout(1440).columns
        for column, (label_key, anchor) in self.heading_specs.items():
            self.tree.heading(column, text=self._t(label_key).upper())
            self.tree.column(
                column,
                width=initial_columns[column],
                minwidth=38,
                anchor=anchor,
                stretch=column in {"title", "project"},
            )

        scrollbar = ttk.Scrollbar(list_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<ButtonPress-1>", self._on_tree_button_press, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_tree_button_release, add="+")
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Return>", lambda _event: self.open_source("contract_path"))
        for tone, background, foreground in (
            ("active", COLORS["accent_dark"], COLORS["text"]),
            ("critical", COLORS["critical_dark"], COLORS["text"]),
            ("warning", COLORS["warning_dark"], COLORS["text"]),
            ("complete", COLORS["complete_dark"], COLORS["muted"]),
            ("neutral", COLORS["panel"], COLORS["text"]),
            ("repository", COLORS["blue_dark"], COLORS["text"]),
        ):
            self.tree.tag_configure(tone, background=background, foreground=foreground)

        self._build_detail(detail_panel)

    def _build_detail(self, parent: tk.Misc) -> None:
        canvas = tk.Canvas(parent, bg=COLORS["panel"], highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=COLORS["panel"], padx=20, pady=15)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(body_window, width=event.width))
        canvas.bind("<Enter>", lambda _event: self.root.bind_all("<MouseWheel>", self._scroll_detail))
        canvas.bind("<Leave>", lambda _event: self.root.unbind_all("<MouseWheel>"))
        self.detail_canvas = canvas
        self.dossier_label = tk.Label(
            body,
            text=self._t("goal_dossier").upper(),
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )
        self.dossier_label.pack(anchor="w")
        title_label = tk.Label(
            body,
            textvariable=self.detail_title,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(self._font("Bahnschrift SemiBold", "TkHeadingFont"), 18),
            justify="left",
            wraplength=330,
        )
        title_label.pack(anchor="w", pady=(7, 3))
        key_label = tk.Label(
            body,
            textvariable=self.detail_key,
            bg=COLORS["panel"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8),
            wraplength=330,
            justify="left",
        )
        key_label.pack(anchor="w")
        self.detail_wrapped_labels.extend((title_label, key_label))

        self._build_source_actions(body)

        self.detail_section_labels: dict[str, tk.Label] = {}
        self._detail_section(body, "lifecycle", self.detail_meta)
        self._detail_section(body, "exact_gate", self.detail_gate)
        self._detail_section(body, "health", self.detail_health)
        self._detail_section(body, "issues", self.detail_issues)

    def _build_source_actions(self, parent: tk.Misc) -> None:
        path_area = tk.Frame(parent, bg=COLORS["panel"])
        path_area.pack(fill="x", pady=(12, 3))
        self.source_label = tk.Label(
            path_area,
            text=self._t("source_artifacts").upper(),
            bg=COLORS["panel"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )
        self.source_label.pack(anchor="w", pady=(0, 6))
        self.path_buttons: dict[str, tk.Button] = {}
        self.path_button_labels = {
            "contract_path": "contract",
            "plan_path": "plan",
            "evidence_path": "evidence",
        }
        button_row = tk.Frame(path_area, bg=COLORS["panel"])
        button_row.pack(fill="x")
        for index, (field, label) in enumerate(
            (
                ("contract_path", "contract"),
                ("plan_path", "plan"),
                ("evidence_path", "evidence"),
            )
        ):
            button = self._button(button_row, self._t(label).upper(), lambda name=field: self.open_source(name))
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 3, 0 if index == 2 else 3))
            button_row.grid_columnconfigure(index, weight=1)
            button.configure(state="disabled")
            self.path_buttons[field] = button

    def _detail_section(self, parent: tk.Misc, label_key: str, variable: tk.StringVar) -> None:
        section = tk.Frame(parent, bg=COLORS["panel"], pady=6)
        section.pack(fill="x")
        tk.Frame(section, bg=COLORS["border_soft"], height=1).pack(fill="x", pady=(0, 6))
        label = tk.Label(
            section,
            text=self._t(label_key).upper(),
            bg=COLORS["panel"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )
        label.pack(anchor="w")
        self.detail_section_labels[label_key] = label
        value_label = tk.Label(
            section,
            textvariable=variable,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(self._font("Segoe UI", "TkDefaultFont"), 10),
            justify="left",
            wraplength=330,
        )
        value_label.pack(anchor="w", pady=(2, 0))
        self.detail_wrapped_labels.append(value_label)

    def _button(self, parent: tk.Misc, text: str, command: Callable[[], None], *, accent: bool = False) -> tk.Button:
        background = COLORS["accent"] if accent else COLORS["panel_alt"]
        foreground = COLORS["bg"] if accent else COLORS["text"]
        active_background = "#78E1CC" if accent else COLORS["panel_high"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground=foreground,
            disabledforeground=COLORS["faint"],
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=15,
            pady=9,
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        )

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-r>", lambda _event: self.refresh())
        self.root.bind("<Control-f>", lambda _event: self.search_entry.focus_set())
        self.root.bind("<Escape>", lambda _event: self.search_var.set(""))
        self.root.bind("<Configure>", self._schedule_responsive_layout)

    def _column_before_separator(self, x: int) -> str | None:
        """Return the data column immediately to the left of a header separator."""
        identifier = self.tree.identify_column(max(0, x - 2))
        if not identifier.startswith("#") or identifier == "#0":
            return None
        try:
            index = int(identifier[1:]) - 1
        except ValueError:
            return None
        columns = self.tree.cget("columns")
        return columns[index] if 0 <= index < len(columns) else None

    def _on_tree_button_press(self, event: tk.Event[tk.Misc]) -> None:
        self._resizing_column = (
            self._column_before_separator(event.x)
            if self.tree.identify_region(event.x, event.y) == "separator"
            else None
        )

    def _on_tree_button_release(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resizing_column is not None:
            self._manual_column_widths[self._resizing_column] = int(self.tree.column(self._resizing_column, "width"))
        self._resizing_column = None

    def _on_tree_double_click(self, event: tk.Event[tk.Misc]) -> str | None:
        if self.tree.identify_region(event.x, event.y) == "separator":
            column = self._column_before_separator(event.x)
            if column is not None:
                self._autofit_tree_column(column)
            return "break"
        self.open_source("contract_path")
        return None

    def _autofit_tree_column(self, column: str) -> None:
        """Fit a visible data column to its heading and currently rendered values."""
        columns = self.tree.cget("columns")
        index = columns.index(column)
        style = ttk.Style(self.root)
        cell_font = tkfont.Font(font=style.lookup("Dashboard.Treeview", "font"))
        heading_font = tkfont.Font(font=style.lookup("Dashboard.Treeview.Heading", "font"))
        widest = heading_font.measure(str(self.tree.heading(column, "text")))
        for item_id in self.tree.get_children(""):
            widest = max(widest, self._widest_tree_value(item_id, index, cell_font))
        width = max(38, min(COLUMN_AUTOFIT_MAX_WIDTH, widest + COLUMN_AUTOFIT_PADDING))
        self.tree.column(column, width=width, minwidth=38, stretch=False)
        self._manual_column_widths[column] = width

    def _widest_tree_value(self, item_id: str, column_index: int, font: tkfont.Font) -> int:
        values = self.tree.item(item_id, "values")
        value = str(values[column_index]) if column_index < len(values) else ""
        widest = font.measure(value)
        for child_id in self.tree.get_children(item_id):
            widest = max(widest, self._widest_tree_value(child_id, column_index, font))
        return widest

    def _scroll_detail(self, event: tk.Event[tk.Misc]) -> None:
        delta = -1 if event.delta > 0 else 1
        self.detail_canvas.yview_scroll(delta * 3, "units")

    def _schedule_responsive_layout(self, event: tk.Event[tk.Misc] | None = None) -> None:
        if event is not None and event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._resize_job = None
        layout = responsive_layout(self.root.winfo_width())
        for column, width in layout.columns.items():
            hidden = width == 0
            effective_width = self._manual_column_widths.get(column, width)
            self.tree.column(
                column,
                width=0 if hidden else effective_width,
                minwidth=0 if hidden else 38,
                stretch=False if hidden or column in self._manual_column_widths else column in {"title", "project"},
            )
        for label in self.detail_wrapped_labels:
            label.configure(wraplength=layout.detail_wrap)
        self.detail_panel.configure(width=layout.detail_width)
        pane_width = self.workspace_pane.winfo_width()
        if pane_width > layout.detail_width + 520:
            try:
                self.workspace_pane.sashpos(0, pane_width - layout.detail_width - 8)
            except tk.TclError:
                pass

    def refresh(self, initial: bool = False) -> None:
        started = time.perf_counter()
        try:
            self.model = self.session.refresh()
            self.last_error = None
            self.entry_by_key = {entry.goal_key: entry for entry in self.model.entries}
            self._update_filter_options()
            self._update_metrics()
            self.apply_filters(select_goal=self.model.next_goal or self.model.next_planned_goal)
            elapsed_ms = (time.perf_counter() - started) * 1000
            startup_ms = (time.perf_counter() - self._startup_started) * 1000
            self.status_line.set(
                self._t(
                    "goals_refreshed",
                    count=len(self.model.entries),
                    elapsed=elapsed_ms,
                    generated=self.model.generated_at or "unknown",
                ) + (f"  •  {self._t('startup', elapsed=startup_ms)}" if initial else "")
            )
        except DashboardError as exc:
            self.model = None
            self.last_error = str(exc)
            self.entry_by_key.clear()
            self.repository_by_iid.clear()
            self.visible_entries.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.status_line.set(f"{self._t('load_error')}  •  {exc}")
            if not initial:
                messagebox.showerror("AgentGoals", str(exc), parent=self.root)

    def _update_filter_options(self) -> None:
        if self.model is None:
            return
        self.combos["status"].configure(values=(self._display_filter_value("all"), *(self._display_filter_value(value) for value in self.model.options.statuses)))
        self.combos["project"].configure(values=(self._display_filter_value("all"), *self.model.options.projects))
        self.combos["owner"].configure(values=(self._display_filter_value("all"), *(self._display_filter_value(value) for value in self.model.options.owners)))
        self.combos["root"].configure(values=(self._display_filter_value("all"), *self.model.options.roots))
        self.combos["health"].configure(values=(self._display_filter_value("all"), *(self._display_filter_value(value) for value in self.model.options.health)))
        for variable in (self.status_var, self.project_var, self.owner_var, self.root_var, self.health_var):
            if variable.get() == "all":
                variable.set(self._display_filter_value("all"))

    def _update_metrics(self) -> None:
        if self.model is None:
            return
        summary = self.model.summary
        for key, value in (
            ("open", summary.open),
            ("runnable", summary.runnable),
            ("blocked", summary.blocked),
            ("review_pending", summary.review_pending),
            ("stale", summary.stale),
            ("completed", summary.completed),
        ):
            self.metric_cards[key].set(value)

    def _schedule_filter(self, *_args: object) -> None:
        if self._filter_job:
            self.root.after_cancel(self._filter_job)
        self._filter_job = self.root.after(80, self.apply_filters)

    def apply_filters(self, select_goal: str | None = None) -> None:
        self._filter_job = None
        if self.model is None:
            return
        filters = DashboardFilters(
            query=self.search_var.get(),
            status=self._filter_choice(self.status_var.get()),
            project=self._filter_choice(self.project_var.get()),
            owner=self._filter_choice(self.owner_var.get()),
            root_id=self._filter_choice(self.root_var.get()),
            health=self._filter_choice(self.health_var.get()),
        )
        self.visible_entries = filter_dashboard_entries(self.model.entries, filters)
        repository_groups = group_dashboard_entries(self.visible_entries)
        self.repository_by_iid.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for group in repository_groups:
            repo_iid = f"repo::{group.root_id}"
            self.repository_by_iid[repo_iid] = group
            self.tree.insert(
                "",
                "end",
                iid=repo_iid,
                open=True,
                values=(
                    "",
                    group.root_id.upper(),
                    f"{group.open} {self._t('open').upper()}",
                    f"{group.total} {self._t('goal').upper()}",
                    "",
                    f"{group.blocked} {self._t('blocked').upper()}",
                    "",
                ),
                tags=("repository",),
            )
            for entry in group.entries:
                self.tree.insert(
                    repo_iid,
                    "end",
                    iid=entry.goal_key,
                    values=(
                        format_queue_position(entry.queue_position),
                        entry.title,
                        self._localize_value(entry.status),
                        entry.project,
                        entry.display_owner,
                        self._localize_value(entry.health_status),
                        entry.updated or "—",
                    ),
                    tags=(status_tone(entry.status),),
                )
        target = select_goal if select_goal in {entry.goal_key for entry in self.visible_entries} else None
        if not target and self.visible_entries:
            target = self.visible_entries[0].goal_key
        if target:
            self.tree.selection_set(target)
            self.tree.focus(target)
            self.tree.see(target)
            parent = self.tree.parent(target)
            if parent:
                self.tree.see(parent)
            self._show_detail(self.entry_by_key[target])
        else:
            self._clear_detail()
        base = self.status_line.get().split("  •  showing")[0]
        self.status_line.set(f"{base}  •  {self._t('showing', count=len(self.visible_entries))}")

    def _on_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if selection and selection[0] in self.entry_by_key:
            self._show_detail(self.entry_by_key[selection[0]])
        elif selection and selection[0] in self.repository_by_iid:
            self._show_repository_detail(self.repository_by_iid[selection[0]])

    def _show_repository_detail(self, group: RepositoryGroup) -> None:
        self.detail_title.set(group.root_id)
        self.detail_key.set(self._t("repository_summary", total=group.total))
        self.detail_meta.set(self._t("repository_meta", open=group.open, runnable=group.runnable, blocked=group.blocked))
        next_entry = next(
            (entry for entry in group.entries if entry.scheduling_status in {"runnable", "in_progress"}),
            None,
        )
        self.detail_gate.set(
            self._t("next_in_repository", title=next_entry.title)
            if next_entry else self._t("no_runnable_repository")
        )
        self.detail_health.set(self._t("repository_health"))
        self.detail_issues.set(self._t("repository_issues"))
        for button in self.path_buttons.values():
            button.configure(state="disabled")

    def _show_detail(self, entry: DashboardEntry) -> None:
        self.detail_title.set(entry.title)
        self.detail_key.set(entry.goal_key)
        self.detail_meta.set(
            f"{self._localize_value(entry.status)}  ·  {self._localize_value(entry.scheduling_status)}\n"
            + self._t(
                "priority_queue_owner",
                priority=entry.priority,
                queue=format_queue_position(entry.queue_position),
                owner=self._display_filter_value(entry.display_owner),
            )
        )
        gate = entry.next_action or entry.blocked_reason
        if not gate and entry.unmet_dependencies:
            gate = self._t("waiting_on", dependencies=", ".join(entry.unmet_dependencies))
        self.detail_gate.set(gate or self._t("no_next_action"))
        self.detail_health.set(self._localize_value(entry.health_status))
        self.detail_issues.set(entry.issue_label)
        for field_name, button in self.path_buttons.items():
            button.configure(state="normal" if getattr(entry, field_name) else "disabled")

    def _clear_detail(self) -> None:
        self.detail_title.set(self._t("no_matching_goal"))
        self.detail_key.set(self._t("adjust_filters"))
        self.detail_meta.set("")
        self.detail_gate.set("")
        self.detail_health.set("")
        self.detail_issues.set("")
        for button in self.path_buttons.values():
            button.configure(state="disabled")

    def open_source(self, field_name: str) -> None:
        selection = self.tree.selection()
        if not selection or selection[0] not in self.entry_by_key:
            return
        try:
            self.session.open_source(selection[0], field_name)
            self.status_line.set(self._t("opened", source=self._t(field_name.replace("_path", "")), goal=selection[0]))
        except DashboardError as exc:
            self.status_line.set(f"{self._t('open_error')}  •  {exc}")
            messagebox.showerror("AgentGoals", str(exc), parent=self.root)


def benchmark_state(state_path: Path, iterations: int) -> dict[str, object]:
    session = DashboardSession(state_path)
    samples = []
    model = None
    for _ in range(max(1, iterations)):
        started = time.perf_counter()
        model = session.refresh()
        samples.append((time.perf_counter() - started) * 1000)
    assert model is not None
    return {
        "state": str(state_path.resolve()),
        "entries": len(model.entries),
        "iterations": len(samples),
        "min_ms": round(min(samples), 3),
        "mean_ms": round(sum(samples) / len(samples), 3),
        "max_ms": round(max(samples), 3),
        "budget_ms": 500,
        "passed": max(samples) <= 500,
    }


def discover_state_path(
    requested: Path,
    *,
    cwd: Path | None = None,
    executable: Path | None = None,
) -> Path:
    if requested.is_absolute():
        return requested.resolve()
    working_directory = (cwd or Path.cwd()).resolve()
    executable_path = (executable or Path(sys.executable)).resolve()
    candidates = [working_directory / requested]
    candidates.extend(parent / requested for parent in (executable_path.parent, *executable_path.parents))
    candidates.append(Path(__file__).resolve().parents[2] / requested)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return (working_directory / requested).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the local read-only AgentGoals desktop dashboard.")
    parser.add_argument("--state", type=Path, default=Path("outputs/global/STATE.json"))
    parser.add_argument("--benchmark", action="store_true", help="Measure validated STATE refresh without opening UI.")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--smoke", action="store_true", help="Create and lay out the desktop window, then exit.")
    parser.add_argument("--probe-output", type=Path, help="Write benchmark or smoke JSON to a file for windowed builds.")
    return parser


def emit_result(payload: dict[str, object], probe_output: Path | None = None, *, stderr: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    if probe_output is not None:
        output_path = probe_output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text, file=sys.stderr if stderr else sys.stdout)


def build_smoke_result(
    *,
    entries: int | None,
    geometry: str,
    state: str,
    error: str | None,
) -> tuple[dict[str, object], int]:
    loaded = entries is not None
    return (
        {
            "status": "passed" if loaded else "failed",
            "entries": entries if loaded else 0,
            "geometry": geometry,
            "state": state,
            "error": error,
        },
        0 if loaded else 2,
    )


def main() -> None:
    startup_started = time.perf_counter()
    args = build_parser().parse_args()
    state_path = discover_state_path(args.state)
    if args.benchmark:
        try:
            emit_result(benchmark_state(state_path, args.iterations), args.probe_output)
        except DashboardError as exc:
            emit_result({"error": str(exc)}, args.probe_output, stderr=True)
            raise SystemExit(2) from exc
        return

    root = tk.Tk()
    if args.smoke:
        root.withdraw()
    app = DashboardApplication(root, state_path, startup_started=startup_started)
    if args.smoke:
        root.update_idletasks()
        payload, exit_code = build_smoke_result(
            entries=len(app.model.entries) if app.model is not None else None,
            geometry=root.geometry(),
            state=str(app.state_path),
            error=app.last_error,
        )
        emit_result(payload, args.probe_output)
        root.destroy()
        if exit_code:
            raise SystemExit(exit_code)
        return
    root.mainloop()

if __name__ == "__main__":
    main()
