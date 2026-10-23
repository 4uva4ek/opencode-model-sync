"""Colors and the Qt style sheet, in a dark and a light variant that follow the system scheme."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Palette:
    window: str
    sidebar: str
    surface: str
    surface_hover: str
    border: str
    text: str
    muted: str
    faint: str
    accent: str
    accent_hover: str
    accent_text: str
    accent_soft: str
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str


DARK = Palette(
    window="#111318",
    sidebar="#0c0e12",
    surface="#181b22",
    surface_hover="#1f232c",
    border="#262a34",
    text="#e8eaf0",
    muted="#9aa1b1",
    faint="#636a7a",
    accent="#7c6cf2",
    accent_hover="#8e80f5",
    accent_text="#ffffff",
    accent_soft="rgba(124, 108, 242, 15%)",
    success="#3ecf8e",
    success_soft="rgba(62, 207, 142, 13%)",
    warning="#f2b84b",
    warning_soft="rgba(242, 184, 75, 13%)",
    danger="#f2665f",
    danger_soft="rgba(242, 102, 95, 13%)",
)

LIGHT = Palette(
    window="#f6f7fb",
    sidebar="#eceef5",
    surface="#ffffff",
    surface_hover="#f1f2f8",
    border="#dfe2ec",
    text="#171a21",
    muted="#5d6475",
    faint="#8f96a6",
    accent="#5b4ce0",
    accent_hover="#4c3dd1",
    accent_text="#ffffff",
    accent_soft="rgba(91, 76, 224, 12%)",
    success="#169c62",
    success_soft="rgba(22, 156, 98, 11%)",
    warning="#b7791f",
    warning_soft="rgba(183, 121, 31, 12%)",
    danger="#d23c35",
    danger_soft="rgba(210, 60, 53, 10%)",
)


def current() -> Palette:
    hints = QGuiApplication.styleHints()
    return LIGHT if hints.colorScheme() == Qt.ColorScheme.Light else DARK


def style_sheet(p: Palette, check: str) -> str:
    return f"""
* {{
    font-size: 13px;
    color: {p.text};
}}
QMainWindow, #content {{ background: {p.window}; }}
#sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.border}; }}
QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; padding: 6px 8px; border-radius: 6px; }}

#brand {{ font-size: 16px; font-weight: 700; }}
#brandSub {{ color: {p.faint}; font-size: 12px; }}
#sectionLabel {{ color: {p.faint}; font-size: 11px; font-weight: 600; letter-spacing: 0.6px; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: none; padding: 0; margin: 0; }}
QListWidget::item:selected {{ background: transparent; }}

#providerCard {{ background: transparent; border-radius: 10px; }}
#providerCard[hover="true"] {{ background: {p.surface_hover}; }}
#providerCard[selected="true"] {{ background: {p.surface}; border: 1px solid {p.border}; }}
#providerName {{ font-weight: 600; }}
#providerUrl {{ color: {p.faint}; font-size: 11px; }}
#countBadge {{ color: {p.muted}; background: {p.surface_hover}; border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600; }}

#title {{ font-size: 22px; font-weight: 700; }}
#subtitle {{ color: {p.muted}; }}
#mono {{ font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Consolas", monospace; color: {p.muted}; font-size: 12px; }}
#configPath {{ color: {p.faint}; font-size: 12px; }}

QPushButton {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {p.surface_hover}; }}
QPushButton:disabled {{ color: {p.faint}; }}
QPushButton#primary {{ background: {p.accent}; border-color: {p.accent}; color: {p.accent_text}; }}
QPushButton#primary:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton#primary:disabled {{ background: {p.accent_soft}; border-color: transparent; color: {p.faint}; }}
QPushButton#danger {{ color: {p.danger}; }}
QPushButton#danger:hover {{ background: {p.danger_soft}; }}
QPushButton#ghost {{ background: transparent; border: none; color: {p.muted}; padding: 6px 8px; }}
QPushButton#ghost:hover {{ color: {p.text}; background: {p.surface_hover}; }}
QPushButton#link {{ background: transparent; border: none; color: {p.accent}; padding: 0; font-weight: 500; }}
QPushButton#link:hover {{ color: {p.accent_hover}; text-decoration: underline; }}

#modelList {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
#modelRow {{ border-bottom: 1px solid {p.border}; }}
#modelRow[last="true"] {{ border-bottom: none; }}
#modelName {{ font-weight: 600; }}

QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {p.faint}; background: transparent; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; image: url({check}); }}
QCheckBox::indicator:disabled {{ border-color: {p.border}; }}

#pill {{ border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 600; }}
QPushButton#pill {{ border: 1px solid transparent; }}
QPushButton#pill:hover {{ border-color: {p.faint}; }}
#pill[tone="accent"] {{ color: {p.accent}; background: {p.accent_soft}; }}
#pill[tone="success"] {{ color: {p.success}; background: {p.success_soft}; }}
#pill[tone="warning"] {{ color: {p.warning}; background: {p.warning_soft}; }}
#pill[tone="danger"] {{ color: {p.danger}; background: {p.danger_soft}; }}
#pill[tone="muted"] {{ color: {p.muted}; background: {p.surface_hover}; }}

#banner {{ border-radius: 10px; padding: 10px 14px; }}
#banner[tone="success"] {{ background: {p.success_soft}; color: {p.success}; }}
#banner[tone="danger"] {{ background: {p.danger_soft}; color: {p.danger}; }}
#banner[tone="accent"] {{ background: {p.accent_soft}; color: {p.accent}; }}
#banner[tone="success"] QLabel {{ color: {p.success}; background: transparent; }}
#banner[tone="danger"] QLabel {{ color: {p.danger}; background: transparent; }}
#banner[tone="accent"] QLabel {{ color: {p.accent}; background: transparent; }}

#suggestion {{ background: {p.accent_soft}; border-radius: 10px; }}
#suggestionText {{ color: {p.text}; font-size: 12px; }}

#empty {{ color: {p.faint}; font-size: 14px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.faint}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QDialog {{ background: {p.window}; }}
QLineEdit {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {p.accent};
}}
QLineEdit:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled {{ color: {p.faint}; }}
QPlainTextEdit {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {p.accent};
}}
QPlainTextEdit:focus {{ border-color: {p.accent}; }}
QComboBox {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 7px 10px;
}}
QComboBox:hover {{ background: {p.surface_hover}; }}
QComboBox:disabled {{ color: {p.faint}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p.surface};
    border: 1px solid {p.border};
    selection-background-color: {p.surface_hover};
    selection-color: {p.text};
    outline: none;
}}
#workerRow {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px; }}
QListWidget#pickerList {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px; padding: 4px; }}
QListWidget#pickerList::item {{ padding: 7px 10px; border-radius: 6px; }}
QListWidget#pickerList::item:hover {{ background: {p.surface_hover}; }}
QListWidget#pickerList::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
#fieldLabel {{ color: {p.muted}; font-size: 12px; font-weight: 600; }}
#hint {{ color: {p.faint}; font-size: 12px; }}
#error {{ color: {p.danger}; font-size: 12px; }}

QMenu {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.surface_hover}; }}
"""
