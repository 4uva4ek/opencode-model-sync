import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from opencode_model_sync.agents_view import ModelList, ModelPicker
from opencode_model_sync.catalog import ModelChoice


@pytest.fixture
def picker():
    app = QApplication.instance() or QApplication([])
    dialog = ModelPicker(None, ModelList(items=[
        ModelChoice("local/z", "Zebra", "Local", free=True, tools=False),
        ModelChoice("cloud/a", "Alpha", "Cloud", free=False, tools=True),
        ModelChoice("local/a", "Alpha", "Local", free=True, tools=True),
        ModelChoice("other/a", "Alpha", "Local", free=False, tools=True),
    ]), "local/a")
    dialog.show()
    app.processEvents()
    yield dialog
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def groups(picker):
    return {item.data(0, Qt.ItemDataRole.UserRole): item for item in
            (picker.listing.topLevelItem(i) for i in range(picker.listing.topLevelItemCount()))}


def test_groups_use_provider_ids_and_preserve_exact_selected_model(picker):
    rows = groups(picker)
    assert list(rows) == ["cloud", "local", "other"]
    assert rows["local"].childCount() == 2
    assert "local" in rows["local"].text(0) and "(2)" in rows["local"].text(0)
    assert rows["local"].isExpanded()
    assert not rows["cloud"].isExpanded()
    assert picker.listing.currentItem().data(0, Qt.ItemDataRole.UserRole) == "local/a"
    picker._accept()
    assert picker.result() == QDialog.DialogCode.Accepted
    assert picker.chosen == "local/a"


def test_header_click_collapses_and_cannot_accept_hidden_model(picker):
    group = groups(picker)["local"]
    point = picker.listing.visualItemRect(group).center()
    QTest.mouseClick(picker.listing.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert not group.isExpanded()
    picker._accept()
    assert picker.result() != QDialog.DialogCode.Accepted
    QTest.mouseClick(picker.listing.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert group.isExpanded()


def test_search_reveals_matches_and_restores_collapsed_groups(picker):
    groups(picker)["local"].setExpanded(False)
    picker.search.setText("alpha")
    assert all(group.isExpanded() and group.childCount() == 1 for group in groups(picker).values())
    picker.search.clear()
    assert not groups(picker)["local"].isExpanded()
    picker.search.setText("cloud alpha")
    assert list(groups(picker)) == ["cloud"]
    picker.search.setText("no such model")
    assert not groups(picker)
    assert not picker.empty.isHidden()


def test_filters_keep_group_counts_and_model_selection(picker):
    picker.free_only.setChecked(True)
    assert list(groups(picker)) == ["local"]
    assert groups(picker)["local"].childCount() == 2
    picker.tools_only.setChecked(True)
    group = groups(picker)["local"]
    assert group.childCount() == 1 and "(1)" in group.text(0)
    picker.listing.setCurrentItem(group.child(0))
    picker._accept()
    assert picker.chosen == "local/a"
