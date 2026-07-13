from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path


def executable(venv_dir: Path, name: str) -> Path:
    directory = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    return directory / f"{name}{suffix}"


def exactly_one(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {pattern} in {directory}, found {len(matches)}")
    return matches[0]


def run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def install_and_smoke(dist_dir: Path, artifact_kind: str, venv_dir: Path) -> dict[str, object]:
    if venv_dir.exists():
        raise SystemExit(f"refusing to reuse existing smoke environment: {venv_dir}")
    artifact = exactly_one(dist_dir, "*.whl" if artifact_kind == "wheel" else "*.tar.gz")
    venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    python = executable(venv_dir, "python")
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(artifact)])

    agentgoals = executable(venv_dir, "agentgoals")
    legacy = executable(venv_dir, "goal-lifecycle")
    version = run([str(agentgoals), "--version"], capture_output=True).stdout.strip()
    legacy_version = run([str(legacy), "--version"], capture_output=True).stdout.strip()
    doctor = subprocess.run(
        [str(agentgoals), "doctor", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if doctor.returncode not in {0, 2}:
        raise SystemExit(f"doctor failed with exit code {doctor.returncode}: {doctor.stderr}")
    payload = json.loads(doctor.stdout)
    if payload.get("version") != 1:
        raise SystemExit(f"doctor schema version mismatch: {payload!r}")

    return {
        "artifact": artifact.name,
        "artifact_kind": artifact_kind,
        "agentgoals_version": version,
        "goal_lifecycle_version": legacy_version,
        "doctor_exit_code": doctor.returncode,
        "doctor_status": payload.get("status"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install and smoke-test one built AgentGoals artifact.")
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--artifact", choices=("wheel", "sdist"), required=True)
    parser.add_argument("--venv-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = install_and_smoke(args.dist_dir, args.artifact, args.venv_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
