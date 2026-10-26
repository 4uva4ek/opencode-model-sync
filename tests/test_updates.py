import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import tomllib
import zipfile

import pytest

from opencode_model_sync import updates


def metadata(version="v0.4.3", name="opencode-companion-linux-x64.tar.gz", digest=None):
    return {"tag_name": version, "assets": [{"name": name, "digest": digest}, {"name": name + ".sha256"}]}


def test_embedded_version_matches_package_and_lock():
    root = Path(__file__).parents[1]
    assert updates.VERSION == tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    packages = tomllib.loads((root / "uv.lock").read_text())["package"]
    assert next(p for p in packages if p["name"] == "opencode-companion")["version"] == updates.VERSION


@pytest.mark.parametrize("system,machine,expected", [
    ("darwin", "arm64", "macos-arm64.zip"),
    ("win32", "AMD64", "windows-x64.zip"),
    ("linux", "x86_64", "linux-x64.tar.gz"),
])
def test_selects_native_release(system, machine, expected):
    assert updates.asset_name(system, machine) == "opencode-companion-" + expected


def test_compares_versions_numerically_and_ignores_previews():
    name = updates.asset_name("linux", "x86_64")
    assert updates.parse_release(metadata("v0.4.10"), "0.4.9", name).version == "0.4.10"
    assert updates.parse_release(metadata("v0.4.2"), "0.4.2", name) is None
    assert updates.parse_release(metadata("v0.4.1"), "0.4.2", name) is None
    assert updates.parse_release({**metadata(), "prerelease": True}, asset=name) is None
    assert updates.parse_release({**metadata(), "draft": True}, asset=name) is None
    with pytest.raises(ValueError):
        updates.version_tuple("v0.4.3/../../other")


def test_missing_build_and_missing_checksum_are_not_installable():
    with pytest.raises(ValueError, match="no build"):
        updates.parse_release(metadata(), asset="missing.zip")
    data = metadata()
    data["assets"].pop()
    with pytest.raises(ValueError, match="no SHA-256"):
        updates.parse_release(data, asset=data["assets"][0]["name"])


def test_download_uses_official_url_and_verifies_digest(tmp_path, monkeypatch):
    content = b"verified package"
    digest = hashlib.sha256(content).hexdigest()
    data = metadata(digest="sha256:" + digest)
    data["assets"][0]["browser_download_url"] = "https://untrusted.invalid/app"
    release = updates.parse_release(data, asset=data["assets"][0]["name"])
    seen = []
    def request(url):
        seen.append(url)
        return io.BytesIO(content)
    monkeypatch.setattr(updates, "request", request)
    output = tmp_path / "archive"
    updates.download(release, output)
    assert output.read_bytes() == content
    assert seen == [updates.RELEASES + "/download/v0.4.3/" + release.asset]
    output.unlink()
    monkeypatch.setattr(updates, "request", lambda url: io.BytesIO(b"corrupted"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        updates.download(release, output)
    assert not output.exists()


def test_download_verifies_published_checksum_file(tmp_path, monkeypatch):
    content = b"package"
    data = metadata()
    release = updates.parse_release(data, asset=data["assets"][0]["name"])
    def request(url):
        return io.BytesIO((hashlib.sha256(content).hexdigest() + "  app\n").encode() if url.endswith(".sha256") else content)
    monkeypatch.setattr(updates, "request", request)
    updates.download(release, tmp_path / "archive")
    assert (tmp_path / "archive").read_bytes() == content


@pytest.mark.parametrize("name", ["../escape", "/escape", "C:/escape", "..\\escape"])
def test_zip_rejects_escaping_paths(tmp_path, name):
    archive = tmp_path / "app.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(name, "bad")
    with pytest.raises(ValueError, match="Unsafe"):
        updates.extract(archive, tmp_path / "unpacked", "win32")


def test_extracts_windows_layout(tmp_path):
    archive = tmp_path / "app.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("OpenCode Companion/OpenCode Companion.exe", b"exe")
    root = updates.extract(archive, tmp_path / "unpacked", "win32")
    assert (root / "OpenCode Companion.exe").read_bytes() == b"exe"


def test_tar_rejects_escape_and_extracts_linux_layout(tmp_path):
    archive = tmp_path / "app.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("../escape")
        member.size = 3
        bundle.addfile(member, io.BytesIO(b"bad"))
    with pytest.raises(tarfile.TarError):
        updates.extract(archive, tmp_path / "unsafe", "linux")
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("opencode-companion/OpenCode Companion")
        member.mode = 0o755
        member.size = 3
        bundle.addfile(member, io.BytesIO(b"exe"))
    root = updates.extract(archive, tmp_path / "valid", "linux")
    assert (root / "OpenCode Companion").read_bytes() == b"exe"


def test_source_checkout_cannot_be_replaced(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    with pytest.raises(ValueError, match="packaged app"):
        updates.installation_root()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX installer")
@pytest.mark.parametrize("fail", [False, True])
def test_installer_replaces_whole_directory_and_rolls_back(tmp_path, fail):
    # Quotes and spaces must never become shell commands.
    directory = tmp_path / "update ' directory"
    directory.mkdir()
    target = tmp_path / "installed ' app"
    target.mkdir()
    (target / "old-library").write_text("old")
    staged = directory / "new app"
    marker = tmp_path / "launched"
    if not fail:
        staged.mkdir()
        executable = staged / "OpenCode Companion"
        import shlex
        executable.write_text("#!/bin/sh\nprintf ok > " + shlex.quote(str(marker)) + "\n")
        executable.chmod(0o755)
    plan = updates.Prepared(directory, staged, target, directory / "previous")
    dead = subprocess.Popen(["/bin/true"])
    dead.wait()
    script = directory / "install.sh"
    script.write_text(updates.installer_script(plan, dead.pid, "linux"))
    result = subprocess.run(["/bin/sh", str(script)], timeout=10)
    if fail:
        assert result.returncode != 0
        assert (target / "old-library").read_text() == "old"
    else:
        assert result.returncode == 0
        assert not (target / "old-library").exists()
        assert (plan.backup / "old-library").read_text() == "old"
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(.01)
        assert marker.read_text() == "ok"


def test_dialog_reports_check_result_and_errors(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from opencode_model_sync.updates_view import UpdateDialog
    from opencode_model_sync import tasks
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(tasks, "run", lambda fn, done, failed: done(None))
    dialog = UpdateDialog(None)
    dialog.check()
    assert not dialog.busy
    assert not dialog.install_button.isEnabled()
    release = updates.parse_release(metadata(), asset=updates.asset_name("linux", "x86_64"))
    dialog.checked(release)
    assert dialog.install_button.isEnabled()
    dialog.failed("network unavailable")
    assert "network unavailable" in dialog.status.text()
    dialog.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Native PowerShell installer")
def test_windows_installer_rolls_back_on_failed_replacement(tmp_path):
    target = tmp_path / "installed ' app"
    target.mkdir()
    (target / "old-library").write_text("old")
    directory = tmp_path / "update"
    directory.mkdir()
    plan = updates.Prepared(directory, directory / "missing", target, directory / "previous")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    script = directory / "install.ps1"
    script.write_text(updates.installer_script(plan, dead.pid, "win32"), encoding="utf-8-sig")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)], timeout=30)
    assert result.returncode != 0
    assert (target / "old-library").read_text() == "old"
    assert (directory / "error.log").is_file()
