"""Agents in the opencode config, and building a team of one planner and several workers.

opencode keeps agents in two maps, like providers. The legacy ``agent`` map has ``prompt``, ``disable``,
``temperature`` and a ``permission`` object with ``edit``, ``bash``, ``webfetch`` and ``task`` keys. The
current ``agents`` map has ``system``, ``disabled`` and an ordered ``permissions`` rule list. New agents
go to the legacy map, whose shape the opencode docs describe. An agent already in the current map is
edited there, but its rule list is kept as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .config import ConfigError, OpencodeConfig
from .i18n import tr

LEGACY = "agent"
CURRENT = "agents"
BUILT_IN = ("build", "plan", "general", "explore")
BUILT_IN_SUBAGENTS = ("general", "explore")
MODES = ("primary", "subagent", "all")
ACCESS = ("allow", "ask", "deny")
CUSTOM = "custom"  # a permission written as pattern rules, kept untouched
PERMISSIONS = ("edit", "bash", "webfetch")
ROLES = ("coder", "tester", "reviewer", "researcher", "custom")
# Edit and bash access per role; None leaves opencode's default.
ROLE_ACCESS = {
    "coder": (None, None),
    "tester": ("deny", None),
    "reviewer": ("deny", "deny"),
    "researcher": ("deny", "deny"),
    "custom": (None, None),
}
# Tool switches of the deprecated ``tools`` map that the edit and bash permissions replace.
_OLD_TOOLS = {"write": "edit", "edit": "edit", "patch": "edit", "bash": "bash", "webfetch": "webfetch"}


@dataclass
class Agent:
    name: str
    mode: str = "all"
    model: str | None = None
    description: str = ""
    prompt: str = ""
    disabled: bool = False
    temperature: float | None = None
    # "allow", "ask", "deny", CUSTOM, or None for opencode's default.
    access: dict[str, str | None] = field(default_factory=lambda: dict.fromkeys(PERMISSIONS))
    # Subagents this agent may hand work to; None means any.
    delegates: list[str] | None = None
    custom_task: bool = False
    section: str = LEGACY
    editable_access: bool = True

    @property
    def can_delegate(self) -> bool:
        return self.mode != "subagent"


@dataclass
class Worker:
    role: str
    name: str
    model: str | None = None


def valid_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name))


def agents(config: OpencodeConfig) -> list[Agent]:
    current = _as_object(config.data.get(CURRENT))
    legacy = _as_object(config.data.get(LEGACY))
    result = [_current(name, entry) for name, entry in current.items() if isinstance(entry, dict)]
    result += [
        _legacy(name, entry) for name, entry in legacy.items() if isinstance(entry, dict) and name not in current
    ]
    order = {"primary": 0, "all": 1, "subagent": 2}
    return sorted(result, key=lambda agent: (order.get(agent.mode, 1), agent.name.lower()))


def agent(config: OpencodeConfig, name: str) -> Agent | None:
    return next((item for item in agents(config) if item.name == name), None)


def subagent_names(config: OpencodeConfig) -> list[str]:
    """Agents another agent can hand work to: the configured ones plus opencode's built-in subagents."""
    names = [item.name for item in agents(config) if item.mode != "primary" and not item.disabled]
    return sorted(set(names) | set(BUILT_IN_SUBAGENTS), key=str.lower)


def save_agent(config: OpencodeConfig, item: Agent, previous: str | None = None) -> None:
    """Write an agent; ``previous`` is its name before the edit, for renames."""
    if not valid_name(item.name):
        raise ConfigError(tr("error.badAgentName"))
    if item.name != previous and agent(config, item.name):
        raise ConfigError(tr("error.agentExists", name=item.name))
    old = agent(config, previous) if previous else None
    section = old.section if old else LEGACY
    entries = config.data.setdefault(section, {})
    entry = dict(entries.pop(previous, {})) if old else {}

    _set(entry, "description", item.description.strip() or None)
    _set(entry, "mode", item.mode)
    _set(entry, "model", (item.model or "").strip() or None)
    if section == LEGACY:
        _set(entry, "prompt", item.prompt.strip() or None)
        _set(entry, "disable", True if item.disabled else None)
        _set(entry, "temperature", item.temperature)
        if item.editable_access:
            _write_permission(entry, item)
    else:
        _set(entry, "system", item.prompt.strip() or None)
        _set(entry, "disabled", True if item.disabled else None)
    entries[item.name] = entry
    if previous and previous != item.name:
        _rename_references(config, previous, item.name)


def remove_agent(config: OpencodeConfig, name: str) -> None:
    for section in (CURRENT, LEGACY):
        _as_object(config.data.get(section)).pop(name, None)
    _rename_references(config, name, None)


