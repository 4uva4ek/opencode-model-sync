"""Frozen-build smoke test; never reads or writes the user's OpenCode configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import traceback


def run(report_path: str) -> int:
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Keep Qt imports inside the try block so DLL errors produce a report
        # instead of an unhandled windowed-PyInstaller error dialog.
        from PySide6.QtCore import qVersion
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtNetwork import QLocalServer
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtWidgets import QApplication
        from . import app as application, i18n, mcp_catalog, settings, window
        from .mcp_catalog_view import CatalogDialog, SetupDialog

        app = QApplication([])
        application.apply_theme(app)
        i18n.set_language("ru")
        with tempfile.TemporaryDirectory(prefix="companion-smoke-", dir=report.parent) as temp:
            os.environ["OPENCODE_CONFIG_DIR"] = temp
            path = Path(temp) / "opencode.json"
            path.write_text('{"mcp":{"servers":{}}}', encoding="utf-8")

            class OfflineWindow(window.MainWindow):
                def refresh(self):
                    self._reload_config()

                def refresh_workspaces(self):
                    pass

            main = OfflineWindow()
            main.tabs.setCurrentIndex(3)
            main.resize(1080, 700)
            browser = CatalogDialog({}, main)
            entry = mcp_catalog.starter()[0]
            setup = SetupDialog(entry, entry.recipes[0], set(), browser)
            setup._accept()
            assert setup.result_config is not None
            main.mcp_page.mcp_servers.data[setup.result_name] = setup.result_config
            main.mcp_page._changed()
            main.mcp_page.save()
            assert not main.mcp_page.dirty
            assert "context7" in json.loads(path.read_text())["mcp"]["servers"]
            assert settings.schema()["properties"]
            assert len(browser.entries) >= 3
            app.processEvents()
            assert not main.grab().isNull()
            assert browser.grab().save(str(report.with_suffix(".png")))
            socket = QLocalServer()
            svg = QSvgRenderer(b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
            assert svg.isValid()
            result = {"status": "ok", "qt": qVersion(), "platform": QGuiApplication.platformName(),
                      "window": main.windowTitle(), "catalog_entries": len(browser.entries),
                      "config_save": "ok"}
            browser.reject()
            main.close()
            del setup, browser, main, socket, svg
            app.processEvents()
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    except Exception:
        report.write_text(json.dumps({"status": "error", "traceback": traceback.format_exc()},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
