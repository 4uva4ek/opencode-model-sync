"""The workspaces page: every folder opencode works in, with the two ways to get rid of one."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme, workspaces
from .i18n import tr
from .widgets import ElidedLabel, button, label, pill, scrolled


class WorkspaceRow(QFrame):
    exclude = Signal(object)
    restore = Signal(object)
    remove = Signal(object)
    unarchive = Signal(object)
    open = Signal(object)

    def __init__(self, item: workspaces.Workspace, excluded: bool, busy: bool, last: bool) -> None:
        super().__init__()
        self.item = item
        self.setObjectName("modelRow")
        self.setProperty("last", last)
        palette = theme.current()

        glyph = QLabel()
        glyph.setPixmap(icons.icon("folder", palette.danger if not item.exists else palette.muted).pixmap(16, 16))
        glyph.setToolTip(tr("ws.missing") if not item.exists else item.directory)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(ElidedLabel(item.name, "providerName"))
        details = ElidedLabel(item.directory, "mono", Qt.TextElideMode.ElideMiddle)
        text.addWidget(details)
        if item.kind == workspaces.WORKTREE and item.project_dir:
            text.addWidget(ElidedLabel(tr("ws.of", folder=item.project_dir), "configPath"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 11, 12, 11)
        layout.setSpacing(10)
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)

        if item.kind == workspaces.WORKTREE:
            layout.addWidget(pill(tr("ws.worktree"), "accent"))
        if item.is_git:
            layout.addWidget(pill("git", "muted"))
        if not item.exists:
            warning = pill(tr("ws.missing"), "danger")
            warning.setToolTip(tr("ws.missingHint"))
            layout.addWidget(warning)
        if item.archived:
            layout.addWidget(pill(tr("ws.archived"), "muted"))
        if item.sessions:
            count = pill(tr("ws.sessions", count=item.sessions), "muted")
            count.setToolTip(tr("ws.sessionsHint"))
            layout.addWidget(count)
        if item.last_used:
            layout.addWidget(pill(item.last_used, "muted"))
        if excluded:
            layout.addWidget(pill(tr("ws.excluded"), "warning"))

        if excluded:
            back = button(tr("ws.restore"), "ghost")
            back.setToolTip(tr("ws.restoreHint"))
            back.setEnabled(not busy)
            back.clicked.connect(lambda: self.restore.emit(item))
            layout.addWidget(back)
        else:
            away = button(tr("ws.exclude"), "ghost")
            away.setToolTip(tr("ws.excludeHint"))
            away.setEnabled(not busy)
            away.clicked.connect(lambda: self.exclude.emit(item))
            layout.addWidget(away)

        if item.archived:
            # opencode already took it off its own list: the way out of an archive is to leave it.
            out = button(tr("ws.unarchive"), "ghost")
            out.setToolTip(tr("ws.unarchiveHint") if item.can_remove else tr("error.workspaceSchema"))
            out.setEnabled(not busy and item.can_remove)
            out.clicked.connect(lambda: self.unarchive.emit(item))
            layout.addWidget(out)
        else:
            drop = button(tr("ws.remove"), "ghost", "trash", palette.danger)
            drop.setToolTip(tr("ws.removeHint") if item.can_remove else tr("error.workspaceSchema"))
            drop.setEnabled(not busy and item.can_remove)
            drop.clicked.connect(lambda: self.remove.emit(item))
            layout.addWidget(drop)

        manage = button("⋯", "ghost")
        manage.setAccessibleName(tr("ws.actions"))
        manage.setToolTip(tr("ws.actions"))
        menu = QMenu(manage)
        open_action = menu.addAction(tr("ws.open"))
        open_action.setEnabled(item.exists)
        open_action.triggered.connect(lambda: self.open.emit(item))
        manage.setMenu(menu)
        layout.addWidget(manage, 0, Qt.AlignmentFlag.AlignVCenter)


class WorkspacesPanel(QWidget):
    refresh = Signal()
    add = Signal()
    exclude = Signal(object)
    restore = Signal(object)
    remove = Signal(object)
    unarchive = Signal(object)
    open = Signal(object)
    show_excluded_toggled = Signal(bool)
    show_archived_toggled = Signal(bool)

    def __init__(
        self,
        items: list[workspaces.Workspace] | None,
        note: str,
        excluded: set[str],
        show_excluded: bool,
        show_archived: bool,
        busy: bool,
    ) -> None:
        super().__init__()
        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(label(tr("ws.title"), "title"))
        heading.addWidget(label(tr("ws.subtitle"), "subtitle", wrap=True))

        refresh = button(tr("ws.refresh"), icon_name="refresh")
        refresh.setToolTip(tr("ws.refreshHint"))
        refresh.setEnabled(not busy)
        refresh.clicked.connect(self.refresh.emit)
        add = button(tr("ws.add"), "primary", "folder")
        add.setToolTip(tr("ws.addHint"))
        add.setEnabled(not busy)
        add.clicked.connect(self.add.emit)
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addLayout(heading, 1)
        header.addWidget(refresh, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(add, 0, Qt.AlignmentFlag.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(label(note, "hint", wrap=True))

        if items is None:
            layout.addWidget(_centered(tr("ws.loading"), "empty"), 1)
            return

        # A row is kept off this page one of two ways: hidden here, or archived in opencode.
        kept = [item for item in items if show_excluded or item.key not in excluded]
        listed = [item for item in kept if show_archived or not item.archived]
        hidden = len([item for item in items if item.key in excluded])
        in_archive = len([item for item in items if item.archived])
        if not listed:
            layout.addWidget(_centered(tr("ws.empty"), "empty"), 1)
        else:
            container = QFrame()
            container.setObjectName("modelList")
            column = QVBoxLayout(container)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(0)
            for index, item in enumerate(listed):
                row = WorkspaceRow(item, item.key in excluded, busy, index == len(listed) - 1)
                row.exclude.connect(self.exclude.emit)
                row.restore.connect(self.restore.emit)
                row.remove.connect(self.remove.emit)
                row.unarchive.connect(self.unarchive.emit)
                row.open.connect(self.open.emit)
                column.addWidget(row)
            column.addStretch(1)
            layout.addWidget(scrolled(container), 1)

        gone = len([item for item in listed if not item.exists])
        summary = label(
            tr("ws.summary", total=len(listed), worktrees=len([item for item in listed if item.kind == workspaces.WORKTREE]), gone=gone),
            "subtitle",
        )
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(summary, 1)
        footer.addWidget(_toggle("ws.showExcluded", hidden, show_excluded, busy, self.show_excluded_toggled))
        footer.addWidget(_toggle("ws.showArchived", in_archive, show_archived, busy, self.show_archived_toggled))
        layout.addLayout(footer)


def _toggle(key: str, count: int, checked: bool, busy: bool, signal) -> QCheckBox:
    widget = QCheckBox(tr(key, count=count))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setToolTip(tr(key + "Hint"))
    widget.setChecked(checked)
    widget.setEnabled(not busy)
    widget.toggled.connect(signal.emit)
    return widget


def _centered(text: str, name: str) -> QWidget:
    widget = label(text, name, wrap=True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget
