"""Reading and writing the global opencode config.

opencode reads ``opencode.json`` and ``opencode.jsonc`` from its config directory and lets the later
name win. Providers live in two maps: the legacy ``provider`` map (``npm`` + ``options``) and the
current ``providers`` map (``package`` + ``settings``). When one ID appears in both, opencode replaces
the legacy entry with the current one wholesale, so every edit here goes to the entry opencode uses.

The two maps do not know the same settings either. Only the current map is asked whether a model is
switched off: a ``disabled`` written into the legacy map is read as nothing at all, which is why a
model is switched through :meth:`OpencodeConfig.move_to_current_map` and why a new provider starts in
the current map. The translation lives here too, in the words opencode's own migration uses.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .i18n import tr

CONFIG_NAMES = ("opencode.json", "opencode.jsonc")
LEGACY = "provider"
CURRENT = "providers"
OPENAI_COMPATIBLE = "@ai-sdk/openai-compatible"

# The current map names an AI SDK provider by the SDK that loads it, which is how opencode's own
# migration spells the ``npm`` of a legacy entry.
AISDK = "aisdk:"

# A legacy model's options are read before the request is built: the ones below configure the
# client, everything else is sent to the server as the request body. The same split opencode makes.
COMPATIBLE_SETTINGS = frozenset(
    {
        "apiKey", "baseURL", "body", "chunkTimeout", "disabled", "extraBody", "headerTimeout",
        "headers", "reasoningEffort", "strictJsonSchema", "timeout", "textVerbosity", "user",
    }
)


class ConfigError(Exception):
    """The config cannot be read or safely written."""


@dataclass
class Provider:
    id: str
    name: str
    section: str
    base_url: str | None
    api_key: str | None
    models: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.name or self.id


def config_dir(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if env.get("OPENCODE_CONFIG_DIR"):
        return Path(env["OPENCODE_CONFIG_DIR"])
    base = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    return base / "opencode"


def config_path(directory: Path | None = None) -> Path:
    directory = directory or config_dir()
    existing = [directory / name for name in CONFIG_NAMES if (directory / name).is_file()]
    return existing[-1] if existing else directory / "opencode.json"


class OpencodeConfig:
    def __init__(self, path: Path, data: dict[str, Any], has_comments: bool) -> None:
        self.path = path
        self.data = data
        self.has_comments = has_comments
        self._backed_up = False

    @classmethod
    def load(cls, path: Path | None = None) -> OpencodeConfig:
        path = path or config_path()
        if not path.exists():
            return cls(path, {"$schema": "https://opencode.ai/config.json"}, has_comments=False)
        text = path.read_text(encoding="utf-8")
        try:
            return cls(path, _as_object(json.loads(text) if text.strip() else {}), has_comments=False)
        except json.JSONDecodeError:
            pass
        try:
            return cls(path, _as_object(json.loads(strip_jsonc(text))), has_comments=True)
        except json.JSONDecodeError as error:
            raise ConfigError(tr("error.invalidJson", file=path, error=error)) from error

    def providers(self) -> list[Provider]:
        current = _as_object(self.data.get(CURRENT, {}))
        legacy = _as_object(self.data.get(LEGACY, {}))
        result = [self._provider(pid, entry, CURRENT) for pid, entry in current.items() if isinstance(entry, dict)]
        result += [
            self._provider(pid, entry, LEGACY)
            for pid, entry in legacy.items()
            if isinstance(entry, dict) and pid not in current
        ]
        return sorted(result, key=lambda provider: provider.title.lower())

    def provider(self, provider_id: str) -> Provider | None:
        return next((item for item in self.providers() if item.id == provider_id), None)

    def add_models(self, provider_id: str, models: dict[str, dict[str, Any]]) -> None:
        entry = self._entry(provider_id)
        target = entry.setdefault("models", {})
        for model_id, model in models.items():
            target.setdefault(model_id, model)

    def remove_models(self, provider_id: str, model_ids: list[str]) -> None:
        models = self._entry(provider_id).get("models", {})
        for model_id in model_ids:
            models.pop(model_id, None)

    def set_model_tools(self, provider_id: str, model_id: str, tools: bool) -> None:
        """Turn tool calling on or off for a model already in the config."""
        entry = self._model(provider_id, model_id)
        if self._section(provider_id) == LEGACY:
            entry["tool_call"] = tools
        else:
            entry.setdefault("capabilities", {})["tools"] = tools

    def move_to_current_map(self, provider_id: str) -> bool:
        """Write a legacy provider into the ``providers`` map and drop its old entry; False if it was there.

        Only the current map knows the switch that keeps a model out of opencode, and an entry there
        takes the place of the legacy one wholesale rather than adding to it. So a provider is moved
        with everything it holds: an unfinished entry would leave the provider without its server.
        """
        if self._section(provider_id) == CURRENT:
            return False
        legacy = _as_object(self.data[LEGACY])
        entry = legacy.pop(provider_id)
        if not legacy:
            self.data.pop(LEGACY)  # an empty legacy map only invites the next reader to doubt itself
        try:
            moved = moved_entry(entry)
        except Unmovable as unknown:
            _as_object(self.data.setdefault(LEGACY, {}))[provider_id] = entry  # back exactly as it was
            raise ConfigError(tr("error.cannotMove", id=provider_id, keys=", ".join(unknown.keys))) from None
        _as_object(self.data.setdefault(CURRENT, {}))[provider_id] = moved
        return True

    def set_model_enabled(self, provider_id: str, model_id: str, enabled: bool) -> bool:
        """Switch a model the way opencode's own settings do; True if the provider moved for it.

        Each map has one word for a switched-off model and ignores the other's, so switching off
        writes ``disabled`` where opencode reads it, in the current map: a provider of the legacy map
        is moved there first, because that word means nothing where it is written. Switching back on
        only has to clear the word its own map reads, so a provider that was deprecated by hand is
        not moved for nothing, and no ``disabled: false`` is left behind either way.
        """
        moved = self.move_to_current_map(provider_id) if not enabled else False
        entry = self._model(provider_id, model_id)
        if enabled:
            entry.pop("disabled", None)
            if entry.get("status") == "deprecated":
                entry.pop("status", None)
        else:
            entry["disabled"] = True
        return moved

    def add_provider(self, provider_id: str, name: str, base_url: str, api_key: str | None) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", provider_id):
            raise ConfigError(tr("error.badId"))
        if self.provider(provider_id):
            raise ConfigError(tr("error.exists", id=provider_id))
        # The current map is the one that knows which of its models opencode should offer, so a new
        # provider starts there rather than in the legacy map it would later have to leave.
        settings: dict[str, Any] = {"baseURL": base_url.rstrip("/")}
        if api_key:
            settings["apiKey"] = api_key
        self.data.setdefault(CURRENT, {})[provider_id] = {
            "package": f"{AISDK}{OPENAI_COMPATIBLE}",
            "name": name or provider_id,
            "settings": settings,
            "models": {},
        }

    def rename_provider(self, provider_id: str, name: str) -> None:
        """Change the display name without invalidating provider/model IDs."""
        name = name.strip()
        if not name:
            raise ConfigError(tr("error.emptyName"))
        self._entry(provider_id)["name"] = name

    def remove_provider(self, provider_id: str) -> None:
        self._entry(provider_id)  # Report stale selections before changing anything.
        # Remove shadowed entries as well, or the legacy provider would reappear.
        for section in (LEGACY, CURRENT):
            _as_object(self.data.get(section)).pop(provider_id, None)
        # Let opencode choose a fallback instead of retaining an unavailable model.
        def clear_models(entry: dict[str, Any]) -> None:
            for key in ("model", "small_model"):
                value = entry.get(key)
                if isinstance(value, str) and value.startswith(provider_id + "/"):
                    entry.pop(key)

        clear_models(self.data)
        for section in ("agent", "mode"):
            for entry in _as_object(self.data.get(section)).values():
                if isinstance(entry, dict):
                    clear_models(entry)
        for key in ("enabled_providers", "disabled_providers"):
            if isinstance(self.data.get(key), list):
                self.data[key] = [item for item in self.data[key] if item != provider_id]

    def save(self) -> None:
        if self.has_comments:
            raise ConfigError(tr("error.comments", file=self.path.name))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and not self._backed_up:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.path, self.path.with_name(f"{self.path.name}.bak-model-sync-{stamp}"))
            self._backed_up = True
        text = json.dumps(self.data, indent=2, ensure_ascii=False) + "\n"
        # Write beside the target and swap, so opencode's watcher never reads a half-written file.
        handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".opencode-model-sync-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temp, self.path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise

    def model_entry(self, provider_id: str, name: str | None, context: int | None, tools: bool | None) -> dict:
        """A model definition in the shape of the section that holds the provider."""
        section = self._section(provider_id)
        entry: dict[str, Any] = {}
        if name:
            entry["name"] = name
        if tools is not None:
            if section == LEGACY:
                entry["tool_call"] = tools
            else:
                entry["capabilities"] = {"tools": tools}
        if context:
            # Legacy limits require both fields; half the window leaves room for the prompt.
            entry["limit"] = {"context": context, "output": min(32768, context // 2)}
        return entry

    def _provider(self, provider_id: str, entry: dict[str, Any], section: str) -> Provider:
        settings = _as_object(entry.get("options" if section == LEGACY else "settings", {}))
        base_url = settings.get("baseURL")
        api_key = settings.get("apiKey")
        return Provider(
            id=provider_id,
            name=str(entry.get("name") or provider_id),
            section=section,
            base_url=resolve_variables(base_url) if isinstance(base_url, str) and base_url else None,
            api_key=resolve_variables(api_key) if isinstance(api_key, str) and api_key else None,
            models={key: value for key, value in _as_object(entry.get("models", {})).items() if isinstance(value, dict)},
        )

    def _section(self, provider_id: str) -> str:
        provider = self.provider(provider_id)
        if not provider:
            raise ConfigError(tr("error.missing", id=provider_id))
        return provider.section

    def _entry(self, provider_id: str) -> dict[str, Any]:
        return self.data[self._section(provider_id)][provider_id]

    def _model(self, provider_id: str, model_id: str) -> dict[str, Any]:
        entry = _as_object(self._entry(provider_id).get("models", {})).get(model_id)
        if not isinstance(entry, dict):
            raise ConfigError(tr("error.missing", id=f"{provider_id}/{model_id}"))
        return entry


def configured_tools(entry: dict[str, Any]) -> bool | None:
    """Tool calling as written in a model entry of either section; None when the config does not say."""
    if isinstance(entry.get("tool_call"), bool):
        return entry["tool_call"]
    tools = _as_object(entry.get("capabilities", {})).get("tools")
    return tools if isinstance(tools, bool) else None


def configured_enabled(entry: dict[str, Any], section: str) -> bool:
    """Whether opencode offers a model, which is a different word in each of the two maps.

    Measured on opencode 2.1.4: the legacy map listens to ``status: "deprecated"`` and reads a
    ``disabled`` as nothing, the current map listens to ``disabled`` and reads a ``status`` as
    nothing. Reading the wrong one would show a model as switched off while opencode still offers it.
    """
    if section == LEGACY:
        return entry.get("status") != "deprecated"
    return entry.get("disabled") is not True


# ---- the legacy map in the words of the current one ----

# Each key of a legacy provider entry, and where the current map wants it. The odd ones out are
# ``npm``, which becomes a package specifier, and ``options``, which splits three ways.
PROVIDER_FIELDS = frozenset({"npm", "api", "options", "models", "name", "env", "headers"})
PROVIDER_CURRENT = frozenset({"package", "settings", "body", "compatibility", "request"})
# The same for a model. ``status`` is carried when it says deprecated, which is how the current map
# words a switched-off model too.
MODEL_FIELDS = frozenset(
    {
        "id", "name", "family", "tool_call", "modalities", "limit", "cost", "options", "headers",
        "provider", "variants", "status",
    }
)
MODEL_CURRENT = frozenset({"modelID", "capabilities", "disabled", "description", "time", "variants"})


class Unmovable(Exception):
    """A config entry holds a key this app has no words for in the current map."""

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys


def moved_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """A provider of the legacy map, spelled the way the current map wants it.

    The rules are opencode's own migration: ``npm`` becomes the package it is loaded through,
    ``options`` split into settings, headers and a request body, and a model's ``tool_call`` moves
    into its capabilities. A key with nowhere to go is refused instead of dropped, because a
    provider that quietly lost part of its definition is worse than a switch that waits.
    """
    _portable(entry, PROVIDER_FIELDS | PROVIDER_CURRENT)
    moved: dict[str, Any] = {}
    for key in ("name", "env"):
        if key in entry:
            moved[key] = entry[key]
    npm = entry.get("npm")
    if isinstance(npm, str) and npm:
        moved["package"] = moved_package(npm)
    if isinstance(entry.get("package"), str):
        moved["package"] = entry["package"]

    options = _as_object(entry.get("options"))
    settings = {key: value for key, value in options.items() if key not in ("headers", "body", "setCacheKey")}
    if isinstance(entry.get("api"), str) and entry["api"]:
        settings["baseURL"] = entry["api"]  # the old word for the server address wins over the option
    if settings:
        moved["settings"] = settings
    if isinstance(options.get("setCacheKey"), bool):
        moved["compatibility"] = {"supportsPromptCacheKey": options["setCacheKey"]}
    headers = {**_as_object(options.get("headers")), **_as_object(entry.get("headers"))}
    if headers:
        moved["headers"] = {key: value for key, value in headers.items() if isinstance(value, str)}
    if isinstance(options.get("body"), dict):
        moved["body"] = options["body"]

    if "models" in entry:
        moved["models"] = {
            model_id: moved_model(model, npm) if isinstance(model, dict) else model
            for model_id, model in _as_object(entry.get("models")).items()
        }
    return moved


def moved_model(entry: dict[str, Any], npm: Any) -> dict[str, Any]:
    _portable(entry, MODEL_FIELDS | MODEL_CURRENT)
    compatible = npm == OPENAI_COMPATIBLE
    moved: dict[str, Any] = {}
    for key in ("name", "family", "description", "time"):
        if key in entry:
            moved[key] = entry[key]
    if isinstance(entry.get("id"), str):
        moved["modelID"] = entry["id"]

    capabilities = dict(_as_object(entry.get("capabilities")))
    if isinstance(entry.get("tool_call"), bool):
        capabilities["tools"] = entry["tool_call"]
    modalities = _as_object(entry.get("modalities"))
    for key in ("input", "output"):
        if isinstance(modalities.get(key), list):
            capabilities[key] = modalities[key]
    if capabilities:
        moved["capabilities"] = capabilities
    if isinstance(entry.get("limit"), dict):
        moved["limit"] = {key: value for key, value in entry["limit"].items() if isinstance(value, (int, float))}
    if isinstance(entry.get("cost"), dict):
        moved["cost"] = _moved_cost(entry["cost"])

    options = dict(_as_object(entry.get("options")))
    if isinstance(entry.get("provider"), dict):
        own = entry["provider"]
        if isinstance(own.get("npm"), str) and own["npm"]:
            moved["package"] = moved_package(own["npm"])
        if isinstance(own.get("api"), str) and own["api"]:
            options["baseURL"] = own["api"]
    settings, body = _split_options(options, compatible)
    if settings:
        moved["settings"] = {**_as_object(moved.get("settings")), **settings}
    if body:
        moved["body"] = {**_as_object(moved.get("body")), **body}
    if isinstance(entry.get("headers"), dict):
        moved["headers"] = {key: value for key, value in entry["headers"].items() if isinstance(value, str)}

    # A variant was a name over its options and is now an entry carrying its own name.
    variants = entry.get("variants")
    if isinstance(variants, dict):
        moved["variants"] = [
            _moved_variant(name, _as_object(options), compatible) for name, options in variants.items()
        ]
    elif isinstance(variants, list):
        moved["variants"] = variants

    if entry.get("status") == "deprecated" or entry.get("disabled") is True:
        moved["disabled"] = True
    return moved


def moved_package(npm: str) -> str:
    """The package specifier for an npm package of the legacy map, the way opencode spells it."""
    return npm if ":" in npm or npm.startswith("@opencode/") else f"{AISDK}{npm}"


def _split_options(options: dict[str, Any], compatible: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Client settings and request body out of a model's options.

    An OpenAI-compatible server is configured by a handful of names; every other option is something
    the request body has to carry, which is how opencode reads a legacy model too.
    """
    if not compatible:
        return options, {}
    settings = {key: value for key, value in options.items() if key in COMPATIBLE_SETTINGS}
    return settings, {key: value for key, value in options.items() if key not in COMPATIBLE_SETTINGS}


