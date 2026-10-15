"""Russian and English interface text.

Every visible string goes through ``tr(key, **values)``. English is the fallback for a missing key,
so an untranslated string still shows something readable.
"""

from __future__ import annotations

LANGUAGES = {"en": "English", "ru": "Русский"}

_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "app.brandSub": "models for opencode",
        "app.trayHint": "The app keeps running in the tray.",
        "tray.open": "Open",
        "tray.syncAll": "Sync all",
        "tray.quit": "Quit",
        "server.ollama": "Ollama",
        "server.lmstudio": "LM Studio",
        "server.openai": "OpenAI-compatible",
        "sidebar.providers": "PROVIDERS",
        "sidebar.found": "FOUND ON THIS COMPUTER",
        "sidebar.addProvider": "Add provider",
        "sidebar.language": "Interface language",
        "card.checking": "Checking…",
        "card.online": "Server is responding",
        "card.offline": "No response: {error}",
        "card.count": "Models in the opencode config",
        "card.new": "New models on the server",
        "suggestion.models": "models: {count}",
        "suggestion.add": "Add",
        "row.context": "Context: {count} tokens",
        "row.tools": "tool calling",
        "row.noTools": "no tool calling",
        "row.toolsHint": "The model can call tools: read files, run commands, edit code. "
        "opencode's agent needs this to work on a project.",
        "row.noToolsHint": "The model cannot call tools, so in opencode it can only chat.",
        "row.toolsToggle": "Click to turn tool calling off for this model in opencode.",
        "row.noToolsToggle": "Click to turn tool calling on for this model in opencode.",
        "status.new": "New",
        "status.configured": "In config",
        "status.missing": "Not on server",
        "top.openFolder": "Open the opencode config folder",
        "top.refresh": "Refresh",
        "top.refreshHint": "Ask the servers again. The config is not changed.",
        "top.syncAll": "Sync all",
        "top.syncAllHint": "Add new models of every provider",
        "header.checking": "Checking server…",
        "header.offline": "No response",
        "header.sync": "Sync",
        "header.syncHint": "Add every new model of this provider to the config",
        "empty.noProviders": "The opencode config has no providers with their own API address yet.\n"
        "Add a provider on the left or pick a local server that was found.",
        "empty.offline": "Server is not responding: {error}",
        "empty.noModels": "No models in the config or on the server.",
        "footer.summary": "In config: {configured}   ·   New: {new}   ·   Not on server: {missing}",
        "footer.remove": "Remove from config ({count})",
        "footer.add": "Add selected ({count})",
        "banner.noNew": "{provider}: no new models.",
        "banner.added": "{provider}: models added — {count}.",
        "banner.allSynced": "All providers are already in sync.",
        "banner.addedAll": "Models added — {count}, providers — {providers}.",
        "banner.removed": "{provider}: models removed — {count}.",
        "banner.providerAdded": "Provider “{name}” added, models — {count}.",
        "banner.saveFailed": "Could not save the config: {error}",
        "banner.toolsOn": "{model}: tool calling is on.",
        "banner.toolsOff": "{model}: tool calling is off.",
        "remove.title": "Remove models",
        "remove.text": "Remove the selected models from the opencode config ({count})?",
        "dialog.title": "New provider",
        "dialog.hint": "Any OpenAI-compatible server: Ollama, LM Studio, vLLM, llama.cpp and others.",
        "dialog.name": "Name",
        "dialog.namePlaceholder": "For example, Ollama on Mac",
        "dialog.id": "ID in opencode",
        "dialog.url": "API address",
        "dialog.key": "API key",
        "dialog.keyPlaceholder": "Optional",
        "dialog.addModels": "Add the models it finds right away",
        "dialog.check": "Check",
        "dialog.cancel": "Cancel",
        "dialog.add": "Add",
        "dialog.needUrl": "Enter the API address.",
        "dialog.connecting": "Connecting…",
        "dialog.failed": "The server did not respond: {error}",
        "dialog.works": "Works: {server}, models: {count}.",
        "dialog.needIdUrl": "An ID and an API address are required.",
        "dialog.exists": "Provider “{id}” is already in the config.",
        "error.comments": "{file} has comments, which would be lost on save; edit it by hand instead.",
        "error.badId": "A provider ID may contain only letters, digits, '.', '_' and '-'.",
        "error.exists": "Provider “{id}” already exists.",
        "error.missing": "Provider “{id}” is not in the config.",
        "error.invalidJson": "{file} is not valid JSON: {error}",
    },
    "ru": {
        "app.brandSub": "модели для opencode",
        "app.trayHint": "Приложение работает в трее.",
        "tray.open": "Открыть",
        "tray.syncAll": "Синхронизировать всё",
        "tray.quit": "Выход",
        "server.ollama": "Ollama",
        "server.lmstudio": "LM Studio",
        "server.openai": "OpenAI-совместимый",
        "sidebar.providers": "ПРОВАЙДЕРЫ",
        "sidebar.found": "НАЙДЕНО НА ЭТОМ КОМПЬЮТЕРЕ",
        "sidebar.addProvider": "Добавить провайдера",
        "sidebar.language": "Язык интерфейса",
        "card.checking": "Проверяется…",
        "card.online": "Сервер отвечает",
        "card.offline": "Нет ответа: {error}",
        "card.count": "Моделей в конфиге opencode",
        "card.new": "Новых моделей на сервере",
        "suggestion.models": "моделей: {count}",
        "suggestion.add": "Добавить",
        "row.context": "Контекст: {count} токенов",
        "row.tools": "вызов инструментов",
        "row.noTools": "без инструментов",
        "row.toolsHint": "Модель умеет вызывать инструменты: читать файлы, запускать команды, править код. "
        "Без этого агент opencode не сможет работать с проектом.",
        "row.noToolsHint": "Модель не умеет вызывать инструменты, поэтому в opencode сможет только переписываться в чате.",
        "row.toolsToggle": "Нажмите, чтобы выключить вызов инструментов у этой модели в opencode.",
        "row.noToolsToggle": "Нажмите, чтобы включить вызов инструментов у этой модели в opencode.",
        "status.new": "Новая",
        "status.configured": "В конфиге",
        "status.missing": "Нет на сервере",
        "top.openFolder": "Открыть папку конфига opencode",
        "top.refresh": "Обновить",
        "top.refreshHint": "Заново опросить серверы. Конфиг не меняется.",
        "top.syncAll": "Синхронизировать всё",
        "top.syncAllHint": "Добавить новые модели всех провайдеров",
        "header.checking": "Проверяю сервер…",
        "header.offline": "Нет ответа",
        "header.sync": "Синхронизировать",
        "header.syncHint": "Добавить в конфиг все новые модели этого провайдера",
        "empty.noProviders": "В конфиге opencode пока нет провайдеров со своим адресом API.\n"
        "Добавьте провайдера слева или выберите найденный локальный сервер.",
        "empty.offline": "Сервер не отвечает: {error}",
        "empty.noModels": "Моделей нет ни в конфиге, ни на сервере.",
        "footer.summary": "В конфиге: {configured}   ·   Новых: {new}   ·   Нет на сервере: {missing}",
        "footer.remove": "Удалить из конфига ({count})",
        "footer.add": "Добавить отмеченные ({count})",
        "banner.noNew": "{provider}: новых моделей нет.",
        "banner.added": "{provider}: добавлено моделей — {count}.",
        "banner.allSynced": "Все провайдеры уже синхронизированы.",
        "banner.addedAll": "Добавлено моделей — {count}, провайдеров — {providers}.",
        "banner.removed": "{provider}: удалено моделей — {count}.",
        "banner.providerAdded": "Провайдер «{name}» добавлен, моделей — {count}.",
        "banner.saveFailed": "Не удалось сохранить конфиг: {error}",
        "banner.toolsOn": "{model}: вызов инструментов включён.",
        "banner.toolsOff": "{model}: вызов инструментов выключен.",
        "remove.title": "Удалить модели",
        "remove.text": "Удалить выбранные модели из конфига opencode ({count})?",
        "dialog.title": "Новый провайдер",
        "dialog.hint": "Любой OpenAI-совместимый сервер: Ollama, LM Studio, vLLM, llama.cpp и другие.",
        "dialog.name": "Название",
        "dialog.namePlaceholder": "Например, Ollama на Mac",
        "dialog.id": "ID в opencode",
        "dialog.url": "Адрес API",
        "dialog.key": "API-ключ",
        "dialog.keyPlaceholder": "Необязательно",
        "dialog.addModels": "Сразу добавить найденные модели",
        "dialog.check": "Проверить",
        "dialog.cancel": "Отмена",
        "dialog.add": "Добавить",
        "dialog.needUrl": "Укажите адрес API.",
        "dialog.connecting": "Подключаюсь…",
        "dialog.failed": "Сервер не ответил: {error}",
        "dialog.works": "Работает: {server}, моделей: {count}.",
        "dialog.needIdUrl": "Нужны ID и адрес API.",
        "dialog.exists": "Провайдер «{id}» уже есть в конфиге.",
        "error.comments": "В {file} есть комментарии, при сохранении они потерялись бы. Отредактируйте файл вручную.",
        "error.badId": "ID провайдера может содержать только буквы, цифры, «.», «_» и «-».",
        "error.exists": "Провайдер «{id}» уже существует.",
        "error.missing": "Провайдера «{id}» нет в конфиге.",
        "error.invalidJson": "{file} не является корректным JSON: {error}",
    },
}

_language = "en"


def set_language(code: str) -> None:
    global _language
    _language = code if code in _TEXT else "en"


def language() -> str:
    return _language


def detect(ui_languages: list[str]) -> str:
    """The first supported language from the system's preferred list, else English."""
    for name in ui_languages:
        code = name.replace("_", "-").split("-")[0].lower()
        if code in _TEXT:
            return code
    return "en"


def tr(key: str, **values: object) -> str:
    text = _TEXT[_language].get(key) or _TEXT["en"][key]
    return text.format(**values) if values else text
