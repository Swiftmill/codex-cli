from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from git import Repo


def clone_repository(source: str, destination: Optional[str] = None) -> Path:
    """Clone a repository locally."""

    dest_path = Path(destination or tempfile.mkdtemp(prefix="codex_repo_"))
    Repo.clone_from(source, dest_path)
    return dest_path


def extract_zip(archive: str, destination: Optional[str] = None) -> Path:
    """Extract a repository archive."""

    dest_path = Path(destination or tempfile.mkdtemp(prefix="codex_zip_"))
    dest_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest_path)
    entries = [p for p in dest_path.iterdir() if p.is_dir()]
    if len(entries) == 1:
        return entries[0]
    return dest_path


def prepare_repository(source: Optional[str]) -> Path:
    """Return a local path for the repository based on the source specification."""

    if not source:
        return Path.cwd()
    path = Path(source)
    if path.exists():
        if path.suffix == ".zip":
            return extract_zip(str(path))
        return path.resolve()
    if source.endswith(".zip"):
        return extract_zip(source)
    return clone_repository(source)


def copy_repository(source: Path, destination: Path) -> None:
    """Copy a repository to a new destination."""

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
