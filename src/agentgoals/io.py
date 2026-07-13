from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class ConcurrentMutationError(RuntimeError):
    """The guarded target changed after preflight and before publication."""


def guarded_lock_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.agentgoals.lock")


@contextmanager
def guarded_file_lock(path: Path):
    """Serialize guarded replacements through a stable, same-directory lock anchor."""
    lock_path = guarded_lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def atomic_replace_bytes_if_hash(path: Path, data: bytes, expected_sha256: str) -> str:
    """Replace one file atomically only when its current bytes match a guard hash."""
    with guarded_file_lock(path):
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if current != expected_sha256:
            raise ConcurrentMutationError(
                f"Guarded target changed: {path} (expected {expected_sha256}, current {current})"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(data)
                handle.flush()
                temp_path = Path(handle.name)
            temp_path.replace(path)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

        after = hashlib.sha256(path.read_bytes()).hexdigest()
        expected_after = hashlib.sha256(data).hexdigest()
        if after != expected_after:
            raise OSError(f"Atomic replacement readback mismatch: {path}")
        return after


def atomic_replace_if_hash(path: Path, text: str, expected_sha256: str) -> str:
    """UTF-8 text convenience wrapper for :func:`atomic_replace_bytes_if_hash`."""
    return atomic_replace_bytes_if_hash(path, text.encode("utf-8"), expected_sha256)
