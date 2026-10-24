"""MCP discovery and a reviewable, editable connection form."""
from __future__ import annotations

from copy import deepcopy
import html
import json
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QSplitter, QVBoxLayout, QWidget,
)

from . import i18n, mcp_catalog as catalog, tasks, theme
from .widgets import button, label, repolish, scrolled


TEXT = {
    "catalog": ("MCP catalog", "Каталог MCP"),
    "browse": ("Add from catalog", "Добавить из каталога"),
    "intro": ("Choose a server, review its connection settings, then save on the MCP page.", "Выберите сервер, проверьте подключение и сохраните изменения на странице MCP."),
    "starter": ("Starter collection", "Для начала"),
    "registry": ("Official MCP Registry", "Официальный реестр MCP"),
    "glama": ("Glama · source repositories", "Glama · репозитории серверов"),
    "glama_remote": ("Glama · remote servers", "Glama · удалённые серверы"),
    "search": ("Search", "Найти"),
    "query": ("Server name or task, e.g. documentation", "Название или задача, например documentation"),
    "key": ("Glama API key (this window only, or GLAMA_API_KEY)", "API-ключ Glama (только в этом окне, либо GLAMA_API_KEY)"),
    "getKey": ("Get a Glama key", "Получить ключ Glama"),
    "loading": ("Loading catalog…", "Загружаю каталог…"),
    "count": ("Servers shown: {count}", "Показано серверов: {count}"),
    "empty": ("No results. Try another name or source.", "Ничего не найдено. Попробуйте другое название или источник."),
    "more": ("Load more", "Загрузить ещё"),
    "add": ("Configure and add…", "Настроить и добавить…"),
    "close": ("Close", "Закрыть"),
    "source": ("Source", "Источник"),
    "publisher": ("Publisher / repository", "Разработчик / репозиторий"),
    "promoted": ("Advertising", "Реклама"),
    "recipe": ("Connection option", "Вариант подключения"),
    "manual": ("The source does not provide a ready connection. Open its instructions, then enter the URL or command.", "Источник не публикует готовое подключение. Откройте инструкцию и укажите адрес или команду."),
    "noSelection": ("Select a server to see its description and connection options.", "Выберите сервер, чтобы увидеть описание и варианты подключения."),
    "glamaCredit": ("MCP data from Glama", "Данные MCP предоставлены Glama"),
    "setup": ("Add MCP server", "Добавить MCP-сервер"),
    "name": ("Name in OpenCode", "Имя в OpenCode"),
    "type": ("Connection", "Подключение"),
    "remote": ("Remote (URL)", "Удалённое (адрес)"),
    "local": ("Local (command)", "Локальное (команда)"),
    "url": ("Server URL", "Адрес сервера"),
    "command": ("Command as a JSON array", "Команда в виде JSON-массива"),
    "enabled": ("Enable after saving", "Включить после сохранения"),
    "preview": ("Configuration preview", "Предпросмотр настроек"),
    "parameter": ("Add header / environment variable", "Добавить заголовок / переменную окружения"),
    "parameterName": ("Parameter name (header for remote, environment variable for local)", "Имя параметра (заголовок для удалённого, переменная окружения для локального)"),
    "draft": ("Add to settings", "Добавить в настройки"),
    "cancel": ("Cancel", "Отмена"),
    "execution": ("Saving an enabled server lets OpenCode connect to it or run its command. Local servers need the runtime named below.", "После сохранения включённого сервера OpenCode сможет подключиться к нему или запустить его команду. Для локального сервера нужна указанная ниже среда запуска."),
    "env": ("{env:NAME} reads a variable from OpenCode's environment. You can also enter the value here.", "{env:NAME} берёт переменную из окружения OpenCode. Можно также указать значение здесь."),
    "oauth": ("This server uses browser sign-in. After saving, authenticate in OpenCode or run: opencode mcp auth {name}", "Сервер использует вход через браузер. После сохранения авторизуйтесь в OpenCode или выполните: opencode mcp auth {name}"),
    "json": ("Enter a JSON array of command arguments, e.g. [\"npx\", \"-y\", \"package\"].", "Введите JSON-массив команды, например [\"npx\", \"-y\", \"package\"]."),
    "duplicate": ("This name already exists. Choose another name; existing servers are kept.", "Такое имя уже есть. Выберите другое — существующий сервер не будет заменён."),
    "invalid_name": ("Use letters, numbers, dot, underscore or hyphen for the name.", "Для имени используйте латинские буквы, цифры, точку, подчёркивание или дефис."),
    "glama_key": ("Glama requires an API key for directory access. Enter it above, or use the free official registry.", "Для доступа к каталогу Glama нужен API-ключ. Введите его выше или выберите официальный реестр без ключа."),
    "network": ("Could not reach the catalog. Check the connection and retry; the starter collection works offline.", "Каталог недоступен. Проверьте соединение и повторите поиск; подборка «Для начала» работает без сети."),
    "response_format": ("The catalog returned an unsupported response.", "Каталог вернул ответ в неподдерживаемом формате."),
    "response_size": ("The catalog response is too large. Narrow your search.", "Ответ каталога слишком большой. Уточните поиск."),
    "invalid_config": ("Check the connection fields: the configuration does not match OpenCode's schema.", "Проверьте поля подключения: настройки не соответствуют формату OpenCode."),
    "invalid_url": ("Enter an http:// or https:// server URL without embedded credentials.", "Укажите адрес сервера http:// или https:// без логина и пароля внутри адреса."),
    "invalid_command": ("Enter a non-empty command.", "Укажите непустую команду."),
    "placeholders": ("Replace the source's {placeholders} with actual values or {env:VARIABLE} references.", "Замените {заполнители} источника значениями или ссылками {env:VARIABLE}."),
    "http": ("Catalog error: {error}. Check your key or try again later.", "Ошибка каталога: {error}. Проверьте ключ или повторите позже."),
    "unknown": ("Could not load the catalog. Try again later.", "Не удалось загрузить каталог. Повторите позже."),
    "installed": ("Already added", "Уже добавлен"),
}


