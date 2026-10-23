"""The tab strip: tabs cut from the same sheet as the page under them.

QTabBar keeps the clicking, the keyboard and the screen-reader interface; only the painting is ours,
because a style sheet can neither draw a tab that opens into the page below it nor slide the
highlight from one tab to the other.
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    Property,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QSizePolicy, QTabBar, QWidget

from . import theme

PAD_X = 15
PAD_Y = 8
RADIUS = 10
SLIDE_MS = 190
FADE_MS = 120


class TabBar(QTabBar):
    """Tabs along the bottom edge of the strip; the chosen one is filled with the colour of its page."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("tabs")
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setMovable(False)
        self.setUsesScrollButtons(False)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hover = -1
        self._offset = float(max(self.currentIndex(), 0))
        self.slide = QPropertyAnimation(self, b"offset", self)
        self.slide.setDuration(SLIDE_MS)
        self.slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.currentChanged.connect(self._glide)

    # Where the highlight stands, counted in tabs, so 0.4 is on its way from the first to the second.
    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()
        if isinstance(self.parentWidget(), TabStrip):
            self.parentWidget().update()

    offset = Property(float, _get_offset, _set_offset)

    def tabSizeHint(self, index: int) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self.tabText(index)) + 2 * PAD_X, metrics.height() + 2 * PAD_Y)

    def opening(self) -> QRectF:
        """Where the chosen tab stands, in the coordinates of this bar, standing on its bottom edge."""
        if self.count() == 0:
            return QRectF(0, 0, 0, self.height())
        first = min(max(math.floor(self._offset), 0), self.count() - 1)
        last = min(first + 1, self.count() - 1)
        weight = self._offset - first
        start = QRectF(self.tabRect(first))
        end = QRectF(self.tabRect(last))
        moved = QRectF(
            start.x() + (end.x() - start.x()) * weight,
            start.y(),
            start.width() + (end.width() - start.width()) * weight,
            start.height(),
        )
        moved.setBottom(self.height())
        return moved.adjusted(3, 0, -3, 0)

    def _glide(self, index: int) -> None:
        self.slide.stop()
        self.slide.setStartValue(self._offset)
        self.slide.setEndValue(float(index))
        self.slide.start()

    def paintEvent(self, event) -> None:
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # A tab that is not the one in use still answers the pointer.
        if self._hover >= 0 and abs(self._hover - self._offset) > 0.5:
            resting = QRectF(self.tabRect(self._hover)).adjusted(2, 1, -2, -1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.surface_hover))
            painter.drawRoundedRect(resting, RADIUS, RADIUS)

        opening = self._shape(self.opening())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.window))
        painter.drawPath(opening)
        # The outline stops at the bottom: that is where the tab becomes the page.
        pen = QPen(QColor(palette.border))
        pen.setWidthF(1.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(opening)

        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        for index in range(self.count()):
            chosen = max(0.0, 1.0 - abs(index - self._offset))
            painter.setPen(_mix(palette.muted, palette.text, chosen) if index != self._hover else QColor(palette.text))
            painter.drawText(QRectF(self.tabRect(index)), int(Qt.AlignmentFlag.AlignCenter), self.tabText(index))

    @staticmethod
    def _shape(tab: QRectF) -> QPainterPath:
        """Rounded at the top, open at the bottom: the tab runs on into the page under it.

        The sweep is negative because Qt counts angles against a downward y axis.
        """
        corner = min(float(RADIUS), tab.height() / 2, tab.width() / 2)
        path = QPainterPath()
        path.moveTo(tab.left(), tab.bottom())
        path.lineTo(tab.left(), tab.top() + corner)
        path.arcTo(QRectF(tab.left(), tab.top(), 2 * corner, 2 * corner), 180, -90)
        path.lineTo(tab.right() - corner, tab.top())
        path.arcTo(QRectF(tab.right() - 2 * corner, tab.top(), 2 * corner, 2 * corner), 90, -90)
        path.lineTo(tab.right(), tab.bottom())
        return path

    def hoverMoveEvent(self, event) -> None:
        self.set_hover(self.tabAt(event.position().toPoint()))
        super().hoverMoveEvent(event)

    def set_hover(self, index: int) -> None:
        """Rest the pointer on a tab without a mouse; the painting tests and shots use it."""
        index = index if 0 <= index < self.count() else -1
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event) -> None:
        self.set_hover(-1)
        super().leaveEvent(event)


class TabStrip(QWidget):
    """The bar the tabs sit in, along the whole top of the window.

    The line along its bottom stops where a tab opens into its page. Whatever is given as the brand
    takes the left end, over the sidebar, so the tabs can start where the page starts.
    """

    def __init__(self, tabs: TabBar, brand: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("tabStrip")
        self.tabs = tabs
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 10, 20, 0)
        row.setSpacing(0)
        if brand is not None:
            row.addWidget(brand, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(tabs, 1, Qt.AlignmentFlag.AlignBottom)

    def paintEvent(self, event) -> None:
        palette = theme.current()
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.sidebar))
        painter.drawRect(self.rect())

        # The line along the bottom gives way to the tab, which carries on into the page below it.
        opening = self.tabs.opening()
        left = self.tabs.geometry().left() + opening.left()
        right = self.tabs.geometry().left() + opening.right()
        line = float(self.height() - 1)
        painter.setBrush(QColor(palette.border))
        painter.drawRect(QRectF(0, line, left, 1))
        painter.drawRect(QRectF(right, line, self.width() - right, 1))


def _mix(first: str, second: str, weight: float) -> QColor:
    """A colour between two others, for text that brightens as the tab fills up."""
    a, b = QColor(first), QColor(second)
    return QColor(
        round(a.red() + (b.red() - a.red()) * weight),
        round(a.green() + (b.green() - a.green()) * weight),
        round(a.blue() + (b.blue() - a.blue()) * weight),
    )


def fade_in(page: QWidget) -> None:
    """A page that appears instead of appearing all at once."""
    effect = QGraphicsOpacityEffect(page)
    page.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", page)
    anim.setDuration(FADE_MS)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: page.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    page.fade = anim
