"""Build a standalone app for the current OS with PyInstaller.

    uv run python scripts/build.py

Produces dist/OpenCode Model Sync(.app|.exe folder) and an archive next to it named
opencode-model-sync-<os>-<arch>.(zip|tar.gz). Each OS has to build its own app.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "OpenCode Model Sync"
SLUG = "opencode-model-sync"


def render_icon(path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "src"))
    from PySide6.QtGui import QGuiApplication

    from opencode_model_sync.icons import logo

    app = QGuiApplication.instance() or QGuiApplication([])
    logo().pixmap(512, 512).save(str(path))
    del app


def target() -> str:
    system = {"darwin": "macos", "win32": "windows"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)
    return f"{system}-{arch}"


def main() -> None:
    icon = ROOT / "assets" / "icon.png"
    icon.parent.mkdir(exist_ok=True)
    render_icon(icon)

    dist = ROOT / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            NAME,
            "--icon",
            str(icon),
            "--osx-bundle-identifier",
            "dev.opencode-model-sync",
            "--paths",
            str(ROOT / "src"),
            # Only Widgets, Gui, Core and Svg are used; leaving the rest out keeps the bundle small.
            "--exclude-module",
            "PySide6.QtNetwork",
            "--exclude-module",
            "PySide6.QtQml",
            "--exclude-module",
            "PySide6.QtQuick",
            "--exclude-module",
            "PySide6.QtPdf",
            str(ROOT / "src" / "opencode_model_sync" / "__main__.py"),
        ],
        check=True,
        cwd=ROOT,
    )

    archive_base = dist / f"{SLUG}-{target()}"
    if sys.platform == "darwin":
        archive = shutil.make_archive(str(archive_base), "zip", dist, f"{NAME}.app")
    elif sys.platform == "win32":
        archive = shutil.make_archive(str(archive_base), "zip", dist, NAME)
    else:
        archive = f"{archive_base}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(dist / NAME, arcname=SLUG)
    print(f"built {archive}")


if __name__ == "__main__":
    main()
