"""Keep one Qt application alive until every test's widgets have been destroyed."""
import os
import gc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmapCache


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    application = QApplication.instance() or QApplication([])
    yield application
    # Dialogs and signal closures can outlive function fixtures through Python cycles.
    # Release them, and graphics caches, while QApplication is still valid.
    from opencode_model_sync import icons
    gc.collect()
    for widget in application.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    icons.icon.cache_clear()
    icons.logo.cache_clear()
    QPixmapCache.clear()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not application.topLevelWidgets()
    application.shutdown()


@pytest.fixture(autouse=True)
def finish_qt_deferred_deletions(qt_application):
    yield
    # processEvents alone does not deliver DeferredDelete events without an event loop.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_application.processEvents()
