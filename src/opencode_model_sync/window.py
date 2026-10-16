"""The main window: providers on the left, the selected provider's models on the right."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from PySide6.QtCore import QFileSystemWatcher, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QEnterEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import discovery, i18n, icons, tasks, theme
from .config import ConfigError, OpencodeConfig, Provider, config_path
from .discovery import Discovery, ModelRow, RemoteModel, Suggestion
from .i18n import tr


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


def host(url: str | None) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc or (url or "")


class ProviderCard(QFrame):
    """One provider in the sidebar, with a status dot and a model count."""

    clicked = Signal(str)

    def __init__(self, provider: Provider, result: Discovery | None) -> None:
        super().__init__()
        self.provider_id = provider.id
        self.setObjectName("providerCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        palette = theme.current()
        color = palette.faint if result is None else palette.success if result.ok else palette.danger
        dot = label("●")
        dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        dot.setToolTip(
            tr("card.checking") if result is None else tr("card.online") if result.ok else tr("card.offline", error=result.error)
        )
        name = ElidedLabel(provider.title, "providerName")
        url = ElidedLabel(host(provider.base_url), "providerUrl")
        count = label(str(len(provider.models)), "countBadge")
        count.setToolTip(tr("card.count"))
        count.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        new = len([m for m in (result.models if result and result.ok else []) if m.id not in provider.models])

        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(name)
        text.addWidget(url)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)
        if new:
            badge = pill(f"+{new}", "accent")
            badge.setToolTip(tr("card.new"))
            layout.addWidget(badge)
        layout.addWidget(count)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        repolish(self)

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setProperty("hover", True)
        repolish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hover", False)
        repolish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.provider_id)
        super().mousePressEvent(event)


class SuggestionCard(QFrame):
    added = Signal(object)

    def __init__(self, suggestion: Suggestion) -> None:
        super().__init__()
        self.setObjectName("suggestion")
        text = label(f"<b>{suggestion.name}</b><br>{host(suggestion.base_url)} · {tr('suggestion.models', count=suggestion.count)}")
        text.setObjectName("suggestionText")
        add = button(tr("suggestion.add"), "link")
        add.clicked.connect(lambda: self.added.emit(suggestion))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.addWidget(text, 1)
        layout.addWidget(add)


class ModelRowWidget(QFrame):
    toggled = Signal()
    tools_toggled = Signal(str, bool)

    def __init__(self, row: ModelRow, checked: bool, last: bool) -> None:
        super().__init__()
        self.row = row
        self.setObjectName("modelRow")
        self.setProperty("last", last)
        self.check = QCheckBox()
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check.setChecked(checked)
        self.check.toggled.connect(lambda _checked: self.toggled.emit())

        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(ElidedLabel(row.name, "modelName"))
        if row.name != row.id:
            names.addWidget(ElidedLabel(row.id, "mono", Qt.TextElideMode.ElideMiddle))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 11, 16, 11)
        layout.setSpacing(12)
        layout.addWidget(self.check)
        layout.addLayout(names, 1)
        remote = row.remote
        if remote and remote.context:
            chip = pill(tokens(remote.context), "muted")
            chip.setToolTip(tr("row.context", count=f"{remote.context:,}".replace(",", " ")))
            layout.addWidget(chip)
        if row.in_config:
            # opencode treats a model without an explicit setting as able to call tools.
            enabled = row.tools is not False
            toggle = QPushButton(tr("row.tools") if enabled else tr("row.noTools"))
            toggle.setObjectName("pill")
            toggle.setProperty("tone", "muted" if enabled else "warning")
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setToolTip(
                tr("row.toolsHint") + "\n" + tr("row.toolsToggle")
                if enabled
                else tr("row.noToolsHint") + "\n" + tr("row.noToolsToggle")
            )
            toggle.clicked.connect(lambda: self.tools_toggled.emit(row.id, not enabled))
            layout.addWidget(toggle)
        elif row.tools is not None:
            tools = pill(tr("row.tools") if row.tools else tr("row.noTools"), "muted" if row.tools else "warning")
            tools.setToolTip(tr("row.toolsHint") if row.tools else tr("row.noToolsHint"))
            layout.addWidget(tools)
        status = {
            "new": (tr("status.new"), "accent"),
            "configured": (tr("status.configured"), "success"),
            "missing": (tr("status.missing"), "warning"),
        }[row.status]
        layout.addWidget(pill(*status))


class AddProviderDialog(QDialog):
    """Name, URL and optional key for a new OpenAI-compatible provider, with a connection check."""

    def __init__(self, parent: QWidget, existing: set[str], preset: Suggestion | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.title"))
        self.setMinimumWidth(460)
        self.existing = existing
        self.result_models: list[RemoteModel] = []
        self.name = QLineEdit(preset.name if preset else "")
        self.name.setPlaceholderText(tr("dialog.namePlaceholder"))
        self.ident = QLineEdit(preset.id if preset else "")
        self.ident.setPlaceholderText("ollama-mac")
        self.url = QLineEdit(preset.base_url if preset else "")
        self.url.setPlaceholderText("http://192.168.1.10:11434/v1")
        self.key = QLineEdit()
        self.key.setPlaceholderText(tr("dialog.keyPlaceholder"))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.add_models = QCheckBox(tr("dialog.addModels"))
        self.add_models.setChecked(True)
        self.status = label("", "hint", wrap=True)
        self.name.textEdited.connect(self._suggest_id)

        title = label(tr("dialog.title"), "title")
        title.setStyleSheet("font-size: 18px;")
        hint = label(tr("dialog.hint"), "hint", wrap=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(10)
        for caption, field in ((tr("dialog.name"), self.name), (tr("dialog.id"), self.ident), (tr("dialog.url"), self.url), (tr("dialog.key"), self.key)):
            layout.addWidget(label(caption, "fieldLabel"))
            layout.addWidget(field)
            layout.addSpacing(4)
        layout.addWidget(self.add_models)
        layout.addWidget(self.status)
        layout.addSpacing(8)

        check = button(tr("dialog.check"), icon_name="refresh")
        check.clicked.connect(self._check)
        cancel = button(tr("dialog.cancel"), "ghost")
        cancel.clicked.connect(self.reject)
        self.save = button(tr("dialog.add"), "primary", "plus")
        self.save.clicked.connect(self._accept)
        actions = QHBoxLayout()
        actions.addWidget(check)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self.save)
        layout.addLayout(actions)
        if preset:
            self._check()

    def values(self) -> tuple[str, str, str, str | None]:
        return (
            self.ident.text().strip(),
            self.name.text().strip(),
            self.url.text().strip().rstrip("/"),
            self.key.text().strip() or None,
        )

    def _suggest_id(self, text: str) -> None:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        self.ident.setText(slug)

    def _set_status(self, text: str, name: str) -> None:
        self.status.setText(text)
        self.status.setObjectName(name)
        repolish(self.status)

    def _check(self) -> None:
        _, _, url, key = self.values()
        if not url:
            self._set_status(tr("dialog.needUrl"), "error")
            return
        self._set_status(tr("dialog.connecting"), "hint")
        tasks.run(lambda: discovery.discover(url, key), self._checked, lambda message: self._set_status(message, "error"))

    def _checked(self, result: Discovery) -> None:
        if not result.ok:
            self._set_status(tr("dialog.failed", error=result.error), "error")
            return
        self.result_models = result.models
        self._set_status(tr("dialog.works", server=tr(f"server.{result.server}"), count=len(result.models)), "hint")

    def _accept(self) -> None:
        ident, _, url, _ = self.values()
        if not ident or not url:
            self._set_status(tr("dialog.needIdUrl"), "error")
            return
        if ident in self.existing:
            self._set_status(tr("dialog.exists", id=ident), "error")
            return
        self.accept()


class MainWindow(QMainWindow):
    synced = Signal(str)
    language_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenCode Model Sync")
        self.setWindowIcon(icons.logo())
        self.resize(1080, 700)
        self.setMinimumSize(860, 540)
        self.config_file = config_path()
        self.config = OpencodeConfig.load(self.config_file)
        self.results: dict[str, Discovery | None] = {}
        self.suggestions: list[Suggestion] = []
        self.selected: str | None = None
        self.checked: dict[str, set[str]] = {}
        self.busy = False

        self.sidebar = self._build_sidebar()
        self.content = QWidget()
        self.content.setObjectName("content")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(28, 24, 28, 22)
        self.content_layout.setSpacing(14)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.content, 1)
        self.setCentralWidget(root)

        # opencode or the user may edit the config while the window is open.
        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(str(self.config_file.parent))
        self.watcher.directoryChanged.connect(lambda _: self._reload_debounced.start())
        self._reload_debounced = QTimer(self, singleShot=True, interval=400)
        self._reload_debounced.timeout.connect(self._reload_config)
        self.banner_timer = QTimer(self, singleShot=True, interval=6000)
        self.banner_timer.timeout.connect(lambda: self.banner.hide())
        self.banner = QFrame()
        self.banner.hide()

        self.refresh()

    # ---- data

    def managed(self) -> list[Provider]:
        """Providers this app can sync: the ones with their own API address."""
        return [provider for provider in self.config.providers() if provider.base_url]

    def refresh(self) -> None:
        self._reload_config()
        for provider in self.managed():
            self.results[provider.id] = None
            self._discover(provider)
        tasks.run(lambda: discovery.scan_local(self.config), self._suggested, lambda _: None)
        self.render()

    def _discover(self, provider: Provider) -> None:
        def done(result: Discovery) -> None:
            if not self.config.provider(provider.id):
                return
            self.results[provider.id] = result
            self.checked.setdefault(provider.id, set()).update(
                model.id for model in result.models if model.id not in provider.models
            )
            self.render()

        tasks.run(lambda: discovery.discover(provider.base_url or "", provider.api_key), done, lambda _: None)

    def _suggested(self, suggestions: list[Suggestion]) -> None:
        self.suggestions = suggestions
        self.render_sidebar()

    def _reload_config(self) -> None:
        try:
            self.config = OpencodeConfig.load(self.config_file)
        except ConfigError as error:
            self.show_banner(str(error), "danger")
            return
        if self.selected not in {provider.id for provider in self.managed()}:
            self.selected = next((provider.id for provider in self.managed()), None)
        active = {provider.id for provider in self.config.providers()}
        self.results = {key: value for key, value in self.results.items() if key in active}
        self.checked = {key: value for key, value in self.checked.items() if key in active}
        self.render()

    # ---- actions

    def sync(self, provider_id: str, only_checked: bool = False) -> None:
        provider = self.config.provider(provider_id)
        result = self.results.get(provider_id)
        if not provider or not result or not result.ok:
            return
        rows = discovery.diff(provider, result)
        chosen = self.checked.get(provider_id, set())
        add = [row.remote for row in rows if row.status == "new" and row.remote and (not only_checked or row.id in chosen)]
        if not add:
            self.show_banner(tr("banner.noNew", provider=provider.title), "accent")
            return
        self._write(provider_id, add, [], tr("banner.added", provider=provider.title, count=len(add)))

    def sync_all(self) -> None:
        plan = []
        for provider in self.managed():
            result = self.results.get(provider.id)
            if result and result.ok:
                add = [row.remote for row in discovery.diff(provider, result) if row.status == "new" and row.remote]
                if add:
                    plan.append((provider.id, add))
        if not plan:
            self.show_banner(tr("banner.allSynced"), "accent")
            self.synced.emit(tr("banner.allSynced"))
            return
        total = sum(len(add) for _, add in plan)

        def work() -> None:
            config = OpencodeConfig.load(self.config_file)
            for provider_id, add in plan:
                discovery.apply(config, provider_id, add, [])

        message = tr("banner.addedAll", count=total, providers=len(plan))
        self._run_write(work, message)

    def remove_selected(self, provider_id: str) -> None:
        provider = self.config.provider(provider_id)
        if not provider:
            return
        chosen = self.checked.get(provider_id, set())
        rows = discovery.diff(provider, self.results.get(provider_id) or Discovery(ok=False))
        remove = [row.id for row in rows if row.in_config and row.id in chosen]
        if not remove:
            return
        answer = QMessageBox.question(
            self,
            tr("remove.title"),
            tr("remove.text", count=len(remove)) + "\n\n" + "\n".join(remove),
        )
        if answer == QMessageBox.StandardButton.Yes:
            chosen.difference_update(remove)
            self._write(provider_id, [], remove, tr("banner.removed", provider=provider.title, count=len(remove)))

    def set_tools(self, provider_id: str, model_id: str, enabled: bool) -> None:
        def work() -> None:
            config = OpencodeConfig.load(self.config_file)
            config.set_model_tools(provider_id, model_id, enabled)
            config.save()

        self._run_write(work, tr("banner.toolsOn" if enabled else "banner.toolsOff", model=model_id))

    def add_provider(self, preset: Suggestion | None = None) -> None:
        dialog = AddProviderDialog(self, {provider.id for provider in self.config.providers()}, preset)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ident, name, url, key = dialog.values()
        models = dialog.result_models if dialog.add_models.isChecked() else []

        def work() -> None:
            config = OpencodeConfig.load(self.config_file)
            config.add_provider(ident, name, url, key)
            discovery.apply(config, ident, models, [])

        self.selected = ident
        self._run_write(work, tr("banner.providerAdded", name=name or ident, count=len(models)), refresh=True)

    def rename_provider(self, provider_id: str) -> None:
        if self.busy:
            return
        provider = self.config.provider(provider_id)
        if not provider:
            return
        name, accepted = QInputDialog.getText(
            self, tr("provider.rename"), tr("dialog.name"), text=provider.title
        )
        if not accepted or name.strip() == provider.title:
            return

        def work() -> None:
            config = OpencodeConfig.load(self.config_file)
            config.rename_provider(provider_id, name)
            config.save()

        self._run_write(work, tr("banner.providerRenamed", name=name.strip()))

    def remove_provider(self, provider_id: str) -> None:
        if self.busy:
            return
        provider = self.config.provider(provider_id)
        if not provider:
            return
        answer = QMessageBox.question(
            self, tr("provider.remove"), tr("provider.removeConfirm", name=provider.title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def work() -> None:
            config = OpencodeConfig.load(self.config_file)
            config.remove_provider(provider_id)
            config.save()

        self._run_write(work, tr("banner.providerRemoved", name=provider.title))

    def _write(self, provider_id: str, add: list[RemoteModel], remove: list[str], message: str) -> None:
        def work() -> None:
            # Re-read the file so edits made since the window loaded it are not overwritten.
            discovery.apply(OpencodeConfig.load(self.config_file), provider_id, add, remove)

        self._run_write(work, message)

    def _run_write(self, work, message: str, refresh: bool = False) -> None:
        self.busy = True
        self.render()

        def done(_: object) -> None:
            self.busy = False
            self.show_banner(message, "success")
            self.synced.emit(message)
            if refresh:
                self.refresh()
            else:
                self._reload_config()

        def failed(error: str) -> None:
            self.busy = False
            self.show_banner(tr("banner.saveFailed", error=error), "danger")
            self.render()

        tasks.run(work, done, failed)

    # ---- rendering

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(6)

        logo = QLabel()
        logo.setPixmap(icons.logo().pixmap(34, 34))
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(label("Model Sync", "brand"))
        self.brand_sub = label(tr("app.brandSub"), "brandSub")
        brand.addWidget(self.brand_sub)
        header = QHBoxLayout()
        header.setContentsMargins(6, 0, 0, 10)
        header.setSpacing(10)
        header.addWidget(logo)
        header.addLayout(brand, 1)
        layout.addLayout(header)

        self.providers_label = label(tr("sidebar.providers"), "sectionLabel")
        layout.addWidget(self.providers_label)
        self.provider_list = QListWidget()
        self.provider_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.provider_list.setSpacing(2)
        layout.addWidget(self.provider_list, 1)

        self.suggestion_box = QVBoxLayout()
        self.suggestion_box.setSpacing(6)
        layout.addLayout(self.suggestion_box)

        self.add_button = button(tr("sidebar.addProvider"), "ghost", "plus")
        self.add_button.clicked.connect(lambda: self.add_provider())
        self.language_button = button("", "ghost")
        self.language_button.clicked.connect(self.switch_language)
        bottom = QHBoxLayout()
        bottom.addWidget(self.add_button)
        bottom.addStretch(1)
        bottom.addWidget(self.language_button)
        layout.addLayout(bottom)
        return sidebar

    def switch_language(self) -> None:
        i18n.set_language("en" if i18n.language() == "ru" else "ru")
        self.language_changed.emit()
        self.render()

    def render(self) -> None:
        self.render_sidebar()
        self.render_content()

    def render_sidebar(self) -> None:
        self.brand_sub.setText(tr("app.brandSub"))
        self.providers_label.setText(tr("sidebar.providers"))
        self.add_button.setText(tr("sidebar.addProvider"))
        self.add_button.setEnabled(not self.busy)
        # The button names the language it switches to.
        self.language_button.setText("EN" if i18n.language() == "ru" else "RU")
        self.language_button.setToolTip(tr("sidebar.language"))
        self.provider_list.clear()
        for provider in self.managed():
            card = ProviderCard(provider, self.results.get(provider.id))
            card.set_selected(provider.id == self.selected)
            card.clicked.connect(self._select)
            item = QListWidgetItem()
            item.setSizeHint(card.sizeHint())
            self.provider_list.addItem(item)
            self.provider_list.setItemWidget(item, card)

        while self.suggestion_box.count():
            widget = self.suggestion_box.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        if self.suggestions:
            self.suggestion_box.addWidget(label(tr("sidebar.found"), "sectionLabel"))
            for suggestion in self.suggestions:
                card = SuggestionCard(suggestion)
                card.added.connect(self.add_provider)
                self.suggestion_box.addWidget(card)

    def _select(self, provider_id: str) -> None:
        self.selected = provider_id
        self.render()

    def render_content(self) -> None:
        layout = self.content_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() and item.widget() is not self.banner:
                item.widget().deleteLater()
            elif item.layout():
                _clear(item.layout())

        layout.addLayout(self._top_bar())
        layout.addWidget(self.banner)
        provider = self.config.provider(self.selected) if self.selected else None
        if not provider:
            empty = label(
                tr("empty.noProviders"),
                "empty",
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty, 1)
            return
        result = self.results.get(provider.id)
        layout.addLayout(self._provider_header(provider, result))
        layout.addWidget(self._model_list(provider, result), 1)
        layout.addLayout(self._footer(provider, result))

    def _top_bar(self) -> QHBoxLayout:
        folder = button("", "ghost", "folder")
        folder.setToolTip(tr("top.openFolder"))
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config_file.parent))))
        path = ElidedLabel(str(self.config_file), "configPath", Qt.TextElideMode.ElideMiddle)
        refresh = button(tr("top.refresh"), icon_name="refresh")
        refresh.setToolTip(tr("top.refreshHint"))
        refresh.clicked.connect(self.refresh)
        sync_all = button(tr("top.syncAll"), "primary", "sync")
        sync_all.setEnabled(not self.busy)
        sync_all.setToolTip(tr("top.syncAllHint"))
        sync_all.clicked.connect(self.sync_all)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(folder)
        bar.addWidget(path, 1)
        bar.addWidget(refresh)
        bar.addWidget(sync_all)
        return bar

    def _provider_header(self, provider: Provider, result: Discovery | None) -> QHBoxLayout:
        title = ElidedLabel(provider.title, "title")
        details = [provider.base_url or ""]
        if result and result.ok:
            details.append(tr(f"server.{result.server}"))
        subtitle = ElidedLabel("  ·  ".join(details), "subtitle")
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(title)
        text.addWidget(subtitle)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addLayout(text, 1)
        if result is None:
            header.addWidget(pill(tr("header.checking"), "muted"))
        elif not result.ok:
            header.addWidget(pill(tr("header.offline"), "danger"))
        sync = button(tr("header.sync"), "primary", "sync")
        sync.setEnabled(bool(result and result.ok) and not self.busy)
        sync.setToolTip(tr("header.syncHint"))
        sync.clicked.connect(lambda: self.sync(provider.id))
        header.addWidget(sync, 0, Qt.AlignmentFlag.AlignVCenter)
        manage = button("⋯", "ghost")
        manage.setObjectName("providerActions")
        manage.setAccessibleName(tr("provider.actions"))
        manage.setToolTip(tr("provider.actions"))
        manage.setEnabled(not self.busy)
        menu = QMenu(manage)
        menu.addAction(tr("provider.rename")).triggered.connect(lambda: self.rename_provider(provider.id))
        menu.addAction(tr("provider.remove")).triggered.connect(lambda: self.remove_provider(provider.id))
        manage.setMenu(menu)
        header.addWidget(manage, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _model_list(self, provider: Provider, result: Discovery | None) -> QWidget:
        rows = discovery.diff(provider, result or Discovery(ok=False))
        if not rows:
            text = (
                tr("empty.offline", error=result.error)
                if result is not None and not result.ok
                else tr("empty.noModels")
            )
            empty = label(text, "empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return empty
        container = QFrame()
        container.setObjectName("modelList")
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        chosen = self.checked.setdefault(provider.id, set())
        for index, row in enumerate(rows):
            widget = ModelRowWidget(row, row.id in chosen, index == len(rows) - 1)
            widget.toggled.connect(lambda w=widget, pid=provider.id: self._toggle(pid, w))
            widget.tools_toggled.connect(lambda model, value, pid=provider.id: self.set_tools(pid, model, value))
            column.addWidget(widget)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)
        return scroll

    def _toggle(self, provider_id: str, widget: ModelRowWidget) -> None:
        chosen = self.checked.setdefault(provider_id, set())
        if widget.check.isChecked():
            chosen.add(widget.row.id)
        else:
            chosen.discard(widget.row.id)
        QTimer.singleShot(0, self.render_content)

    def _footer(self, provider: Provider, result: Discovery | None) -> QHBoxLayout:
        rows = discovery.diff(provider, result or Discovery(ok=False))
        chosen = self.checked.get(provider.id, set())
        new = [row for row in rows if row.status == "new"]
        missing = [row for row in rows if row.status == "missing"]
        picked_new = [row for row in new if row.id in chosen]
        picked_config = [row for row in rows if row.in_config and row.id in chosen]
        configured = len([row for row in rows if row.in_config])

        summary = label(
            tr("footer.summary", configured=configured, new=len(new), missing=len(missing)), "subtitle"
        )
        footer = QHBoxLayout()
        footer.addWidget(summary, 1)
        if configured:
            remove = button(tr("footer.remove", count=len(picked_config)), "danger", "trash", theme.current().danger)
            remove.setEnabled(bool(picked_config) and not self.busy)
            remove.clicked.connect(lambda: self.remove_selected(provider.id))
            footer.addWidget(remove)
        if new:
            add = button(tr("footer.add", count=len(picked_new)), icon_name="plus")
            add.setEnabled(bool(picked_new) and not self.busy)
            add.clicked.connect(lambda: self.sync(provider.id, only_checked=True))
            footer.addWidget(add)
        return footer

    def show_banner(self, text: str, tone: str) -> None:
        self.banner.deleteLater()
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        self.banner.setProperty("tone", tone)
        row = QHBoxLayout(self.banner)
        row.setContentsMargins(14, 10, 14, 10)
        row.addWidget(label(text, wrap=True), 1)
        self.render_content()
        self.banner_timer.start()


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())
