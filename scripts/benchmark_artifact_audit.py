from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import uuid
from pathlib import Path

from goal_lifecycle.artifact_audit import begin_audit_receipt, complete_audit_receipt, list_audit_receipts
from goal_lifecycle.artifact_tool import ArtifactFile, ArtifactResult
from goal_lifecycle.io import atomic_write_text


def artifact_result(repo: Path, index: int, action: str) -> ArtifactResult:
    path = repo / "goals" / "active" / f"benchmark-{index}-goal-contract.md"
    return ArtifactResult(
        "applied" if action == "created" else "preview",
        (ArtifactFile(path, "", f"{index:064x}", action),),
    )


def summarize(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "iterations": len(samples),
        "mean_ms": round(statistics.fmean(samples) * 1000, 3),
        "p50_ms": round(ordered[math.ceil((len(ordered) - 1) * 0.50)] * 1000, 3),
        "p95_ms": round(ordered[math.ceil((len(ordered) - 1) * 0.95)] * 1000, 3),
        "max_ms": round(max(samples) * 1000, 3),
    }


def benchmark(repo: Path, iterations: int) -> dict[str, object]:
    jsonl_path = repo / "legacy-receipts.jsonl"
    jsonl_samples = []
    sqlite_samples = []

    for index in range(iterations):
        payload = {
            "version": 1,
            "mode": "apply",
            "status": "applied",
            "file_count": 1,
            "files": [
                {
                    "path": str(repo / "goals" / "active" / f"benchmark-{index}-goal-contract.md"),
                    "sha256": f"{index:064x}",
                    "action": "created",
                }
            ],
        }
        started = time.perf_counter()
        prior = jsonl_path.read_text(encoding="utf-8") if jsonl_path.is_file() else ""
        atomic_write_text(jsonl_path, prior + json.dumps(payload, sort_keys=True) + "\n")
        jsonl_samples.append(time.perf_counter() - started)

        planned = artifact_result(repo, index, "planned")
        created = artifact_result(repo, index, "created")
        started = time.perf_counter()
        receipt_id = begin_audit_receipt(repo, repo / "goals" / "active", f"benchmark-{index}", planned)
        complete_audit_receipt(repo, receipt_id, created)
        sqlite_samples.append(time.perf_counter() - started)

    started = time.perf_counter()
    rows = list_audit_receipts(repo)
    query_seconds = time.perf_counter() - started
    database = repo / ".goal-lifecycle" / "artifact-audit.sqlite"
    return {
        "scope": {
            "environment": "local filesystem; sequential warm process",
            "comparison": "legacy whole-history read/rewrite versus SQLite pending-plus-finalize transaction",
            "not_measured": [
                "fsync or power-loss durability",
                "multi-process lock contention",
                "cold-cache behavior",
                "production-scale retention or query load",
            ],
            "interpretation": "The operation shapes are intentionally different; do not use this as a general SQLite throughput claim.",
        },
        "iterations": iterations,
        "legacy_jsonl_rewrite": summarize(jsonl_samples),
        "sqlite_receipt_transaction": summarize(sqlite_samples),
        "sqlite_query_all": {"rows": len(rows), "elapsed_ms": round(query_seconds * 1000, 3)},
        "legacy_jsonl_bytes": jsonl_path.stat().st_size,
        "sqlite_bytes": database.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark legacy artifact JSONL rewrite against repo-local SQLite receipts.")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path(".tmp/tests"))
    args = parser.parse_args()
    if args.iterations < 2:
        parser.error("--iterations must be at least 2")
    root = args.out / f"artifact-audit-benchmark-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    result = benchmark(root.resolve(), args.iterations)
    result["output_root"] = str(root.resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
