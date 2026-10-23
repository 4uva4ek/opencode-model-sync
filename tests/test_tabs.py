"""The tab strip: a tab that opens into its page, a highlight that glides, a page that fades in."""
import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from opencode_model_sync import app as application, theme, window


@pytest.fixture
def view(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    application.apply_theme(app)
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps({"provider": {"local": {
        "name": "Local", "options": {"baseURL": "http://localhost:1234/v1"}, "models": {}
    }}}))
    monkeypatch.setattr(window, "config_path", lambda: path)
    monkeypatch.setattr(window.MainWindow, "refresh", window.MainWindow._reload_config)
    # Listing workspaces asks a running opencode; here it only records that the tab asked.
    opened = []
    monkeypatch.setattr(window.MainWindow, "refresh_workspaces", lambda self: opened.append(self.tab))

    def run(work, done, failed):
        try:
            result = work()
        except Exception as error:
            failed(str(error))
        else:
            done(result)

    monkeypatch.setattr(window.tasks, "run", run)
    widget = window.MainWindow()
    widget.resize(1000, 600)
    widget.show()
    spin(app)
    yield widget, app, opened
    widget.close()
    widget.deleteLater()
    app.processEvents()


def spin(app, seconds=0.05):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def strip_of(widget):
    return widget.tabs.parentWidget()


def test_the_tabs_sit_over_the_page_they_open(view):
    widget, _, _ = view
    strip = strip_of(widget)
    assert strip.geometry().bottom() + 1 == widget.stack.geometry().top()


def test_the_chosen_tab_reaches_down_into_its_page(view):
    widget, app, _ = view
    bar = widget.tabs
    opening = bar.opening()
    # The tab stands on the bottom edge of the strip rather than stopping short of it.
    assert opening.bottom() == pytest.approx(bar.height())
    seam = bar.mapTo(widget, QPoint(int(opening.center().x()), int(opening.bottom())))
    assert seam.y() == widget.stack.geometry().top()


def test_the_tab_is_cut_from_the_same_sheet_as_its_page(view):
    widget, app, _ = view
    strip = strip_of(widget)
    bar = widget.tabs
    opening = bar.opening()
    image = widget.grab().toImage()
    inside = bar.mapTo(widget, QPoint(int(opening.center().x()), bar.height() - 3))
    page = widget.stack.mapTo(widget, QPoint(widget.width() // 2, 3))
    assert image.pixelColor(inside).name() == theme.current().window
    assert image.pixelColor(inside).name() == image.pixelColor(page).name()
    # Away from the tab the strip is still the darker chrome.
    aside = strip.mapTo(widget, QPoint(bar.geometry().right() - 4, strip.height() - 3))
    assert image.pixelColor(aside).name() == theme.current().sidebar


def test_the_strip_line_stops_where_the_tab_opens(view):
    widget, app, _ = view
    strip = strip_of(widget)
    bar = widget.tabs
    opening = bar.opening()
    image = widget.grab().toImage()
    row = strip.height() - 1  # the strip draws its dividing line along its own bottom edge
    under_tab = strip.mapTo(widget, QPoint(int(bar.geometry().left() + opening.center().x()), row))
    beside_tab = strip.mapTo(widget, QPoint(bar.geometry().right() - 4, row))
    assert image.pixelColor(beside_tab).name() == theme.current().border
    assert image.pixelColor(under_tab).name() == theme.current().window


def test_moving_to_the_other_tab_shows_workspaces_and_frees_the_width(view):
    widget, app, opened = view
    widget.tabs.setCurrentIndex(1)
    spin(app)
    assert widget.stack.currentIndex() == 1
    assert widget.tab == "workspaces"
    assert not widget.sidebar.isVisibleTo(widget)
    assert opened == ["workspaces"]
    widget.tabs.setCurrentIndex(1)
    spin(app)
    assert opened == ["workspaces"], "the list is asked for once, not on every click"
    widget.tabs.setCurrentIndex(0)
    spin(app)
    assert widget.sidebar.isVisibleTo(widget)
    assert widget.stack.currentIndex() == 0


def test_the_highlight_glides_across_instead_of_jumping(view):
    widget, app, _ = view
    bar = widget.tabs
    seen = []
    bar.slide.valueChanged.connect(lambda value: seen.append(value))
    bar.setCurrentIndex(1)
    assert bar.slide.endValue() == 1.0
    spin(app, 3.0)
    assert bar._offset == pytest.approx(1.0)
    assert any(0.05 < value < 0.95 for value in seen), "the highlight should pass between the tabs"


def test_the_opening_lands_on_the_tab_the_highlight_reached(view):
    widget, app, _ = view
    bar = widget.tabs
    bar._set_offset(0.5)
    half = bar.opening()
    assert half.left() == pytest.approx((bar.tabRect(0).left() + bar.tabRect(1).left()) / 2 + 3)
    assert half.width() == pytest.approx((bar.tabRect(0).width() + bar.tabRect(1).width()) / 2 - 6)


def test_the_tab_is_rounded_at_the_top_rather_than_cut_diagonally():
    # The corner arcs sweep against Qt's downward axis; the wrong way round and the tab comes out a wedge.
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from opencode_model_sync.tabs import TabBar

    image = QImage(64, 24, QImage.Format.Format_RGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawPath(TabBar._shape(QRectF(2, 2, 60, 20)))
    painter.end()

    assert image.pixelColor(32, 3).name() == "#ffffff", "the top runs flat between the corners"
    assert image.pixelColor(2, 2).name() == "#000000", "the top corners are rounded off"
    assert image.pixelColor(61, 2).name() == "#000000"
    assert image.pixelColor(3, 21).name() == "#ffffff", "the bottom stands full width"
    assert image.pixelColor(60, 21).name() == "#ffffff"


def test_a_page_fades_in_and_leaves_no_effect_behind(view):
    from opencode_model_sync.tabs import fade_in

    widget, app, _ = view
    page = widget.stack.widget(0)
    fade_in(page)
    assert page.graphicsEffect() is not None
    spin(app, 3.0)
    assert page.graphicsEffect() is None
