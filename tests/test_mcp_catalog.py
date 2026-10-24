"""Catalog contracts and a real Qt add/save workflow, without user config or network."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from opencode_model_sync import i18n, mcp_catalog as catalog, settings
from opencode_model_sync.config import strip_jsonc
from opencode_model_sync.mcp_catalog_view import CatalogDialog, SetupDialog, TEXT
from opencode_model_sync.settings_view import SettingsPanel


@pytest.fixture
def app():
    result = QApplication.instance() or QApplication([])
    i18n.set_language("en")
    return result


def test_starter_recipes_match_current_config_schema():
    for entry in catalog.starter():
        for recipe in entry.recipes:
            result = catalog.prepare_config(recipe.config)
            assert result["disabled"] is False
            assert "disabled" not in recipe.config


def test_registry_filters_and_preserves_auth_package_arguments():
    server = {"name": "io.test/server", "version": "1.2.3", "remotes": [
        {"type": "streamable-http", "url": "https://example.org/mcp", "headers": [{"name": "Authorization", "value": "Bearer {env:TEST_TOKEN}"}]}],
        "packages": [{"registryType": "npm", "identifier": "@test/mcp", "version": "1.2.3", "transport": {"type": "stdio"},
                      "packageArguments": [{"type": "named", "name": "--mode", "value": "read"}],
                      "environmentVariables": [{"name": "TEST_TOKEN", "isRequired": True}]}]}
    data = {"servers": [{"server": server}, {"server": server}, {"server": {"name": "old"}, "_meta": {"io.modelcontextprotocol.registry/official": {"isLatest": False}}}],
            "metadata": {"nextCursor": "opaque:+/value"}}
    page = catalog.parse_registry(data)
    assert len(page.entries) == 1
    assert page.cursor == "opaque:+/value"
    remote, package = page.entries[0].recipes
    assert remote.config["headers"]["Authorization"] == "Bearer {env:TEST_TOKEN}"
    assert remote.config["oauth"] is False
    assert package.config["command"] == ["npx", "-y", "@test/mcp@1.2.3", "--mode", "read"]
    assert package.config["environment"] == {"TEST_TOKEN": "{env:TEST_TOKEN}"}
    for recipe in page.entries[0].recipes:
        catalog.prepare_config(recipe.config)


def test_do_not_guess_required_arguments_or_unsafe_links():
    data = {"packages": [{"registryType": "npm", "identifier": "test", "packageArguments": [{"type": "positional", "isRequired": True}]}],
            "remotes": [{"type": "streamable-http", "url": "file:///secret"}]}
    assert catalog.registry_recipes(data) == []
    with pytest.raises(catalog.CatalogError, match="placeholders"):
        catalog.prepare_config({"type": "remote", "url": "https://example.org/{workspace}"})
    with pytest.raises(catalog.CatalogError, match="invalid_command"):
        catalog.prepare_config({"type": "local", "command": []})


def test_glama_no_guessed_auth_and_preserves_attribution():
    row = {"id": "one", "name": "One", "url": "https://glama.ai/mcp/connectors/test/one", "isBoosted": True,
           "connection": {"url": "https://example.org/mcp", "transport": "streamable_http", "authType": "oauth2"}}
    page = catalog.parse_glama({"connectors": [row], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}, True)
    assert page.cursor == "next"
    entry = page.entries[0]
    assert entry.url == row["url"] and entry.promoted
    assert entry.recipes[0].config["oauth"] == {}
    row["connection"]["authType"] = "api_key"
    assert catalog.parse_glama({"connectors": [row]}, True).entries[0].recipes == []
    with pytest.raises(catalog.CatalogError, match="glama_key"):
        catalog.fetch("glama")


def test_request_pagination_and_search_are_encoded(monkeypatch):
    requests = []
    def fetch(url, token=""):
        requests.append((url, token))
        return {"servers": [], "metadata": {}}
    monkeypatch.setattr(catalog, "request_json", fetch)
    catalog.fetch("registry", "a & b", "opaque+/cursor")
    assert "version=latest" in requests[0][0]
    assert "search=a+%26+b" in requests[0][0]
    assert "cursor=opaque%2B%2Fcursor" in requests[0][0]
    assert not requests[0][1]


def test_setup_rejects_duplicate_and_only_applies_on_accept(app):
    entry = catalog.starter()[0]
    dialog = SetupDialog(entry, entry.recipes[0], {"context7"})
    dialog._accept()
    assert dialog.result_config is None
    assert "already exists" in dialog.error.text()
    dialog.name.setText("docs")
    dialog.enabled.setChecked(False)
    dialog._accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_config == {"type": "remote", "url": "https://mcp.context7.com/mcp", "disabled": True}


def test_catalog_add_save_preserves_comments_and_other_settings(app, tmp_path, monkeypatch):
    from opencode_model_sync import mcp_catalog_view
    path = tmp_path / "opencode.jsonc"
    path.write_text('{\n// keep\n"agents":{"coder":{"model":"local/a"}}, "mcp":{"servers":{"existing":{"type":"remote","url":"https://old.example/mcp"}}}\n}')
    panel = SettingsPanel(path, mcp=True)
    before = path.read_text()
    class Accepted:
        result_name = "context7"
        result_config = catalog.prepare_config(catalog.starter()[0].recipes[0].config)
        def __init__(self, installed, parent): assert "existing" in installed
        def exec(self): return QDialog.DialogCode.Accepted
    monkeypatch.setattr(mcp_catalog_view, "CatalogDialog", Accepted)
    panel.browse_catalog()
    assert panel.dirty and not panel.errors
    assert path.read_text() == before
    panel.save()
    result = json.loads(strip_jsonc(path.read_text()))
    assert result["agents"] == {"coder": {"model": "local/a"}}
    assert set(result["mcp"]["servers"]) == {"existing", "context7"}
    assert "// keep" in path.read_text()
    assert next(tmp_path.glob("*.bak-model-sync-*")).read_text() == before


def test_async_stale_response_does_not_replace_current_source(app, monkeypatch):
    from opencode_model_sync import mcp_catalog_view
    pending = []
    monkeypatch.setattr(mcp_catalog_view.tasks, "run", lambda work, done, failed: pending.append((done, failed)))
    dialog = CatalogDialog({})
    dialog.source.setCurrentIndex(1)
    assert len(pending) == 1
    dialog.source.setCurrentIndex(0)
    pending[0][0](catalog.Page([catalog.Entry("stale", "Stale", "", "registry", "https://example.org")]))
    assert all(e.id != "stale" for e in dialog.entries)
    assert dialog.listing.count() == len(catalog.starter())
    assert all(len(pair) == 2 and all(pair) for pair in TEXT.values())
