"""Application entry point: theme, main window and the tray icon."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import icons, theme
from .window import MainWindow

APP_ID = "opencode-model-sync"


class TrayWindow(MainWindow):
    """Closing the window hides it to the tray while a tray icon is available."""

    def __init__(self, tray: QSystemTrayIcon | None) -> None:
        super().__init__()
        self.tray = tray
        self.hinted = False

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.tray or not self.tray.isVisible():
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self.hinted:
            self.hinted = True
            self.tray.showMessage("Model Sync", "Приложение работает в трее.", icons.logo(), 3000)


def apply_theme(app: QApplication) -> None:
    palette = theme.current()
    app.setStyleSheet(theme.style_sheet(palette, icons.check_file(palette.accent_text)))


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("OpenCode Model Sync")
    app.setOrganizationName(APP_ID)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(icons.logo())
    app.setStyle("Fusion")
    apply_theme(app)

    tray = QSystemTrayIcon(icons.logo()) if QSystemTrayIcon.isSystemTrayAvailable() else None
    window = TrayWindow(tray)

    def restyle(_scheme: object) -> None:
        apply_theme(app)
        icons.icon.cache_clear()
        window.render()

    app.styleHints().colorSchemeChanged.connect(restyle)

    if tray:
        def show_window() -> None:
            window.showNormal()
            window.raise_()
            window.activateWindow()

        menu = QMenu()
        open_action = QAction("Открыть", menu)
        open_action.triggered.connect(show_window)
        sync_action = QAction("Синхронизировать всё", menu)
        sync_action.triggered.connect(window.sync_all)
        quit_action = QAction("Выход", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(open_action)
        menu.addAction(sync_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.setToolTip("OpenCode Model Sync")
        tray.activated.connect(
            lambda reason: show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        window.synced.connect(lambda message: tray.showMessage("Model Sync", message, icons.logo(), 4000))
        tray.show()
        app.setQuitOnLastWindowClosed(False)

    window.show()
    return app.exec()
