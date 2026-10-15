"""Reading and writing the global opencode config.

opencode reads ``opencode.json`` and ``opencode.jsonc`` from its config directory and lets the later
name win. Providers live in two maps: the legacy ``provider`` map (``npm`` + ``options``) and the
current ``providers`` map (``package`` + ``settings``). When one ID appears in both, opencode replaces
the legacy entry with the current one wholesale, so every edit here goes to the entry opencode uses.
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

CONFIG_NAMES = ("opencode.json", "opencode.jsonc")
LEGACY = "provider"
CURRENT = "providers"
OPENAI_COMPATIBLE = "@ai-sdk/openai-compatible"


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
            raise ConfigError(f"{path} is not valid JSON: {error}") from error

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

    def add_provider(self, provider_id: str, name: str, base_url: str, api_key: str | None) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", provider_id):
            raise ConfigError("Provider ID may contain only letters, digits, '.', '_' and '-'")
        if self.provider(provider_id):
            raise ConfigError(f"Provider '{provider_id}' already exists")
        # The legacy shape is what opencode's own docs show for custom OpenAI-compatible providers.
        options: dict[str, Any] = {"baseURL": base_url.rstrip("/")}
        if api_key:
            options["apiKey"] = api_key
        self.data.setdefault(LEGACY, {})[provider_id] = {
            "npm": OPENAI_COMPATIBLE,
            "name": name or provider_id,
            "options": options,
            "models": {},
        }

    def save(self) -> None:
        if self.has_comments:
            raise ConfigError(f"{self.path.name} has comments, which would be lost on save; edit it by hand instead")
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
            raise ConfigError(f"Provider '{provider_id}' is not in the config")
        return provider.section

    def _entry(self, provider_id: str) -> dict[str, Any]:
        return self.data[self._section(provider_id)][provider_id]


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
