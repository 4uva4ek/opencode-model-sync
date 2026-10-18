import json
from pathlib import Path

import pytest

from opencode_model_sync import agents, i18n
from opencode_model_sync.agents import Agent, Worker
from opencode_model_sync.config import ConfigError, OpencodeConfig


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")


def load(tmp_path: Path, data: dict) -> OpencodeConfig:
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return OpencodeConfig.load(path)


def saved(config: OpencodeConfig) -> dict:
    config.save()
    return json.loads(config.path.read_text(encoding="utf-8"))


def test_reads_both_sections_and_current_wins(tmp_path):
    config = load(
        tmp_path,
        {
            "agent": {
                "coder": {"mode": "subagent", "model": "lmstudio/q", "description": "d", "tools": {"bash": False}},
                "same": {"mode": "primary", "prompt": "old"},
            },
            "agents": {"same": {"mode": "subagent", "system": "new", "model": {"providerID": "p", "model": "m", "variant": "high"}}},
        },
    )
    by_name = {item.name: item for item in agents.agents(config)}
    assert by_name["coder"].access["bash"] == "deny"
    assert by_name["same"].section == "agents"
    assert by_name["same"].prompt == "new"
    assert by_name["same"].model == "p/m#high"
    assert not by_name["same"].editable_access


def test_team_writes_planner_and_restricted_subagents(tmp_path):
    config = load(tmp_path, {"$schema": "x", "theme": "dark"})
    members = agents.team(
        "planner",
        "anthropic/claude-opus-5-5",
        [Worker("coder", "coder", "opencode/glm-5.3-flash-free"), Worker("tester", "tester", None)],
        delegate_only=True,
    )
    agents.save_team(config, members, make_default=True)
    data = saved(config)

    assert data["theme"] == "dark"
    assert data["default_agent"] == "planner"
    planner = data["agent"]["planner"]
    assert planner["mode"] == "primary"
    assert planner["model"] == "anthropic/claude-opus-5-5"
    assert planner["permission"] == {"edit": "deny", "bash": "deny", "task": {"*": "deny", "coder": "allow", "tester": "allow"}}
    assert "- coder: " in planner["prompt"] and "- tester: " in planner["prompt"]
    assert data["agent"]["coder"] == {
        "description": i18n.tr("role.coder.description"),
        "mode": "subagent",
        "model": "opencode/glm-5.3-flash-free",
        "prompt": i18n.tr("role.coder.prompt"),
    }
    assert data["agent"]["tester"]["permission"] == {"edit": "deny"}
    assert "model" not in data["agent"]["tester"]


def test_team_keeps_settings_it_does_not_manage(tmp_path):
    config = load(tmp_path, {"agent": {"coder": {"mode": "subagent", "color": "#112233", "steps": 7}}})
    agents.save_team(config, agents.team("lead", None, [Worker("coder", "coder", "a/b")], True), make_default=False)
    coder = saved(config)["agent"]["coder"]
    assert coder["color"] == "#112233" and coder["steps"] == 7 and coder["model"] == "a/b"


def test_save_agent_replaces_old_tool_switches_and_keeps_pattern_rules(tmp_path):
    config = load(
        tmp_path,
        {
            "agent": {
                "x": {
                    "mode": "all",
                    "tools": {"write": False, "bash": False, "mymcp_*": False},
                    "permission": {"bash": {"*": "ask", "git status": "allow"}},
                }
            }
        },
    )
    item = agents.agent(config, "x")
    assert item.access == {"edit": "deny", "bash": "custom", "webfetch": None}
    item.access["edit"] = "allow"
    item.description = "desc"
    agents.save_agent(config, item, "x")
    entry = saved(config)["agent"]["x"]
    assert entry["tools"] == {"mymcp_*": False}
    assert entry["permission"] == {"bash": {"*": "ask", "git status": "allow"}, "edit": "allow"}


def test_rename_updates_delegation_and_default(tmp_path):
    config = load(
        tmp_path,
        {
            "default_agent": "coder",
            "agent": {
                "lead": {"mode": "primary", "permission": {"task": {"*": "deny", "coder": "allow"}}},
                "coder": {"mode": "subagent", "description": "d"},
            },
        },
    )
    item = agents.agent(config, "coder")
    item.name = "dev"
    agents.save_agent(config, item, "coder")
    data = saved(config)
    assert "coder" not in data["agent"] and "dev" in data["agent"]
    assert data["agent"]["lead"]["permission"]["task"] == {"*": "deny", "dev": "allow"}
    assert data["default_agent"] == "dev"


def test_remove_agent_cleans_references(tmp_path):
    config = load(
        tmp_path,
        {
            "default_agent": "lead",
            "agent": {
                "lead": {"mode": "primary", "permission": {"task": {"*": "deny", "coder": "allow"}}},
                "coder": {"mode": "subagent"},
            },
        },
    )
    agents.remove_agent(config, "coder")
    assert saved(config)["agent"]["lead"]["permission"]["task"] == {"*": "deny"}
    agents.remove_agent(config, "lead")
    assert "default_agent" not in saved(config)


def test_task_patterns_are_not_rewritten(tmp_path):
    config = load(tmp_path, {"agent": {"lead": {"mode": "primary", "permission": {"task": {"*": "ask", "review-*": "allow"}}}}})
    item = agents.agent(config, "lead")
    assert item.custom_task and item.delegates is None
    item.delegates = ["general"]
    agents.save_agent(config, item, "lead")
    assert saved(config)["agent"]["lead"]["permission"]["task"] == {"*": "ask", "review-*": "allow"}


def test_current_section_agent_keeps_its_rules(tmp_path):
    rules = [{"action": "edit", "resource": "*", "effect": "deny"}]
    config = load(tmp_path, {"agents": {"x": {"mode": "subagent", "permissions": rules, "system": "s"}}})
    item = agents.agent(config, "x")
    item.model = "opencode/big-pickle"
    item.prompt = "new"
    agents.save_agent(config, item, "x")
    entry = saved(config)["agents"]["x"]
    assert entry == {"mode": "subagent", "permissions": rules, "system": "new", "model": "opencode/big-pickle"}


def test_names_are_validated(tmp_path):
    config = load(tmp_path, {"agent": {"a": {}}})
    with pytest.raises(ConfigError):
        agents.save_agent(config, Agent(name="bad name"))
    with pytest.raises(ConfigError):
        agents.save_agent(config, Agent(name="a"))
    with pytest.raises(ConfigError):
        agents.save_team(config, [Agent(name="b"), Agent(name="b")], make_default=False)


def test_subagent_names_include_built_ins(tmp_path):
    config = load(tmp_path, {"agent": {"lead": {"mode": "primary"}, "coder": {"mode": "subagent"}, "off": {"mode": "subagent", "disable": True}}})
    assert agents.subagent_names(config) == ["coder", "explore", "general"]
