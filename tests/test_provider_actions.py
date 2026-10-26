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
    # The content layout is: the top bar, the provider header, the model list, the footer.
    header = widget.content_layout.itemAt(1).layout()
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


def rows_of(widget):
    return {row.row.id: row for row in widget.findChildren(window.ModelRowWidget)}


@pytest.mark.parametrize("language", ["en", "ru"])
def test_two_switches_keep_labels_and_change_only_their_own_state(view, language):
    widget, path = view
    previous = i18n.language()
    i18n.set_language(language)
    try:
        path.write_text(json.dumps({"providers": {"local": {
            "settings": {"baseURL": "http://localhost:1234/v1"},
            "models": {"m": {"capabilities": {"tools": True}}}}}}))
        widget._reload_config()
        labels = [i18n.tr(key) for key in ("row.display", "row.tools")]
        for name in ("model_switch", "tools_switch"):
            getattr(rows_of(widget)["m"], name).click()
        row = rows_of(widget)["m"]
        switches = [row.model_switch, row.tools_switch]
        assert [control.text() for control in switches] == labels
        assert all(control.isCheckable() and not control.isChecked() for control in switches)
        saved = json.loads(path.read_text())["providers"]["local"]["models"]["m"]
        assert saved == {"disabled": True, "capabilities": {"tools": False}}
        for name in ("model_switch", "tools_switch"):
            getattr(rows_of(widget)["m"], name).click()
        row = rows_of(widget)["m"]
        assert [control.text() for control in (row.model_switch, row.tools_switch)] == labels
        assert all(control.isChecked() for control in (row.model_switch, row.tools_switch))
        widget.busy = True
        widget.render()
        row = rows_of(widget)["m"]
        assert all(not control.isEnabled() for control in (row.model_switch, row.tools_switch))
    finally:
        i18n.set_language(previous)


def test_the_switch_in_a_row_preserves_the_provider_format(view):
    """The point of the button: one click instead of opening the settings of opencode."""
    widget, path = view
    path.write_text(
        json.dumps({"provider": {"local": {
            "name": "Local",
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": "http://localhost:1234/v1"},
            # The old map is switched off by its own word, and a stray ``disabled`` of it is nothing.
            "models": {"on": {"tool_call": True}, "off": {"status": "deprecated"}},
        }}})
    )
    widget._reload_config()
    widget.render()

    rows = rows_of(widget)
    assert rows["on"].model_switch.isChecked()
    assert not rows["off"].model_switch.isChecked()

    rows["on"].model_switch.click()  # off: keep the provider format
    rows_of(widget)["off"].model_switch.click()  # on: only the mark leaves the entry
    saved = json.loads(path.read_text())
    assert list(saved["provider"]["local"]["models"]) == ["on", "off"]
    assert saved["provider"]["local"]["models"]["on"] == {"tool_call": True, "status": "deprecated"}
    assert saved["provider"]["local"]["models"]["off"] == {}
    assert "providers" not in saved

    widget.render()
    rows = rows_of(widget)
    assert not rows["on"].model_switch.isChecked()
    assert rows["off"].model_switch.isChecked()


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
