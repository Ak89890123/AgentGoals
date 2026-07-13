# AgentGoals Desktop Shell Spike

Date: 2026-07-11

## Decision

Use the native Python 3.11 / Tk 8.6 desktop shell for the first Windows release and package it as a PyInstaller onedir application.

This keeps the existing AgentGoals Python implementation authoritative, adds no browser or server runtime, and meets the measured startup, memory, refresh, and installed-size budgets.

## Local capability findings

- Python 3.11.15 and Tk 8.6 are available. Interpreter-level Tk initialization measured 33.72 ms.
- Node 24.14, npm 11.9, Rust 1.96, Go, .NET, and WebView2 150 are installed.
- No Tauri crates were present in the local Cargo source cache.
- `pywebview`, PySide6, CEF Python, and PyInstaller were not initially installed.
- PyInstaller 6.21 was added only to the repo-local `.venv` through the `desktop` optional dependency.

## Candidate comparison

| Candidate | Python-core reuse | Added runtime/build surface | Packaging risk | First-release decision |
|---|---:|---:|---:|---|
| Native Tk | direct | Tk ships with Python | low | selected |
| Tauri + Python sidecar | indirect | Rust, Node, WebView2, sidecar | high | defer |
| pywebview | direct bridge | new Python package + WebView2 | medium | defer |
| Electron | indirect | bundled Chromium + Node | high size/memory | reject |

Online framework documentation lookup was attempted but blocked by the active network gateway. The first-release decision therefore rests on directly measured local capability, dependency count, integration boundaries, and packaged results rather than unverified web claims.

## Packaging iteration

- PyInstaller onefile candidate: 11.79 MB executable, 47.84 MB working set, but 2.036 s mean cold-start measurement with a 2.16 s outlier. It failed the strict startup direction and was not retained.
- PyInstaller onedir candidate: 29.59 MB installed folder, 39.8 MB working set, 1.049 s mean and 1.167 s max over the final five-run cold-start check. It passed all Contract budgets.

The onedir package is intentional. `AgentGoals.exe` must remain beside its `_internal` directory.

## Final measured result

- Validated 12-entry STATE refresh: 3.49 ms mean, 4.53 ms max over 20 iterations.
- Synthetic 1,000-Goal build and filter: 7.03 ms mean, 7.49 ms max over 20 iterations.
- Packaged cold start: 1,048.98 ms mean, 1,167.35 ms max over 5 iterations.
- Working set: 39.8 MB; private memory: 22.35 MB.
- Installed package: 29.59 MB.

## Recovery

Delete the ignored `dist/agentgoals-dashboard/` output and continue using the existing STATE JSON/Markdown commands. The desktop shell does not mutate Goal sources or registries and is not required by reconciliation, aggregation, validation, queue, onboarding, or handoff commands.
