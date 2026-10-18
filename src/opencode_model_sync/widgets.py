"""Small widgets and helpers shared by the windows and dialogs."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from . import icons, theme


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


class ElidedLabel(QLabel):
    """A label that shortens its text with an ellipsis instead of widening its parent."""

    def __init__(self, text: str, name: str | None = None, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight) -> None:
        super().__init__()
        self.full = text
        self.mode = mode
        if name:
            self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(30)
        self.setToolTip(text)
        self.setText(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.full, self.mode, self.width()))


def pill(text: str, tone: str) -> QLabel:
    widget = label(text, "pill")
    widget.setProperty("tone", tone)
    widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return widget


def button(text: str, name: str | None = None, icon_name: str | None = None, color: str | None = None) -> QPushButton:
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    if icon_name:
        palette = theme.current()
        tint = color or (palette.accent_text if name == "primary" else palette.muted)
        widget.setIcon(icons.icon(icon_name, tint))
        widget.setIconSize(QSize(16, 16))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def tokens(count: int) -> str:
    return f"{count // 1024}K" if count >= 1024 and count % 1024 == 0 else f"{round(count / 1000)}K"
