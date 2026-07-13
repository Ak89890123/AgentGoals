from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_package_artifacts import ArtifactVerificationError, verify_directory


def write_wheel(
    path: Path,
    *,
    payload: bytes = b"__version__ = '0.2.1'\n",
    version: str = "0.2.1",
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("agentgoals/__init__.py", payload)
        archive.writestr(
            f"agentgoals-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: agentgoals\nVersion: {version}\n",
        )
        archive.writestr(
            f"agentgoals-{version}.dist-info/entry_points.txt",
            "[console_scripts]\nagentgoals = agentgoals.cli:main\ngoal-lifecycle = agentgoals.cli:main\n",
        )


def write_sdist(
    path: Path,
    *,
    member_name: str = "agentgoals-0.2.1/PACKAGE_README.md",
    version: str = "0.2.1",
) -> None:
    data = b"Portable AgentGoals package.\n"
    info = tarfile.TarInfo(member_name)
    info.size = len(data)
    metadata = f"Metadata-Version: 2.1\nName: agentgoals\nVersion: {version}\n".encode()
    metadata_info = tarfile.TarInfo(f"agentgoals-{version}/src/agentgoals.egg-info/PKG-INFO")
    metadata_info.size = len(metadata)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(data))
        archive.addfile(metadata_info, io.BytesIO(metadata))


def test_verifier_accepts_safe_wheel_and_sdist(tmp_path: Path) -> None:
    write_wheel(tmp_path / "agentgoals-0.2.1-py3-none-any.whl")
    write_sdist(tmp_path / "agentgoals-0.2.1.tar.gz")

    result = verify_directory(tmp_path)

    assert result["status"] == "passed"
    assert [item["kind"] for item in result["artifacts"]] == ["wheel", "sdist"]


@pytest.mark.parametrize(
    ("wheel_payload", "sdist_member"),
    [
        (b"C:\\devhome\\secret\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"D:\\Users\\someone\\private\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"D:\\work\\private\\file.txt\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"C:\\project\\private\\file.txt\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (br"\\server\share\file.txt" + b"\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"Q:\\\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"/Users/someone/private\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"/home/runner/work/private\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"/opt/private/file.txt\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"/tmp\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"PATH=C:\\private\\bin\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"PYTHONPATH=/private/src\n", "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"sk-" + b"x" * 24, "agentgoals-0.2.1/PACKAGE_README.md"),
        (b"safe\n", "agentgoals-0.2.1/tests/test_private.py"),
        (b"safe\n", "agentgoals-0.2.1/README.md"),
    ],
)
def test_verifier_rejects_forbidden_artifact_content(
    tmp_path: Path, wheel_payload: bytes, sdist_member: str
) -> None:
    write_wheel(tmp_path / "agentgoals-0.2.1-py3-none-any.whl", payload=wheel_payload)
    write_sdist(tmp_path / "agentgoals-0.2.1.tar.gz", member_name=sdist_member)

    with pytest.raises(ArtifactVerificationError):
        verify_directory(tmp_path)


def test_verifier_rejects_stale_matching_artifact_versions(tmp_path: Path) -> None:
    write_wheel(
        tmp_path / "agentgoals-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    write_sdist(
        tmp_path / "agentgoals-0.2.0.tar.gz",
        member_name="agentgoals-0.2.0/PACKAGE_README.md",
        version="0.2.0",
    )

    with pytest.raises(ArtifactVerificationError, match="filename must identify"):
        verify_directory(tmp_path)


def test_verifier_allows_urls_and_escaped_regexes(tmp_path: Path) -> None:
    write_wheel(
        tmp_path / "agentgoals-0.2.1-py3-none-any.whl",
        payload=(
            b'REF = "https://json-schema.org/draft/2020-12/schema"\n'
            b'PREFIX = "\\\\?\\\\"\n'
            b'RELATIVE = "./CONTRACT.md"\n'
            + br'POSIX_REGEX = "^\/tmp\/item$"'
            + b"\n"
        ),
    )
    write_sdist(
        tmp_path / "agentgoals-0.2.1.tar.gz",
        member_name="agentgoals-0.2.1/PACKAGE_README.md",
    )

    assert verify_directory(tmp_path)["status"] == "passed"


def test_verifier_rejects_artifact_filenames_that_do_not_bind_project_and_version(tmp_path: Path) -> None:
    write_wheel(tmp_path / "renamed-0.2.1-py3-none-any.whl")
    write_sdist(
        tmp_path / "renamed-0.2.1.tar.gz",
        member_name="agentgoals-0.2.1/PACKAGE_README.md",
    )

    with pytest.raises(ArtifactVerificationError, match="filename must identify"):
        verify_directory(tmp_path)