def _moved_variant(name: str, options: dict[str, Any], compatible: bool) -> dict[str, Any]:
    variant: dict[str, Any] = {"id": name}
    settings, body = _split_options(options, compatible)
    if settings:
        variant["settings"] = settings
    if body:
        variant["body"] = body
    return variant


def _moved_cost(cost: dict[str, Any]) -> list[dict[str, Any]]:
    """The price of a model, and a second tier of its own when a long context costs more."""
    prices = [
        {
            "input": cost.get("input"),
            "output": cost.get("output"),
            "cache": {"read": cost.get("cache_read") or 0, "write": cost.get("cache_write") or 0},
        }
    ]
    over = cost.get("context_over_200k")
    if isinstance(over, dict):
        prices.append(
            {
                "tier": {"type": "context", "size": 200_000},
                "input": over.get("input"),
                "output": over.get("output"),
                "cache": {"read": over.get("cache_read") or 0, "write": over.get("cache_write") or 0},
            }
        )
    return prices


def _portable(entry: dict[str, Any], known: frozenset[str]) -> None:
    unknown = sorted(key for key in entry if key not in known)
    if unknown:
        raise Unmovable(unknown)


def resolve_variables(value: str) -> str:
    """Expand opencode's ``{env:NAME}`` placeholders; unknown variables become empty."""
    return re.sub(r"\{env:([^}]+)\}", lambda match: os.environ.get(match.group(1).strip(), ""), value)


def strip_jsonc(text: str) -> str:
    """Remove comments and trailing commas outside strings."""
    out: list[str] = []
    index = 0
    in_string = False
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < len(text):
                out.append(text[index + 1])
                index += 1
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            out.append(char)
        elif text.startswith("//", index):
            newline = text.find("\n", index)
            index = len(text) if newline == -1 else newline
            continue
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end == -1 else end + 2
            continue
        else:
            out.append(char)
        index += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _as_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
