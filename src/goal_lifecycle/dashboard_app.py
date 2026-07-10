from __future__ import annotations

import argparse
import json
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from goal_lifecycle.dashboard import (
    DashboardEntry,
    DashboardError,
    DashboardFilters,
    DashboardModel,
    DashboardSession,
    filter_dashboard_entries,
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
        tk.Label(
            self,
            text=label.upper(),
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Cascadia Mono", 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(1, 0))

    def set(self, value: int) -> None:
        self.value.configure(text=str(value))


class DashboardApplication:
    def __init__(self, root: tk.Tk, state_path: Path, *, startup_started: float | None = None) -> None:
        self.root = root
        self.state_path = state_path.resolve()
        self.session = DashboardSession(self.state_path)
        self.model: DashboardModel | None = None
        self.visible_entries: list[DashboardEntry] = []
        self.entry_by_key: dict[str, DashboardEntry] = {}
        self._filter_job: str | None = None
        self._resize_job: str | None = None
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
        self.detail_title = tk.StringVar(value="Select a Goal")
        self.detail_key = tk.StringVar(value="No source selected")
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

    def _configure_window(self) -> None:
        self.root.title("Goal Control — Local Dashboard")
        self.root.configure(bg=COLORS["bg"])
        self.root.geometry("1440x860")
        self.root.minsize(1080, 680)

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
        tk.Label(
            status,
            text="READ ONLY  •  CTRL+R REFRESH  •  CTRL+F SEARCH",
            bg=COLORS["bg"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        ).pack(side="right")

    def _build_header(self, parent: tk.Misc) -> None:
        header = tk.Frame(parent, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 16))

        brand = tk.Frame(header, bg=COLORS["bg"])
        brand.pack(side="left")
        tk.Label(
            brand,
            text="GOAL / CONTROL",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=(self._font("Bahnschrift SemiBold", "TkHeadingFont"), 24),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="LOCAL LIFECYCLE OBSERVATORY",
            bg=COLORS["bg"],
            fg=COLORS["accent"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 9, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, bg=COLORS["bg"])
        actions.pack(side="right")
        tk.Label(
            actions,
            text=str(self.state_path),
            bg=COLORS["bg"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8),
        ).pack(anchor="e", pady=(0, 6))
        self._button(actions, "↻  REFRESH", self.refresh, accent=True).pack(anchor="e")

    def _build_metrics(self, parent: tk.Misc) -> None:
        metrics = tk.Frame(parent, bg=COLORS["bg"])
        metrics.pack(fill="x", pady=(0, 14))
        self.metric_cards: dict[str, MetricCard] = {}
        specs = (
            ("open", "Open", COLORS["blue"]),
            ("runnable", "Runnable", COLORS["accent"]),
            ("blocked", "Blocked", COLORS["critical"]),
            ("review_pending", "Review", COLORS["warning"]),
            ("stale", "Stale", "#C58BFF"),
            ("completed", "Completed", COLORS["complete"]),
        )
        for index, (key, label, accent) in enumerate(specs):
            card = MetricCard(metrics, label, accent)
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
        for key, label, variable, width in (
            ("status", "STATUS", self.status_var, 15),
            ("project", "PROJECT", self.project_var, 18),
            ("owner", "OWNER", self.owner_var, 15),
            ("root", "REPO", self.root_var, 15),
            ("health", "HEALTH", self.health_var, 12),
        ):
            block = tk.Frame(bar, bg=COLORS["panel"])
            block.pack(side="left", padx=(0, 8))
            tk.Label(
                block,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["faint"],
                font=(self._font("Cascadia Mono", "TkFixedFont"), 7, "bold"),
            ).pack(anchor="w")
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
        self.tree = ttk.Treeview(list_panel, columns=columns, show="headings", style="Dashboard.Treeview")
        headings = {
            "queue": ("Q", "center"),
            "title": ("GOAL", "w"),
            "status": ("STATUS", "w"),
            "project": ("PROJECT", "w"),
            "owner": ("OWNER", "w"),
            "health": ("HEALTH", "w"),
            "updated": ("UPDATED", "center"),
        }
        initial_columns = responsive_layout(1440).columns
        for column, (label, anchor) in headings.items():
            self.tree.heading(column, text=label)
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
        self.tree.bind("<Double-1>", lambda _event: self.open_source("contract_path"))
        self.tree.bind("<Return>", lambda _event: self.open_source("contract_path"))
        for tone, background, foreground in (
            ("active", COLORS["accent_dark"], COLORS["text"]),
            ("critical", COLORS["critical_dark"], COLORS["text"]),
            ("warning", COLORS["warning_dark"], COLORS["text"]),
            ("complete", COLORS["complete_dark"], COLORS["muted"]),
            ("neutral", COLORS["panel"], COLORS["text"]),
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
        tk.Label(
            body,
            text="GOAL DOSSIER",
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        ).pack(anchor="w")
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

        self._detail_section(body, "LIFECYCLE", self.detail_meta)
        self._detail_section(body, "EXACT GATE", self.detail_gate)
        self._detail_section(body, "HEALTH", self.detail_health)
        self._detail_section(body, "ISSUES", self.detail_issues)

    def _build_source_actions(self, parent: tk.Misc) -> None:
        path_area = tk.Frame(parent, bg=COLORS["panel"])
        path_area.pack(fill="x", pady=(12, 3))
        tk.Label(
            path_area,
            text="SOURCE ARTIFACTS",
            bg=COLORS["panel"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        self.path_buttons: dict[str, tk.Button] = {}
        button_row = tk.Frame(path_area, bg=COLORS["panel"])
        button_row.pack(fill="x")
        for index, (field, label) in enumerate(
            (
                ("contract_path", "CONTRACT"),
                ("plan_path", "PLAN"),
                ("evidence_path", "EVIDENCE"),
            )
        ):
            button = self._button(button_row, label, lambda name=field: self.open_source(name))
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 3, 0 if index == 2 else 3))
            button_row.grid_columnconfigure(index, weight=1)
            button.configure(state="disabled")
            self.path_buttons[field] = button

    def _detail_section(self, parent: tk.Misc, label: str, variable: tk.StringVar) -> None:
        section = tk.Frame(parent, bg=COLORS["panel"], pady=6)
        section.pack(fill="x")
        tk.Frame(section, bg=COLORS["border_soft"], height=1).pack(fill="x", pady=(0, 6))
        tk.Label(
            section,
            text=label,
            bg=COLORS["panel"],
            fg=COLORS["faint"],
            font=(self._font("Cascadia Mono", "TkFixedFont"), 8, "bold"),
        ).pack(anchor="w")
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

    def _button(self, parent: tk.Misc, text: str, command: object, *, accent: bool = False) -> tk.Button:
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
            self.tree.column(
                column,
                width=width,
                minwidth=0 if hidden else 38,
                stretch=False if hidden else column in {"title", "project"},
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
                f"{len(self.model.entries)} Goals  •  refreshed {elapsed_ms:.1f} ms  •  "
                f"generated {self.model.generated_at or 'unknown'}"
                + (f"  •  startup {startup_ms:.1f} ms" if initial else "")
            )
        except DashboardError as exc:
            self.model = None
            self.last_error = str(exc)
            self.entry_by_key.clear()
            self.visible_entries.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.status_line.set(f"LOAD ERROR  •  {exc}")
            if not initial:
                messagebox.showerror("Goal Control", str(exc), parent=self.root)

    def _update_filter_options(self) -> None:
        if self.model is None:
            return
        self.combos["status"].configure(values=("all", *self.model.options.statuses))
        self.combos["project"].configure(values=("all", *self.model.options.projects))
        self.combos["owner"].configure(values=("all", *self.model.options.owners))
        self.combos["root"].configure(values=("all", *self.model.options.roots))
        self.combos["health"].configure(values=("all", *self.model.options.health))

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
            status=self.status_var.get(),
            project=self.project_var.get(),
            owner=self.owner_var.get(),
            root_id=self.root_var.get(),
            health=self.health_var.get(),
        )
        self.visible_entries = filter_dashboard_entries(self.model.entries, filters)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for entry in self.visible_entries:
            self.tree.insert(
                "",
                "end",
                iid=entry.goal_key,
                values=(
                    format_queue_position(entry.queue_position),
                    entry.title,
                    entry.status.replace("_", " ").upper(),
                    entry.project,
                    entry.display_owner,
                    entry.health_status.upper(),
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
            self._show_detail(self.entry_by_key[target])
        else:
            self._clear_detail()
        base = self.status_line.get().split("  •  showing")[0]
        self.status_line.set(f"{base}  •  showing {len(self.visible_entries)}")

    def _on_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if selection and selection[0] in self.entry_by_key:
            self._show_detail(self.entry_by_key[selection[0]])

    def _show_detail(self, entry: DashboardEntry) -> None:
        self.detail_title.set(entry.title)
        self.detail_key.set(entry.goal_key)
        self.detail_meta.set(
            f"{entry.status.replace('_', ' ').upper()}  ·  {entry.scheduling_status.replace('_', ' ').upper()}\n"
            f"Priority {entry.priority}  ·  Queue {format_queue_position(entry.queue_position)}  ·  {entry.display_owner}"
        )
        gate = entry.next_action or entry.blocked_reason
        if not gate and entry.unmet_dependencies:
            gate = "Waiting on " + ", ".join(entry.unmet_dependencies)
        self.detail_gate.set(gate or "No explicit next action recorded")
        self.detail_health.set(entry.health_label)
        self.detail_issues.set(entry.issue_label)
        for field_name, button in self.path_buttons.items():
            button.configure(state="normal" if getattr(entry, field_name) else "disabled")

    def _clear_detail(self) -> None:
        self.detail_title.set("No matching Goal")
        self.detail_key.set("Adjust filters or refresh the source STATE")
        self.detail_meta.set("")
        self.detail_gate.set("")
        self.detail_health.set("")
        self.detail_issues.set("")
        for button in self.path_buttons.values():
            button.configure(state="disabled")

    def open_source(self, field_name: str) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        try:
            self.session.open_source(selection[0], field_name)
            self.status_line.set(f"Opened {field_name.replace('_path', '')} for {selection[0]}")
        except DashboardError as exc:
            self.status_line.set(f"OPEN ERROR  •  {exc}")
            messagebox.showerror("Goal Control", str(exc), parent=self.root)


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
    parser = argparse.ArgumentParser(description="Open the local read-only Goal Control desktop dashboard.")
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
        emit_result(
            {
                "status": "passed" if app.model is not None else "failed",
                "entries": len(app.model.entries) if app.model else 0,
                "geometry": root.geometry(),
                "state": str(app.state_path),
                "error": app.last_error,
            },
            args.probe_output,
        )
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
