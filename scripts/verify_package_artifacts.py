from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import tomllib
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROJECT = "agentgoals"
EXPECTED_ENTRY_POINTS = (
    "agentgoals = agentgoals.cli:main",
    "goal-lifecycle = agentgoals.cli:main",
)
FORBIDDEN_BYTES = (
    b"c:\\devhome",
    b"c:/devhome",
    b"c:\\users\\",
    b"c:/users/",
    b"/home/runner/",
)
FORBIDDEN_PATH_PATTERNS = (
    re.compile(rb"(?i)(?<![A-Za-z0-9_])[a-z]:[\\/][^\r\n<>\"']*"),
    re.compile(
        rb"(?<![A-Za-z0-9_])\\\\[A-Za-z0-9._~-]+[\\/][A-Za-z0-9._~-]+(?:[\\/][A-Za-z0-9._~-]+)*"
    ),
    re.compile(
        rb"(?<![A-Za-z0-9_:/\\.])/(?=[A-Za-z0-9._~-])(?!/)[A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)*"
    ),
)
CAPTURED_ENVIRONMENT_PATTERNS = (
    re.compile(rb"(?m)(?:^|[\r\n])\s*(?:PATH|PYTHONPATH)\s*="),
)
SECRET_PATTERNS = (
    re.compile(rb"ghp_[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}", re.IGNORECASE),
    re.compile(rb"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}", re.IGNORECASE),
)


class ArtifactVerificationError(ValueError):
    pass


def project_version() -> str:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise ArtifactVerificationError("pyproject.toml project.version is missing")
    return version


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_no_forbidden_content(name: str, content: bytes) -> None:
    lowered = content.lower()
    for forbidden in FORBIDDEN_BYTES:
        if forbidden in lowered:
            raise ArtifactVerificationError(f"{name} contains forbidden machine-local content")
    if any(pattern.search(content) for pattern in FORBIDDEN_PATH_PATTERNS):
        raise ArtifactVerificationError(f"{name} contains a forbidden machine-local path")
    if any(pattern.search(content) for pattern in CAPTURED_ENVIRONMENT_PATTERNS):
        raise ArtifactVerificationError(f"{name} contains a captured environment path")
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        raise ArtifactVerificationError(f"{name} contains a high-signal credential pattern")


def ensure_no_forbidden_member(name: str) -> None:
    normalized = name.replace("\\", "/").lower()
    if ".venv" in normalized:
        raise ArtifactVerificationError(f"{name} contains a bundled virtual-environment member")
    if normalized == "readme.md" or normalized.endswith("/readme.md"):
        raise ArtifactVerificationError(f"{name} contains the operator README.md")
    if "/tests/" in f"/{normalized}/" or normalized.startswith("tests/"):
        raise ArtifactVerificationError(f"{name} contains a tests tree")


def ensure_artifact_filename(path: Path, expected_version: str, kind: str) -> None:
    if kind == "wheel":
        pattern = re.compile(
            rf"^{re.escape(EXPECTED_PROJECT)}-{re.escape(expected_version)}(?:-[^-]+){{3,4}}\.whl$"
        )
    elif kind == "sdist":
        pattern = re.compile(rf"^{re.escape(EXPECTED_PROJECT)}-{re.escape(expected_version)}\.tar\.gz$")
    else:
        raise ArtifactVerificationError(f"unsupported artifact kind: {kind}")
    if not pattern.fullmatch(path.name):
        raise ArtifactVerificationError(
            f"{kind} filename must identify {EXPECTED_PROJECT} {expected_version!r}: {path.name!r}"
        )


def verify_wheel(path: Path, expected_version: str) -> dict[str, object]:
    ensure_artifact_filename(path, expected_version, "wheel")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            ensure_no_forbidden_member(name)
            ensure_no_forbidden_content(name, archive.read(name))

        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ArtifactVerificationError("wheel must contain exactly one dist-info METADATA file")
        metadata = BytesParser(policy=policy.default).parsebytes(archive.read(metadata_names[0]))
        if metadata.get("Name") != EXPECTED_PROJECT:
            raise ArtifactVerificationError(f"wheel Name must be {EXPECTED_PROJECT!r}")
        version = metadata.get("Version")
        if not version:
            raise ArtifactVerificationError("wheel Version metadata is missing")
        if version != expected_version:
            raise ArtifactVerificationError(
                f"wheel Version must match project version {expected_version!r}, got {version!r}"
            )

        entry_point_names = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        if len(entry_point_names) != 1:
            raise ArtifactVerificationError("wheel must contain exactly one entry_points.txt file")
        entry_points = archive.read(entry_point_names[0]).decode("utf-8").splitlines()
        missing = [item for item in EXPECTED_ENTRY_POINTS if item not in entry_points]
        if missing:
            raise ArtifactVerificationError(f"wheel is missing entry points: {missing}")

    return {
        "kind": "wheel",
        "filename": path.name,
        "sha256": sha256(path),
        "member_count": len(names),
        "project": EXPECTED_PROJECT,
        "version": version,
    }


def verify_sdist(path: Path, expected_version: str) -> dict[str, object]:
    ensure_artifact_filename(path, expected_version, "sdist")
    with tarfile.open(path, mode="r:*") as archive:
        members = archive.getmembers()
        metadata_payloads: list[bytes] = []
        for member in members:
            ensure_no_forbidden_member(member.name)
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ArtifactVerificationError(f"could not read sdist member {member.name}")
            content = extracted.read()
            ensure_no_forbidden_content(member.name, content)
            if member.name.endswith(".egg-info/PKG-INFO"):
                metadata_payloads.append(content)

    if len(metadata_payloads) != 1:
        raise ArtifactVerificationError("sdist must contain exactly one egg-info PKG-INFO file")
    metadata = BytesParser(policy=policy.default).parsebytes(metadata_payloads[0])
    if metadata.get("Name") != EXPECTED_PROJECT:
        raise ArtifactVerificationError(f"sdist Name must be {EXPECTED_PROJECT!r}")
    version = metadata.get("Version")
    if not version:
        raise ArtifactVerificationError("sdist Version metadata is missing")
    if version != expected_version:
        raise ArtifactVerificationError(
            f"sdist Version must match project version {expected_version!r}, got {version!r}"
        )

    return {
        "kind": "sdist",
        "filename": path.name,
        "sha256": sha256(path),
        "member_count": len(members),
        "project": EXPECTED_PROJECT,
        "version": version,
    }


def exactly_one(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise ArtifactVerificationError(
            f"expected exactly one {pattern} in {directory.as_posix()}, found {len(matches)}"
        )
    return matches[0]


def verify_directory(directory: Path, expected_version: str | None = None) -> dict[str, object]:
    root = directory.resolve()
    if not root.is_dir():
        raise ArtifactVerificationError(f"artifact directory does not exist: {directory}")
    expected = expected_version or project_version()
    wheel = exactly_one(root, "*.whl")
    sdist = exactly_one(root, "*.tar.gz")
    artifacts = [verify_wheel(wheel, expected), verify_sdist(sdist, expected)]
    versions = {str(item["version"]) for item in artifacts if "version" in item}
    if versions != {expected}:
        raise ArtifactVerificationError(
            f"wheel and sdist artifact versions must equal project version {expected!r}, got {sorted(versions)!r}"
        )
    return {"version": 1, "status": "passed", "artifacts": artifacts}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify portable AgentGoals release artifacts.")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    try:
        result = verify_directory(build_parser().parse_args(argv).dist_dir)
    except (ArtifactVerificationError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(json.dumps({"version": 1, "status": "failed", "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
