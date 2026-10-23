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

# When the page is too narrow for every tag, these give up their place, the least telling first.
# A folder that is not on the disk holds on to its warning to the last.
TAGS_THAT_YIELD = ("excluded", "archived", "git", "worktree", "missing")


class WorkspaceRow(QFrame):
    exclude = Signal(object)
    restore = Signal(object)
    remove = Signal(object)
    open = Signal(object)

    def __init__(self, item: workspaces.Workspace, excluded: bool, busy: bool, last: bool) -> None:
        super().__init__()
        self.item = item
        self._tags: list[tuple[str, QWidget]] = []
        self._floor = 0  # the width the row needs with every tag out of the way
        self._tag_gap = 0
        self.setObjectName("modelRow")
        self.setProperty("last", last)
        palette = theme.current()

        glyph = QLabel()
        glyph.setPixmap(icons.icon("folder", palette.danger if not item.exists else palette.muted).pixmap(16, 16))
        glyph.setToolTip(tr("ws.missing") if not item.exists else item.directory)

        text = QVBoxLayout()
        text.setSpacing(2)

        # The tags that say what kind of folder this is ride the name's line: when the page runs
        # short of width it is the text here that shortens, not the buttons at the end of the row.
        titled = QHBoxLayout()
        titled.setSpacing(6)
        titled.addWidget(ElidedLabel(item.name, "providerName"), 1)
        text.addLayout(titled)

        # The path gives way first: the counts and the date ride along on its line rather than
        # taking room away from the buttons at the end of the row, and they shorten too.
        where = QHBoxLayout()
        where.setSpacing(8)
        where.addWidget(ElidedLabel(item.directory, "mono", Qt.TextElideMode.ElideMiddle), 1)
        if item.sessions:
            sessions = ElidedLabel(tr("ws.sessions", count=item.sessions), "configPath")
            sessions.setToolTip(tr("ws.sessionsHint"))
            where.addWidget(sessions, 0, Qt.AlignmentFlag.AlignBottom)
        if item.last_used:
            seen = ElidedLabel(item.last_used, "configPath")
            seen.setToolTip(tr("ws.lastUsedHint"))
            where.addWidget(seen, 0, Qt.AlignmentFlag.AlignBottom)
        text.addLayout(where)
        if item.kind == workspaces.WORKTREE and item.project_dir:
            text.addWidget(ElidedLabel(tr("ws.of", folder=item.project_dir), "configPath"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 11, 12, 11)
        layout.setSpacing(10)
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)

        # What kind of folder this is, told by small tags. A tag is shown at its whole width or
        # not at all, so nothing is ever cut mid-word; the folder that is not on the disk is the
        # last one to give up its place.
        if item.kind == workspaces.WORKTREE:
            self._tags.append(("worktree", pill(tr("ws.worktree"), "accent", yields=True)))
        if item.is_git:
            self._tags.append(("git", pill("git", "muted", yields=True)))
        if not item.exists:
            warning = pill(tr("ws.missing"), "danger", yields=True)
            warning.setToolTip(tr("ws.missingHint"))
            self._tags.append(("missing", warning))
        if item.archived:
            self._tags.append(("archived", pill(tr("ws.archived"), "muted", yields=True)))
        if excluded:
            self._tags.append(("excluded", pill(tr("ws.excluded"), "warning", yields=True)))
        for _, widget in self._tags:
            titled.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

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

        drop = button(tr("ws.remove"), "ghost", "trash", palette.danger)
        drop.setToolTip(tr("ws.removeHint"))
        drop.setEnabled(not busy)
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

        # Measured once with every tag hidden, so what a tag may keep is worked out from the
        # width alone and hiding one cannot set the next one off hiding itself.
        for _, widget in self._tags:
            widget.setVisible(False)
        self._floor = layout.totalMinimumSize().width()
        self._tag_gap = titled.spacing()
        self._fit_tags()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_tags()

    def _fit_tags(self) -> None:
        """Keep as many tags as the row has whole widths for, the telling ones holding on."""
        room = self.width() - self._floor
        shown = {name for name, _ in self._tags}
        for name in TAGS_THAT_YIELD:
            if name in shown and self._tags_need(shown) > room:
                shown.discard(name)
        for name, widget in self._tags:
            widget.setVisible(name in shown)

    def _tags_need(self, names: set[str]) -> int:
        widths = [widget.sizeHint().width() for name, widget in self._tags if name in names]
        return sum(widths) + self._tag_gap * max(len(widths) - 1, 0)


class WorkspacesPanel(QWidget):
    refresh = Signal()
    add = Signal()
    exclude = Signal(object)
    restore = Signal(object)
    remove = Signal(object)
    open = Signal(object)
    show_excluded_toggled = Signal(bool)

    def __init__(
        self,
        items: list[workspaces.Workspace] | None,
        note: str,
        excluded: set[str],
        show_excluded: bool,
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

        listed = items if show_excluded else [item for item in items if item.key not in excluded]
        hidden = len(items) - len(listed)
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
                row.open.connect(self.open.emit)
                column.addWidget(row)
            column.addStretch(1)
            layout.addWidget(scrolled(container), 1)

        gone = len([item for item in listed if not item.exists])
        summary = label(
            tr("ws.summary", total=len(listed), worktrees=len([item for item in listed if item.kind == workspaces.WORKTREE]), gone=gone),
            "subtitle",
        )
        toggle = QCheckBox(tr("ws.showExcluded", count=hidden))
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setToolTip(tr("ws.showExcludedHint"))
        toggle.setChecked(show_excluded)
        toggle.setEnabled(not busy)
        toggle.toggled.connect(self.show_excluded_toggled.emit)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(summary, 1)
        footer.addWidget(toggle)
        layout.addLayout(footer)


def _centered(text: str, name: str) -> QWidget:
    widget = label(text, name, wrap=True)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget
