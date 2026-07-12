from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from goal_lifecycle.io import atomic_write_text
from goal_lifecycle.skill_eval import load_manifest


MODEL_DECISION_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "skill-eval-model-decision.schema.json"


def plan_runs(manifest: dict[str, Any], runs: int) -> list[dict[str, str]]:
    return [
        {"run_id": f"run-{run_index}", "case_id": case["id"], "language": case["language"]}
        for run_index in range(1, runs + 1)
        for case in manifest["cases"]
    ]


def build_prompt(skill_text: str, prompt: str) -> str:
    return "\n".join(
        (
            "You are an isolated behavior-evaluation runtime.",
            "Apply the supplied Goal Preflight policy to the user prompt below.",
            "Do not modify the supplied policy or any source file. If the policy calls for durable output, create only the required Markdown artifacts under ./artifacts. Do not write elsewhere.",
            "Return only the JSON decision required by the output schema.",
            "\n--- Goal Preflight policy ---\n",
            skill_text,
            "\n--- User prompt ---\n",
            prompt,
        )
    )


def execute(
    manifest_path: Path,
    out_dir: Path,
    *,
    runs: int,
    codex_command: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    skill_path = Path(manifest["skill"]["path"])
    if not skill_path.is_file():
        raise ValueError(f"Frozen Skill is unavailable: {skill_path}")
    skill_text = skill_path.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    observations = []
    for run_index in range(1, runs + 1):
        decisions = []
        for case in manifest["cases"]:
            workspace = out_dir / "workspaces" / f"run-{run_index}" / case["id"]
            workspace.mkdir(parents=True, exist_ok=True)
            final = workspace / "final.json"
            command = [
                codex_command,
                "exec",
                "--ephemeral",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "--cd",
                str(workspace),
                "--output-schema",
                str(MODEL_DECISION_SCHEMA),
                "--output-last-message",
                str(final),
            ]
            if model:
                command.extend(("--model", model))
            if reasoning_effort:
                command.extend(("--config", f'model_reasoning_effort="{reasoning_effort}"'))
            result = subprocess.run(
                command + ["-"],
                input=build_prompt(skill_text, case["prompt"]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0 or not final.is_file():
                raise RuntimeError(f"{case['id']} in run-{run_index} failed: {result.stderr.strip() or result.stdout.strip()}")
            decision = json.loads(final.read_text(encoding="utf-8"))
            artifacts = sorted((path.relative_to(out_dir).as_posix() for path in (workspace / "artifacts").rglob("*.md"))) if (workspace / "artifacts").is_dir() else []
            decisions.append({"case_id": case["id"], **decision, "reference_loads": [], "artifact_paths": artifacts})
        observations.append({"id": f"run-{run_index}", "observations": decisions})
    payload = {
        "version": 1,
        "manifest_version": manifest["version"],
        "skill_sha256": manifest["skill"]["sha256"],
        "observation_source": "model_runtime",
        "runtime": {
            "command": codex_command,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "mode": "isolated_codex_exec",
        },
        "runs": observations,
    }
    atomic_write_text(out_dir / "observations.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return {"status": "completed", "observations": str((out_dir / "observations.json").resolve()), "run_count": runs, "case_count": len(manifest["cases"])}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or execute isolated Codex runtime observations for Goal Skill evaluation.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-model-runtime", action="store_true")
    parser.add_argument("--codex-command", default=shutil.which("codex") or "codex")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", choices=("none", "low", "medium", "high", "xhigh", "max"))
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    if args.runs < 1:
        parser.error("--runs must be positive")
    if not args.execute:
        print(json.dumps({"status": "dry_run", "planned": plan_runs(manifest, args.runs), "model_calls": len(manifest["cases"]) * args.runs}, ensure_ascii=False))
        return 0
    if not args.confirm_model_runtime:
        print(json.dumps({"status": "confirmation_required", "reason": "Use --confirm-model-runtime to authorize model calls."}, ensure_ascii=False))
        return 2
    try:
        print(
            json.dumps(
                execute(
                    args.manifest,
                    args.out,
                    runs=args.runs,
                    codex_command=args.codex_command,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                ),
                ensure_ascii=False,
            )
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