def team(planner: str, planner_model: str | None, workers: list[Worker], delegate_only: bool) -> list[Agent]:
    """A primary planner that may only hand work to the listed workers, and the workers as subagents."""
    members = []
    for worker in workers:
        edit, bash = ROLE_ACCESS[worker.role]
        members.append(
            Agent(
                name=worker.name,
                mode="subagent",
                model=worker.model or None,
                description=tr(f"role.{worker.role}.description"),
                prompt=tr(f"role.{worker.role}.prompt"),
                access={"edit": edit, "bash": bash, "webfetch": None},
            )
        )
    roster = "\n".join(f"- {member.name}: {member.description}" for member in members)
    lead = Agent(
        name=planner,
        mode="primary",
        model=planner_model or None,
        description=tr("team.plannerDescription"),
        prompt=tr("team.plannerPrompt" if delegate_only else "team.plannerPromptHands", workers=roster),
        access={"edit": "deny", "bash": "deny", "webfetch": None} if delegate_only else dict.fromkeys(PERMISSIONS),
        delegates=[member.name for member in members],
    )
    return [lead, *members]


def save_team(config: OpencodeConfig, members: list[Agent], make_default: bool) -> None:
    """Create or overwrite the team's agents; settings this app does not manage are kept."""
    names = [member.name for member in members]
    if len(set(names)) != len(names):
        raise ConfigError(tr("error.teamDuplicate"))
    for member in members:
        existing = agent(config, member.name)
        if existing:
            member.section = existing.section
            member.editable_access = existing.editable_access
        save_agent(config, member, member.name if existing else None)
    if make_default:
        config.data["default_agent"] = members[0].name


def default_agent(config: OpencodeConfig) -> str | None:
    value = config.data.get("default_agent")
    return value if isinstance(value, str) else None


def _legacy(name: str, entry: dict[str, Any]) -> Agent:
    permission = entry.get("permission")
    editable = permission is None or isinstance(permission, dict)
    permission = _as_object(permission)
    access: dict[str, str | None] = {}
    tools = _as_object(entry.get("tools"))
    for key in PERMISSIONS:
        value = permission.get(key)
        if isinstance(value, str) and value in ACCESS:
            access[key] = value
        elif value is not None:
            access[key] = CUSTOM
        elif any(tools.get(tool) is False for tool, target in _OLD_TOOLS.items() if target == key):
            access[key] = "deny"
        else:
            access[key] = None
    delegates, custom_task = _read_task(permission.get("task"))
    temperature = entry.get("temperature")
    return Agent(
        name=name,
        mode=_mode(entry),
        model=_model(entry.get("model")),
        description=str(entry.get("description") or ""),
        prompt=str(entry.get("prompt") or ""),
        disabled=entry.get("disable") is True,
        temperature=float(temperature) if isinstance(temperature, (int, float)) else None,
        access=access,
        delegates=delegates,
        custom_task=custom_task,
        section=LEGACY,
        editable_access=editable,
    )


def _current(name: str, entry: dict[str, Any]) -> Agent:
    return Agent(
        name=name,
        mode=_mode(entry),
        model=_model(entry.get("model")),
        description=str(entry.get("description") or ""),
        prompt=str(entry.get("system") or ""),
        disabled=entry.get("disabled") is True,
        access=dict.fromkeys(PERMISSIONS, CUSTOM if entry.get("permissions") else None),
        custom_task=bool(entry.get("permissions")),
        section=CURRENT,
        editable_access=False,
    )


def _mode(entry: dict[str, Any]) -> str:
    mode = entry.get("mode")
    return mode if mode in MODES else "all"


def _model(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict) and value.get("providerID") and value.get("model"):
        variant = f"#{value['variant']}" if value.get("variant") else ""
        return f"{value['providerID']}/{value['model']}{variant}"
    return None


def _read_task(value: Any) -> tuple[list[str] | None, bool]:
    """A task permission this app can show as a list of allowed subagents, or a flag that it cannot."""
    if value is None:
        return None, False
    if not isinstance(value, dict) or value.get("*") != "deny":
        return None, True
    allowed = [name for name, action in value.items() if name != "*"]
    if any(value[name] != "allow" or not valid_name(name) for name in allowed):
        return None, True
    return allowed, False


def _write_permission(entry: dict[str, Any], item: Agent) -> None:
    permission = _as_object(entry.get("permission"))
    for key in PERMISSIONS:
        value = item.access.get(key)
        if value != CUSTOM:
            _set(permission, key, value)
    if not item.custom_task:
        delegates = item.delegates if item.can_delegate else None
        _set(permission, "task", None if delegates is None else {"*": "deny", **dict.fromkeys(delegates, "allow")})
    _set(entry, "permission", permission or None)
    # The permission object replaces the deprecated tool switches; a leftover switch would contradict it.
    tools = _as_object(entry.get("tools"))
    for tool in _OLD_TOOLS:
        tools.pop(tool, None)
    _set(entry, "tools", tools or None)


def _rename_references(config: OpencodeConfig, old: str, new: str | None) -> None:
    for entry in _as_object(config.data.get(LEGACY)).values():
        task = _as_object(_as_object(entry).get("permission")).get("task") if isinstance(entry, dict) else None
        if isinstance(task, dict) and old in task:
            action = task.pop(old)
            if new:
                task[new] = action
    if config.data.get("default_agent") == old:
        _set(config.data, "default_agent", new)


def _set(target: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        target.pop(key, None)
    else:
        target[key] = value


def _as_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
