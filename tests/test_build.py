"""Exercise macOS release packaging with real directory and file symlinks."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("build_app", Path(__file__).parents[1] / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires macOS ditto and codesign")
def test_macos_archive_preserves_bundle_links(tmp_path):
    app = tmp_path / "Example.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Frameworks/python3__dot__12/lib-dynload").mkdir(parents=True)
    (contents / "Frameworks/python3.12").symlink_to("python3__dot__12")
    (contents / "Resources").mkdir()
    (contents / "Resources/module").symlink_to("../Frameworks/python3.12/lib-dynload/module")
    (contents / "Info.plist").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>example</string>
<key>CFBundleIdentifier</key><string>dev.test.model-sync</string>
<key>CFBundlePackageType</key><string>APPL</string>
</dict></plist>""")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }")
    subprocess.run(["cc", str(source), "-o", str(contents / "MacOS/example")], check=True)
    subprocess.run(["cc", "-dynamiclib", str(source), "-o", str(contents / "Frameworks/python3__dot__12/lib-dynload/module")], check=True)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    archive = tmp_path / "example.zip"
    build.archive_macos(app, archive)
    assert archive.is_file()