def t(key: str, **values) -> str:
    text = TEXT[key][i18n.language() == "ru"]
    return text.format(**values) if values else text


def anchor(url: str, title: str) -> str:
    return f'<a style="color: {theme.current().accent_hover}" href="{html.escape(url, quote=True)}">{html.escape(title)}</a>'


def link(url: str, title: str) -> QLabel:
    widget = QLabel()
    if catalog.web_url(url):
        widget.setText(anchor(url, title))
    widget.setOpenExternalLinks(True)
    widget.setWordWrap(True)
    return widget


class SetupDialog(QDialog):
    def __init__(self, entry: catalog.Entry, recipe: catalog.Recipe | None, taken: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("setup"))
        self.resize(690, 680)
        self.taken = taken
        self.template = deepcopy(recipe.config) if recipe else {"type": "remote", "url": ""}
        self.result_name = ""
        self.result_config = None
        self.name = QLineEdit(catalog.server_name(entry.id.rsplit("/", 1)[-1]))
        self.kind = QComboBox()
        self.kind.addItem(t("remote"), "remote")
        self.kind.addItem(t("local"), "local")
        self.kind.setCurrentIndex(1 if self.template["type"] == "local" else 0)
        self.kind.setEnabled(recipe is None)
        self.address = QLineEdit(self.template.get("url", ""))
        self.command = QLineEdit(json.dumps(self.template.get("command", []), ensure_ascii=False))
        self.enabled = QCheckBox(t("enabled"))
        self.enabled.setChecked(True)
        self.parameters = []
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(135)
        self.error = label("", "error", wrap=True)
        self.accept_button = button(t("draft"), "primary", "plus")
        self.accept_button.clicked.connect(self._accept)
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        title = label(entry.name, "title", wrap=True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        content.addWidget(title)
        content.addWidget(link(entry.url, t("source")))
        content.addWidget(label(t("execution"), "hint", wrap=True))
        if recipe and recipe.note:
            content.addWidget(label(recipe.note, "hint", wrap=True))
        if recipe is None:
            content.addWidget(label(t("manual"), "hint", wrap=True))
        form = QFormLayout()
        self.form = form
        form.addRow(t("name"), self.name)
        form.addRow(t("type"), self.kind)
        self.url_label = label(t("url"))
        self.command_label = label(t("command"))
        form.addRow(self.url_label, self.address)
        form.addRow(self.command_label, self.command)
        for group in ("headers", "environment"):
            for key, value in self.template.get(group, {}).items():
                control = QLineEdit(value)
                control.setToolTip(t("env"))
                # Values stay editable; reveal only environment references in the preview.
                control.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
                form.addRow(key, control)
                self.parameters.append((group, key, control))
                control.textChanged.connect(self._preview)
        content.addLayout(form)
        parameter = button(t("parameter"), "ghost", "plus")
        parameter.clicked.connect(self.add_parameter)
        content.addWidget(parameter)
        content.addWidget(label(t("env"), "hint", wrap=True))
        content.addWidget(self.enabled)
        self.auth_note = label("", "hint", wrap=True)
        content.addWidget(self.auth_note)
        content.addWidget(label(t("preview"), "fieldLabel"))
        content.addWidget(self.preview)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(scrolled(body), 1)
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        cancel = button(t("cancel"), "ghost")
        cancel.clicked.connect(self.reject)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self.accept_button)
        layout.addLayout(actions)
        for edit in (self.name, self.address, self.command):
            edit.textChanged.connect(self._preview)
        self.kind.currentIndexChanged.connect(self._preview)
        self.enabled.toggled.connect(self._preview)
        self._preview()

    def add_parameter(self):
        name, ok = QInputDialog.getText(self, t("parameter"), t("parameterName"))
        name = name.strip()
        group = "headers" if self.kind.currentData() == "remote" else "environment"
        if not ok or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name): return
        if any(g == group and key == name for g, key, _ in self.parameters): return
        control = QLineEdit()
        control.setPlaceholderText("{env:" + name.upper().replace("-", "_") + "}")
        control.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        control.setToolTip(t("env"))
        self.parameters.append((group, name, control))
        self.form.addRow(name, control)
        control.textChanged.connect(self._preview)
        # A header supplied by the user replaces automatic OAuth discovery.
        if group == "headers": self.template["oauth"] = False
        self._preview()

    def config(self) -> dict:
        config = deepcopy(self.template)
        config["type"] = self.kind.currentData()
        if config["type"] == "remote":
            config.pop("command", None)
            config.pop("environment", None)
            config["url"] = self.address.text().strip()
        else:
            config.pop("url", None)
            config.pop("headers", None)
            config.pop("oauth", None)
            try:
                command = json.loads(self.command.text())
            except ValueError:
                raise catalog.CatalogError("json") from None
            if not isinstance(command, list) or not all(isinstance(x, str) for x in command):
                raise catalog.CatalogError("json")
            config["command"] = command
        for group, key, edit in self.parameters:
            if group == ("headers" if config["type"] == "remote" else "environment"):
                config.setdefault(group, {})[key] = edit.text().strip()
        config["disabled"] = not self.enabled.isChecked()
        return config

    def _preview(self, *_):
        remote = self.kind.currentData() == "remote"
        self.address.setVisible(remote)
        self.url_label.setVisible(remote)
        self.command.setVisible(not remote)
        self.command_label.setVisible(not remote)
        self.auth_note.setText(t("oauth", name=self.name.text()) if "oauth" in self.template and self.template["oauth"] is not False else "")
        try:
            config = self.config()
            for group in ("headers", "environment"):
                for key, value in config.get(group, {}).items():
                    if value and "{env:" not in value:
                        config[group][key] = "••••"
            self.preview.setPlainText(json.dumps(config, indent=2, ensure_ascii=False))
        except catalog.CatalogError:
            self.preview.setPlainText(t("json"))
        self.error.clear()

    def _accept(self):
        name = self.name.text().strip()
        if not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", name):
            self.error.setText(t("invalid_name"))
            return
        if name in self.taken:
            self.error.setText(t("duplicate"))
            return
        try:
            config = catalog.prepare_config(self.config(), enabled=self.enabled.isChecked())
        except catalog.CatalogError as error:
            self.error.setText(t(str(error)))
            return
        self.result_name, self.result_config = name, config
        self.accept()


