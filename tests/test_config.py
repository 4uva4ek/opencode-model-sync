import json
from pathlib import Path

import pytest

from opencode_model_sync.config import ConfigError, OpencodeConfig, config_dir, config_path, strip_jsonc


def write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


LEGACY_MAC = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "Ollama MAC",
    "options": {"baseURL": "http://192.168.1.10:11434/v1", "apiKey": "ollama"},
    "models": {"qwen3.8:27b-mlx": {"name": "Qwen3.8-mlx"}},
}


def test_config_dir_prefers_opencode_variable(tmp_path):
    assert config_dir({"OPENCODE_CONFIG_DIR": str(tmp_path)}) == tmp_path
    assert config_dir({"XDG_CONFIG_HOME": str(tmp_path)}) == tmp_path / "opencode"


def test_config_path_lets_jsonc_win(tmp_path):
    assert config_path(tmp_path) == tmp_path / "opencode.json"
    (tmp_path / "opencode.json").write_text("{}")
    (tmp_path / "opencode.jsonc").write_text("{}")
    assert config_path(tmp_path) == tmp_path / "opencode.jsonc"


def test_models_go_to_the_legacy_section_that_defines_the_provider(tmp_path):
    path = write(tmp_path / "opencode.json", {"provider": {"ollama-mac": LEGACY_MAC}})
    config = OpencodeConfig.load(path)
    entry = config.model_entry("ollama-mac", None, 65536, True)
    config.add_models("ollama-mac", {"qwen3.6:latest": entry})
    config.save()

    saved = json.loads(path.read_text())
    assert "providers" not in saved
    mac = saved["provider"]["ollama-mac"]
    assert mac["options"]["baseURL"] == "http://192.168.1.10:11434/v1"
    assert mac["models"]["qwen3.6:latest"] == {"tool_call": True, "limit": {"context": 65536, "output": 32768}}
    assert mac["models"]["qwen3.8:27b-mlx"] == {"name": "Qwen3.8-mlx"}


def test_current_entry_wins_over_legacy_entry_with_same_id(tmp_path):
    path = write(
        tmp_path / "opencode.json",
        {
            "provider": {"local": LEGACY_MAC},
            "providers": {"local": {"settings": {"baseURL": "http://127.0.0.1:1234/v1"}, "models": {}}},
        },
    )
    config = OpencodeConfig.load(path)
    provider = config.provider("local")
    assert provider.section == "providers"
    assert provider.base_url == "http://127.0.0.1:1234/v1"
    assert config.model_entry("local", "M", None, False) == {"name": "M", "capabilities": {"tools": False}}


def test_existing_model_settings_are_kept(tmp_path):
    path = write(tmp_path / "opencode.json", {"provider": {"ollama-mac": LEGACY_MAC}})
    config = OpencodeConfig.load(path)
    config.add_models("ollama-mac", {"qwen3.8:27b-mlx": {"name": "overwritten?"}})
    assert config.provider("ollama-mac").models["qwen3.8:27b-mlx"] == {"name": "Qwen3.8-mlx"}


def test_remove_models(tmp_path):
    path = write(tmp_path / "opencode.json", {"provider": {"ollama-mac": LEGACY_MAC}})
    config = OpencodeConfig.load(path)
    config.remove_models("ollama-mac", ["qwen3.8:27b-mlx", "unknown"])
    assert config.provider("ollama-mac").models == {}


