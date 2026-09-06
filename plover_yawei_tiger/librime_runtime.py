"""Pinned, isolated librime runtime for the Yawei Plover extension.

The runtime is downloaded only when the user explicitly enables the Rime
backend.  It is kept outside both the Plover installation and any Weasel/Rime
installation, so its DLL and user database cannot compete with another Rime
process.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional
from urllib.request import Request, urlopen


LIBRIME_VERSION = "1.17.0"
LIBRIME_ASSET = "rime-33e7814-Windows-msvc-x64.7z"
LIBRIME_SHA256 = "7478c7caa4ff6b37de86daba1f7ce4a994a4f5ba24872a820fb2b3a9b01fed15"
LIBRIME_URL = (
    "https://github.com/rime/librime/releases/download/"
    f"{LIBRIME_VERSION}/{LIBRIME_ASSET}"
)


class RimeRuntime:
    def __init__(self, dll_path: Path, root: Path):
        self.dll_path = Path(dll_path)
        self.root = Path(root)


def default_root() -> Path:
    override = os.environ.get("PLOVER_YAWEI_RIME_ROOT")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "Plover" / "yawei-rime"


def _download(url: str, target: Path):
    request = Request(url, headers={"User-Agent": "plover-yawei-tiger"})
    with urlopen(request, timeout=60) as source, target.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_librime(root: Optional[Path] = None) -> RimeRuntime:
    """Return the pinned DLL, downloading and verifying it if necessary."""

    root = Path(root or default_root())
    version_root = root / "runtime" / ("librime-" + LIBRIME_VERSION)
    dll_path = version_root / "rime.dll"
    marker = version_root / ".complete"
    if dll_path.is_file() and marker.is_file():
        return RimeRuntime(dll_path, version_root)

    version_root.parent.mkdir(parents=True, exist_ok=True)
    archive = root / "downloads" / LIBRIME_ASSET
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file() or _sha256(archive) != LIBRIME_SHA256:
        archive.unlink(missing_ok=True)
        _download(LIBRIME_URL, archive)
    if _sha256(archive) != LIBRIME_SHA256:
        raise RuntimeError("librime archive SHA-256 verification failed")

    staging = Path(tempfile.mkdtemp(prefix="librime-", dir=str(version_root.parent)))
    try:
        tar = shutil.which("tar")
        if not tar:
            raise RuntimeError("Windows tar.exe is required to install librime")
        subprocess.run([tar, "-xf", str(archive), "-C", str(staging)], check=True)
        extracted = staging / "dist" / "lib" / "rime.dll"
        if not extracted.is_file():
            raise RuntimeError("librime archive does not contain dist/lib/rime.dll")
        version_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted, dll_path)
        marker.write_text(LIBRIME_SHA256 + "\n", encoding="ascii")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return RimeRuntime(dll_path, version_root)


def ensure_rime_data(root: Optional[Path] = None):
    """Create the isolated shared/user Rime directories and seed project data."""

    package_root = Path(__file__).resolve().parent / "rime_data"
    data_root = Path(root or default_root()) / "data"
    shared = data_root / "shared"
    user = data_root / "user"
    shared.mkdir(parents=True, exist_ok=True)
    user.mkdir(parents=True, exist_ok=True)
    for name in ("yawei_tiger.schema.yaml", "yawei_tiger.dict.yaml"):
        source = package_root / name
        target = shared / name
        if not source.is_file():
            raise RuntimeError("packaged Rime data is missing: %s" % name)
        if not target.is_file() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
    return shared, user
