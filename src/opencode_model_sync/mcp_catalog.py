"""Read public MCP catalog metadata. Browsing never runs a server or changes OpenCode."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse


SOURCES = {
    "starter": "https://opencode.ai/docs/mcp-servers/#examples",
    "registry": "https://registry.modelcontextprotocol.io/",
    "glama": "https://glama.ai/mcp/servers",
    "glama_remote": "https://glama.ai/mcp/connectors",
}
MAX_BYTES = 8 * 1024 * 1024


@dataclass
class Recipe:
    label: str
    config: dict
    note: str = ""


@dataclass
class Entry:
    id: str
    name: str
    description: str
    source: str
    url: str
    repository: str = ""
    recipes: list[Recipe] = field(default_factory=list)
    promoted: bool = False


@dataclass
class Page:
    entries: list[Entry]
    cursor: str = ""


class CatalogError(ValueError):
    pass


def web_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlparse(value)
        return value if parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def server_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-.")[:100] or "mcp-server"


def starter() -> list[Entry]:
    docs = SOURCES["starter"]
    return [
        Entry("context7", "Context7", "Library documentation and code examples / Документация библиотек и примеры кода", "starter", docs.replace("#examples", "#context7"),
              "https://github.com/upstash/context7", [Recipe("HTTPS", {"type": "remote", "url": "https://mcp.context7.com/mcp"})]),
        Entry("sentry", "Sentry", "Application errors and issues / Ошибки приложений и задачи", "starter", docs.replace("#examples", "#sentry"),
              "https://github.com/getsentry/sentry-mcp", [Recipe("HTTPS · OAuth", {"type": "remote", "url": "https://mcp.sentry.dev/mcp", "oauth": {}}, "OAuth")]),
        Entry("gh-grep", "Grep by Vercel", "Find public code examples / Поиск примеров в открытом коде", "starter", docs.replace("#examples", "#grep-by-vercel"),
              "https://grep.app", [Recipe("HTTPS", {"type": "remote", "url": "https://mcp.grep.app"})]),
        Entry("playwright", "Playwright", "Browser automation / Управление браузером", "starter", "https://github.com/microsoft/playwright-mcp",
              "https://github.com/microsoft/playwright-mcp", [Recipe("npm · Node.js", {"type": "local", "command": ["npx", "-y", "@playwright/mcp@latest"]}, "Node.js")]),
        Entry("github", "GitHub", "Repositories, issues and pull requests / Репозитории, задачи и pull requests", "starter", "https://github.com/github/github-mcp-server",
              "https://github.com/github/github-mcp-server", [Recipe("HTTPS · token", {"type": "remote", "url": "https://api.githubcopilot.com/mcp/", "oauth": False,
                  "headers": {"Authorization": "Bearer {env:GITHUB_TOKEN}"}}, "GITHUB_TOKEN")]),
    ]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Catalog credentials must never follow a redirect to another host.
        return None


def request_json(url: str, token: str = "") -> dict:
    headers = {"Accept": "application/json", "User-Agent": "OpenCode-Companion/0.4"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(url, headers=headers), timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise CatalogError("response_size")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise CatalogError("response_format")
        return result
    except urllib.error.HTTPError as error:
        raise CatalogError(f"HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CatalogError("network") from None
    except CatalogError:
        raise
    except (ValueError, UnicodeError):
        raise CatalogError("response_format") from None


def _mapping(items: list) -> dict:
    result = {}
    for item in items:
        name = item.get("name", "")
        if not name:
            continue
        value = item.get("value") or item.get("default")
        if not value:
            if not item.get("isRequired", True):
                continue
            # References are intentionally left visible for the setup dialog.
            value = "{env:" + re.sub(r"\W+", "_", name).upper() + "}"
        result[name] = str(value)
    return result


def _arguments(items: list) -> list[str]:
    result = []
    for item in items:
        if item.get("isRepeated") or item.get("variables"):
            raise ValueError("manual arguments")
        value = item.get("value", item.get("default"))
        if value is None:
            if not item.get("isRequired", False):
                continue
            raise ValueError("required argument")
        if item.get("type") == "named":
            if not item.get("name"):
                raise ValueError("argument name")
            result.append(item["name"])
        if str(value):
            result.append(str(value))
    return result


def registry_recipes(server: dict) -> list[Recipe]:
    recipes = []
    for remote in server.get("remotes", []):
        if remote.get("type") not in ("streamable-http", "sse") or not web_url(remote.get("url")):
            continue
        config = {"type": "remote", "url": remote["url"]}
        headers = _mapping(remote.get("headers", []))
        if headers:
            config.update(headers=headers, oauth=False)
        recipes.append(Recipe(remote["url"], config))
    for package in server.get("packages", []):
        kind, name = package.get("registryType"), package.get("identifier", "")
        if not name or name.startswith("-") or package.get("transport", {}).get("type", "stdio") != "stdio":
            continue
        registry = package.get("registryBaseUrl", "").rstrip("/")
        expected = {"npm": "https://registry.npmjs.org", "pypi": "https://pypi.org"}
        if registry and kind in expected and registry != expected[kind]:
            continue
        # Unknown registries/argument forms require the publisher's instructions.
        try:
            before = _arguments(package.get("runtimeArguments", []))
            after = _arguments(package.get("packageArguments", []))
        except ValueError:
            continue
        version = package.get("version", "")
        pinned = version and version != "latest"
        env = _mapping(package.get("environmentVariables", []))
        if kind == "npm":
            command = ["npx", "-y", *before, name + ("@" + version if pinned else ""), *after]
        elif kind == "pypi":
            command = ["uvx", *before, name + ("==" + version if pinned else ""), *after]
        elif kind == "oci":
            # OCI identifiers already contain their publisher-provided tag/digest.
            command = ["docker", "run", "--rm", "-i", *before]
            for key in env:
                command.extend(["-e", key])
            command.extend([name, *after])
        else:
            continue
        config = {"type": "local", "command": command}
        if env:
            config["environment"] = env
        recipes.append(Recipe(f"{kind}: {name}", config, {"npm": "Node.js", "pypi": "uv", "oci": "Docker"}[kind]))
    return recipes


def parse_registry(data: dict) -> Page:
    if not isinstance(data.get("servers"), list):
        raise CatalogError("response_format")
    entries = []
    seen = set()
    for row in data["servers"]:
        server = row.get("server", {})
        name = server.get("name")
        meta = row.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
        if not name or name in seen or meta.get("status", "active") != "active" or meta.get("isLatest") is False:
            continue
        seen.add(name)
        url = SOURCES["registry"] + "?" + urlencode({"q": name})
        entries.append(Entry(name, server.get("title") or name, server.get("description", ""), "registry", url,
                             web_url((server.get("repository") or {}).get("url")), registry_recipes(server)))
    return Page(entries, data.get("metadata", {}).get("nextCursor") or "")


def parse_glama(data: dict, remote: bool) -> Page:
    key = "connectors" if remote else "servers"
    if not isinstance(data.get(key), list):
        raise CatalogError("response_format")
    entries = []
    for row in data[key]:
        if row.get("deprecatedAt"):
            continue
        recipes = []
        connection = row.get("connection") or {}
        url = web_url(connection.get("url"))
        if url and connection.get("transport") == "streamable_http":
            config = {"type": "remote", "url": url}
            auth = connection.get("authType", "none")
            if auth == "none":
                config["oauth"] = False
            elif auth == "oauth2":
                config["oauth"] = {}
            # The API does not specify API-key/basic header formats. Require setup.
            if auth in ("none", "oauth2"):
                recipes.append(Recipe("HTTPS" + (" · OAuth" if auth == "oauth2" else ""), config, "OAuth" if auth == "oauth2" else ""))
        repo = web_url((row.get("repository") or {}).get("url"))
        if not recipes:
            # Only known, publisher-documented recipes; never infer an executable from a repo name.
            recipes = next((deepcopy(e.recipes) for e in starter() if repo and e.repository.rstrip("/") == repo.rstrip("/")), [])
        listing = web_url(row.get("url"))
        if not listing or urlparse(listing).hostname != "glama.ai":
            continue
        entries.append(Entry(str(row.get("id") or row.get("slug")), row.get("name") or row.get("slug", "MCP"),
                             row.get("description") or "", "glama_remote" if remote else "glama", listing,
                             repo, recipes, bool(row.get("isBoosted"))))
    info = data.get("pageInfo") or {}
    return Page(entries, (info.get("endCursor") or "") if info.get("hasNextPage") else "")


def fetch(source: str, query: str = "", cursor: str = "", token: str = "") -> Page:
    if source == "starter":
        words = query.casefold().split()
        return Page([e for e in starter() if all(w in f"{e.name} {e.description}".casefold() for w in words)])
    if source == "registry":
        params = {"limit": 30, "version": "latest"}
        if query: params["search"] = query
        if cursor: params["cursor"] = cursor
        return parse_registry(request_json("https://registry.modelcontextprotocol.io/v0.1/servers?" + urlencode(params)))
    if source in ("glama", "glama_remote"):
        if not token:
            raise CatalogError("glama_key")
        remote = source == "glama_remote"
        params = {"first": 30, "sort": "search-relevance:desc"}
        if query: params["query"] = query
        if cursor: params["after"] = cursor
        endpoint = "connectors" if remote else "servers"
        return parse_glama(request_json(f"https://glama.ai/api/mcp/v1/{endpoint}?" + urlencode(params), token), remote)
    raise CatalogError("source")


def prepare_config(config: dict, *, enabled=True) -> dict:
    """Validate against the same installed-version schema as the existing MCP editor."""
    from . import settings
    result = deepcopy(config)
    result.pop("enabled", None)
    result["disabled"] = not enabled
    info = settings.schema()["properties"]["mcp"]["properties"]["servers"]["additionalProperties"]
    if settings.validation_errors(result, info):
        raise CatalogError("invalid_config")
    if result["type"] == "remote" and not web_url(result["url"]):
        raise CatalogError("invalid_url")
    if result["type"] == "local" and (not result["command"] or not result["command"][0].strip()):
        raise CatalogError("invalid_command")
    # Unresolved registry templates are not OpenCode variables.
    text = json.dumps(result)
    if re.search(r"\{(?!env:|file:)[a-zA-Z_][\w.-]*\}", text):
        raise CatalogError("placeholders")
    return result