def test_save_backs_up_once_and_keeps_other_keys(tmp_path):
    path = write(tmp_path / "opencode.json", {"$schema": "x", "theme": "dark", "provider": {"m": LEGACY_MAC}})
    config = OpencodeConfig.load(path)
    config.remove_models("m", ["qwen3.8:27b-mlx"])
    config.save()
    config.save()
    backups = list(tmp_path.glob("opencode.json.bak-model-sync-*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["provider"]["m"]["models"]
    assert json.loads(path.read_text())["theme"] == "dark"


def test_add_provider_uses_legacy_openai_compatible_shape(tmp_path):
    config = OpencodeConfig.load(tmp_path / "opencode.json")
    config.add_provider("lmstudio", "LM Studio", "http://127.0.0.1:1234/v1/", None)
    config.save()
    saved = json.loads((tmp_path / "opencode.json").read_text())
    assert saved["provider"]["lmstudio"] == {
        "npm": "@ai-sdk/openai-compatible",
        "name": "LM Studio",
        "options": {"baseURL": "http://127.0.0.1:1234/v1"},
        "models": {},
    }
    with pytest.raises(ConfigError):
        config.add_provider("lmstudio", "again", "http://x", None)
    with pytest.raises(ConfigError):
        config.add_provider("bad id", "x", "http://x", None)


def test_jsonc_is_read_but_not_overwritten(tmp_path):
    path = tmp_path / "opencode.jsonc"
    path.write_text('{\n  // keep me\n  "provider": {"m": {"options": {"baseURL": "http://a//b"},},},\n}\n')
    config = OpencodeConfig.load(path)
    assert config.has_comments
    assert config.provider("m").base_url == "http://a//b"
    with pytest.raises(ConfigError):
        config.save()


def test_strip_jsonc_keeps_slashes_inside_strings():
    assert json.loads(strip_jsonc('{"u": "http://x/*y*/", /* c */ "a": [1,],}')) == {"u": "http://x/*y*/", "a": [1]}


def test_env_placeholders_are_resolved(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret")
    path = write(
        tmp_path / "opencode.json",
        {"provider": {"m": {"options": {"baseURL": "http://h/v1", "apiKey": "{env:MY_KEY}"}}}},
    )
    assert OpencodeConfig.load(path).provider("m").api_key == "secret"


def test_set_model_tools_uses_the_section_shape(tmp_path):
    path = write(
        tmp_path / "opencode.json",
        {
            "provider": {"old": LEGACY_MAC},
            "providers": {"new": {"settings": {"baseURL": "http://h/v1"}, "models": {"m": {"name": "M"}}}},
        },
    )
    config = OpencodeConfig.load(path)
    config.set_model_tools("old", "qwen3.8:27b-mlx", False)
    config.set_model_tools("new", "m", False)
    assert config.provider("old").models["qwen3.8:27b-mlx"] == {"name": "Qwen3.8-mlx", "tool_call": False}
    assert config.provider("new").models["m"] == {"name": "M", "capabilities": {"tools": False}}
    with pytest.raises(ConfigError):
        config.set_model_tools("old", "unknown", True)


def test_configured_tools_reads_both_shapes():
    from opencode_model_sync.config import configured_tools

    assert configured_tools({"tool_call": False}) is False
    assert configured_tools({"capabilities": {"tools": True}}) is True
    assert configured_tools({"name": "x"}) is None


@pytest.mark.parametrize("section", ["provider", "providers"])
def test_rename_provider_preserves_settings_and_id(tmp_path, section):
    path = write(tmp_path / "opencode.json", {section: {"local": LEGACY_MAC}, "model": "local/m"})
    config = OpencodeConfig.load(path)
    config.rename_provider("local", "  New name  ")
    config.save()
    saved = json.loads(path.read_text())
    assert saved[section]["local"] == {**LEGACY_MAC, "name": "New name"}
    assert saved["model"] == "local/m"
    assert json.loads(next(tmp_path.glob("*.bak-*")).read_text())[section]["local"] == LEGACY_MAC
    with pytest.raises(ConfigError):
        config.rename_provider("local", "  ")
    with pytest.raises(ConfigError):
        config.rename_provider("missing", "New name")


@pytest.mark.parametrize("sections", [("provider",), ("providers",), ("provider", "providers")])
def test_remove_provider_clears_shadowed_entries_and_references(tmp_path, sections):
    data = {section: {"local": LEGACY_MAC, "other": LEGACY_MAC} for section in sections}
    data.update({"model": "local/m", "small_model": "other/m",
                 "agent": {"build": {"model": "local/m", "prompt": "keep"},
                           "review": {"model": "local-other/m"}},
                 "mode": {"plan": {"model": "local/m"}},
                 "enabled_providers": ["local", "other"], "disabled_providers": ["else"],
                 "theme": "dark"})
    path = write(tmp_path / "opencode.json", data)
    config = OpencodeConfig.load(path)
    config.remove_provider("local")
    config.save()
    saved = OpencodeConfig.load(path)
    assert saved.provider("local") is None
    for section in sections:
        assert saved.data[section] == {"other": LEGACY_MAC}
    assert "model" not in saved.data
    assert saved.data["small_model"] == "other/m"
    assert saved.data["agent"] == {"build": {"prompt": "keep"}, "review": {"model": "local-other/m"}}
    assert saved.data["mode"] == {"plan": {}}
    assert saved.data["enabled_providers"] == ["other"]
    assert saved.data["disabled_providers"] == ["else"]
    assert saved.data["theme"] == "dark"
    assert json.loads(next(tmp_path.glob("*.bak-*")).read_text()) == data
    with pytest.raises(ConfigError):
        saved.remove_provider("local")


@pytest.mark.parametrize("operation", ["rename", "remove"])
def test_provider_edits_do_not_overwrite_jsonc(tmp_path, operation):
    path = tmp_path / "opencode.jsonc"
    original = '{/* keep */ "provider": {"local": {"name": "Local"}}}'
    path.write_text(original)
    config = OpencodeConfig.load(path)
    if operation == "rename":
        config.rename_provider("local", "New name")
    else:
        config.remove_provider("local")
    with pytest.raises(ConfigError):
        config.save()
    assert path.read_text() == original
