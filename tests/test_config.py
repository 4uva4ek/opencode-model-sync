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
