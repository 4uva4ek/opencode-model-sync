"""Provider actions exercise the UI and real config writes without network requests."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
from opencode_model_sync import window, i18n


@pytest.fixture
def view(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps({"provider": {"local": {
        "name": "Local", "options": {"baseURL": "http://localhost:1234/v1"}, "models": {}
    }}}))
    monkeypatch.setattr(window, "config_path", lambda: path)
    monkeypatch.setattr(window.MainWindow, "refresh", window.MainWindow._reload_config)
    def run(work, done, failed):
        try:
            result = work()
        except Exception as error:
            failed(str(error))
        else:
            done(result)
    monkeypatch.setattr(window.tasks, "run", run)
    widget = window.MainWindow()
    yield widget, path
    widget.close()
    widget.deleteLater()
    app.processEvents()


def action_menu(widget):
    # Rendering replaces widgets with deleteLater; use the current header layout.
    header = widget.content_layout.itemAt(2).layout()
    return header.itemAt(header.count() - 1).widget().menu()


def test_rename_action_persists_and_keeps_selection(view, monkeypatch):
    widget, path = view
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("Renamed", True))
    action_menu(widget).actions()[0].trigger()
    assert json.loads(path.read_text())["provider"]["local"]["name"] == "Renamed"
    assert widget.selected == "local"
    assert widget.config.provider("local").title == "Renamed"


def test_remove_requires_confirmation_and_updates_selection(view, monkeypatch):
    widget, path = view
    original = path.read_text()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.No)
    action_menu(widget).actions()[1].trigger()
    assert path.read_text() == original
    def confirm(*args):
        assert args[-1] == QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", confirm)
    widget.checked["local"] = {"model"}
    action_menu(widget).actions()[1].trigger()
    assert json.loads(path.read_text())["provider"] == {}
    assert widget.selected is None
    assert "local" not in widget.checked


def test_cancel_and_empty_rename_do_not_write(view, monkeypatch):
    widget, path = view
    original = path.read_text()
    for value in [("Ignored", False), ("  ", True)]:
        monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: value)
        widget.rename_provider("local")
        assert path.read_text() == original
    assert widget.config.provider("local").title == "Local"
    assert not widget.busy


@pytest.mark.parametrize("language", ["en", "ru"])
def test_provider_menu_is_translated_and_disabled_during_save(view, language):
    widget, _ = view
    previous = i18n.language()
    try:
        i18n.set_language(language)
        widget.busy = True
        widget.render()
        menu = action_menu(widget)
        assert [a.text() for a in menu.actions()] == [i18n.tr("provider.rename"), i18n.tr("provider.remove")]
        assert not menu.parentWidget().isEnabled()
    finally:
        i18n.set_language(previous)