class CatalogDialog(QDialog):
    def __init__(self, installed: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("catalog"))
        self.resize(960, 700)
        self.installed = deepcopy(installed)
        self.entries = []
        self.cursor = ""
        self.generation = 0
        self.finished.connect(self._finished)
        self.result_name = ""
        self.result_config = None
        self.source = QComboBox()
        for key in catalog.SOURCES:
            self.source.addItem(t(key), key)
        self.query = QLineEdit()
        self.query.setPlaceholderText(t("query"))
        self.query.setClearButtonEnabled(True)
        self.search = button(t("search"), "primary")
        self.search.clicked.connect(lambda: self.load())
        self.query.returnPressed.connect(lambda: self.load())
        self.source.currentIndexChanged.connect(lambda: self.load())
        self.key = QLineEdit(os.environ.get("GLAMA_API_KEY", ""))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(t("key"))
        self.key.returnPressed.connect(lambda: self.load())
        self.get_key = link("https://glama.ai/settings/api-keys", t("getKey"))
        self.listing = QListWidget()
        self.listing.setMinimumWidth(330)
        self.listing.currentRowChanged.connect(self.details)
        self.listing.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.description = QPlainTextEdit()
        self.description.setReadOnly(True)
        self.source_link = QLabel()
        self.source_link.setOpenExternalLinks(True)
        self.repo_link = QLabel()
        self.repo_link.setOpenExternalLinks(True)
        self.options = QComboBox()
        self.options.currentIndexChanged.connect(self.connection_preview)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.add = button(t("add"), "primary", "plus")
        self.add.clicked.connect(self.add_selected)
        self.status = label("", "hint", wrap=True)
        self.more = button(t("more"))
        self.more.clicked.connect(lambda: self.load(more=True))
        self.credit = QLabel()
        self.credit.setOpenExternalLinks(True)
        self.credit.setWordWrap(True)
        right = QWidget()
        details = QVBoxLayout(right)
        details.setContentsMargins(8, 0, 0, 0)
        details.addWidget(self.description, 2)
        details.addWidget(self.source_link)
        details.addWidget(self.repo_link)
        details.addWidget(label(t("recipe"), "fieldLabel"))
        details.addWidget(self.options)
        details.addWidget(self.preview, 1)
        details.addWidget(self.add)
        split = QSplitter()
        split.addWidget(self.listing)
        split.addWidget(right)
        split.setSizes([400, 500])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.addWidget(label(t("catalog"), "title"))
        layout.addWidget(label(t("intro"), "hint", wrap=True))
        search = QHBoxLayout()
        search.addWidget(self.source)
        search.addWidget(self.query, 1)
        search.addWidget(self.search)
        layout.addLayout(search)
        keyrow = QHBoxLayout()
        keyrow.addWidget(self.key, 1)
        keyrow.addWidget(self.get_key)
        layout.addLayout(keyrow)
        layout.addWidget(split, 1)
        layout.addWidget(self.credit)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        footer.addWidget(self.more)
        close = button(t("close"), "ghost")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.load()

    def _finished(self, *_):
        self.generation += 1
        self.key.clear()

    def load(self, *, more=False):
        source, query = self.source.currentData(), self.query.text().strip()
        if more and (source, query) != getattr(self, "loaded_query", None):
            more = False
        self.generation += 1
        generation = self.generation
        self.key.setVisible(source.startswith("glama"))
        self.get_key.setVisible(source.startswith("glama"))
        credit_url = "https://glama.ai" if source.startswith("glama") else catalog.SOURCES[source]
        credit_text = t("glamaCredit") if source.startswith("glama") else t(source)
        self.credit.setText(anchor(credit_url, credit_text))
        cursor = self.cursor if more else ""
        if not more:
            self.entries = []
            self.listing.clear()
            self.cursor = ""
            self.details(-1)
        self.more.setEnabled(False)
        self.status.setText(t("loading"))
        token = self.key.text().strip()

        def done(page):
            if generation != self.generation: return
            self.loaded_query = (source, query)
            seen = {e.id for e in self.entries}
            for entry in page.entries:
                if entry.id in seen: continue
                seen.add(entry.id)
                self.entries.append(entry)
                item = QListWidgetItem()
                item.setToolTip(entry.description)
                self.listing.addItem(item)
                card = QFrame()
                card.setObjectName("providerCard")
                row = QVBoxLayout(card)
                row.setContentsMargins(8, 6, 8, 6)
                row.setSpacing(2)
                suffix = " · " + t("promoted") if entry.promoted else ""
                if catalog.server_name(entry.id.rsplit("/", 1)[-1]) in self.installed:
                    suffix += " · " + t("installed")
                name = label(entry.name + suffix, "fieldLabel", wrap=True)
                name.setTextFormat(Qt.TextFormat.PlainText)
                row.addWidget(name)
                row.addWidget(link(entry.url, "Glama" if entry.source.startswith("glama") else t("source")))
                card.setMinimumWidth(0)
                item.setSizeHint(card.sizeHint())
                self.listing.setItemWidget(item, card)
            self.cursor = page.cursor if page.cursor != cursor else ""
            self.more.setEnabled(bool(self.cursor))
            self.status.setText(t("count", count=len(self.entries)) if self.entries else t("empty"))
            if self.listing.currentRow() < 0 and self.entries: self.listing.setCurrentRow(0)

        def failed(message):
            if generation != self.generation: return
            self.more.setEnabled(bool(self.cursor))
            self.status.setText(t(message) if message in TEXT else t("http", error=message) if re.fullmatch(r"HTTP \d+", message) else t("unknown"))

        if source == "starter":
            done(catalog.fetch(source, query))
        else:
            tasks.run(lambda: catalog.fetch(source, query, cursor, token), done, failed)

    def details(self, index):
        for row in range(self.listing.count()):
            card = self.listing.itemWidget(self.listing.item(row))
            if card:
                card.setProperty("selected", row == index)
                repolish(card)
        self.options.clear()
        self.source_link.clear()
        self.repo_link.clear()
        entry = self.entries[index] if 0 <= index < len(self.entries) else None
        self.add.setEnabled(entry is not None)
        if not entry:
            self.description.setPlainText(t("noSelection"))
            self.preview.clear()
            return
        self.description.setPlainText(entry.name + "\n\n" + entry.description)
        for widget, url, title in ((self.source_link, entry.url, t("source")), (self.repo_link, entry.repository, t("publisher"))):
            if catalog.web_url(url):
                widget.setText(anchor(url, title))
        for recipe in entry.recipes:
            self.options.addItem(recipe.label)
        self.connection_preview()

    def connection_preview(self, *_):
        index = self.listing.currentRow()
        if not 0 <= index < len(self.entries): return
        entry = self.entries[index]
        recipe_index = self.options.currentIndex()
        self.preview.setPlainText(json.dumps(entry.recipes[recipe_index].config, indent=2, ensure_ascii=False)
                                  if 0 <= recipe_index < len(entry.recipes) else t("manual"))

    def add_selected(self):
        index = self.listing.currentRow()
        if not 0 <= index < len(self.entries): return
        entry = self.entries[index]
        recipe_index = self.options.currentIndex()
        recipe = entry.recipes[recipe_index] if 0 <= recipe_index < len(entry.recipes) else None
        dialog = SetupDialog(entry, recipe, set(self.installed), self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        self.result_name, self.result_config = dialog.result_name, dialog.result_config
        self.accept()
