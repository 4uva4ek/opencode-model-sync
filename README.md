# OpenCode Model Sync

[Русская версия](README.ru.md)

A small desktop app for Linux, macOS (Apple Silicon) and Windows. It asks your model servers which models they serve and adds them to the [opencode](https://opencode.ai) config. It works with the regular opencode release: opencode picks up config changes on its own.

## Features

- Lists the providers in `~/.config/opencode/opencode.json` that have their own API address, and checks whether each server responds.
- Works with Ollama, LM Studio, vLLM, llama.cpp and any OpenAI-compatible server, local or on your network.
- For Ollama and LM Studio it reads the real context size and tool-calling support. Embedding models are skipped.
- **Sync** adds new models. **Remove from config** removes the models you select, for example ones that are gone from the server.
- Two independent buttons keep the same labels in both states. Highlighted means on; muted means off:
  - **Display** shows or hides the model in OpenCode's catalog through the config, preserving its settings.
  - **Tools** enables or disables tool-calling support.
- Only one Model Sync instance runs per user. Launching again brings the existing window forward, including from the tray. A crashed instance does not prevent the next launch.
- Finds local servers on their default ports that are not in the config yet and offers to add them.
- The config only changes when you press a button. A backup `opencode.json.bak-model-sync-*` is written next to it before the first change.
- Rename or remove a provider from its **⋯** menu. Renaming keeps its ID; removing also clears model selections that refer to it.
- The **Workspaces** tab lists the folders opencode works in and cleans up the rows that are stuck there.
- Lives in the tray. Light or dark theme follows the system. Russian and English interface.

Models go into the config section where the provider is defined, the legacy `provider` map or the newer `providers` map. If one ID ended up in both, opencode would ignore the legacy entry together with its server address.

The **Settings** and **MCP** tabs can edit `.jsonc` while retaining comments and unchanged values. The existing provider sync and agent editing actions still refuse to rewrite files containing comments.

## Settings and MCP

Five independent tabs: Providers, Workspaces, Agents and teams, MCP, and Settings.

- Settings covers the `opencode.json` schema for OpenCode 2.1.4: 29 current sections with nested fields and 19 V1 compatibility sections. Categories and search include experimental settings such as `experimental.subagent_depth`.
- Finite choices use dropdowns; nested objects and ordered lists use forms. Arbitrary third-party SDK and plugin data uses JSON. Labels and hover descriptions support English and Russian.
- Not set leaves the field absent, preserving inheritance and OpenCode defaults. Project configuration and managed policies can override global values.
- MCP provides local and remote server creation, editing, removal and enable checkboxes backed by `disabled`. Server names stay constant; global timeouts expand separately.
- Save validates the schema, backs up the file, merges unrelated external edits and refuses conflicting changes. Drafts survive tab and language switches.
- Notices during editing and after saving explain when changes take effect. Server startup settings warn about a restart; integrations may need reconnection. OpenCode is never closed or restarted automatically.

## Agents and teams

The separate **Agents and teams** tab shows which model each opencode agent runs on and lets you change it. The model picker groups models by provider in collapsible sections.

- **Build a team**: a planner on a strong model plus several workers (coder, tester, reviewer, researcher or your own), each on its own model. The planner becomes a primary agent that may hand work only to its workers. With "only hands out work" checked, it cannot edit files or run commands. The workers become subagents, and each gets only the access its role needs: the tester cannot edit files, the reviewer and the researcher change nothing.
- **New agent** and **Edit**: name, description, kind (primary, subagent or both), model, instructions, temperature, access to file edits, commands and the web, and the subagents the agent may hand work to. The built-in agents `build`, `plan`, `general` and `explore` can be set up under their own names.
- Models are picked from the ones opencode has connected: the app asks opencode itself (`opencode models`), so the list holds your local models and free cloud models from opencode Zen and OpenRouter alike. The free, local and tool-calling labels and the context size come from the config and from the [models.dev](https://models.dev) catalog that opencode uses. The catalog is cached for a day. A model you switched off is left out of the list, which `opencode models` still reports. An agent whose model is not among the connected ones is flagged.

The app looks for the opencode command line on `PATH`, in the install script, npm and bun folders, and inside OpenCode Desktop on Windows, macOS and Linux. If it is somewhere else, set the `OPENCODE_CLI` environment variable to its path. If it cannot be found, the model list comes from the config.

New agents go to the `agent` section, whose format the opencode docs describe. An agent from the newer `agents` section is edited there, but its permission rules are kept as written. Settings the app does not manage, such as `color` or `steps`, are kept.

## Workspaces

The **Workspaces** tab lists the folders opencode works in and the git worktrees made from them, the same list opencode shows in its sidebar. Rows for folders that are no longer on the disk stay there for good, and opencode has no screen to clean them up.

- **Exclude** hides a workspace in this app only. opencode is not touched and the folder stays where it is. "Show excluded" brings the hidden rows back; **Bring back** returns one of them.
- **Remove** asks opencode itself. A worktree goes away through `DELETE /api/worktree`, removed the way opencode created it; when it holds changes that are not committed, the app asks a second time before dropping those. A project folder is archived in opencode's database, which is how opencode takes it off its own list — the folder and its sessions stay, and opening the folder in opencode shows it again.
- What opencode has archived is off this page, exactly as it is off opencode's own list. "Show archived" brings those rows into view, and **Back from the archive** clears the mark so the workspace is on the list of opencode again.
- **Add folder** hands a folder to the running opencode, the same way opening a folder there registers it.
- A row says whether its folder is still on the disk, whether it is a git worktree, how many sessions opencode has saved for it, and when it was last used. The **⋯** menu opens the folder.

While opencode runs, the list comes from it through `opencode api`; otherwise the same rows are read from `~/.local/share/opencode/opencode.db`. opencode's database is copied to `opencode.db.bak-model-sync-*` before anything is written to it. Which workspaces are excluded is this app's own file, `~/.config/opencode/model-sync-workspaces.json`.

## Download

Builds for every platform are attached to the [latest release](../../releases/latest). The builds are not signed:

- **macOS:** unzip, then right-click the app and choose **Open** the first time.
- **Windows:** unzip and run `OpenCode Model Sync.exe`. SmartScreen may ask you to confirm.
- **Linux:** unpack the archive and run `opencode-model-sync/OpenCode Model Sync`.

## Run from source

You need [uv](https://docs.astral.sh/uv/).

```bash
uv run opencode-model-sync
```

## Build

Each platform builds its own app:

```bash
uv run python scripts/build.py
```

The result is in `dist/`: an `.app` on macOS, a folder with an `.exe` on Windows, a folder with an executable on Linux, plus an archive. To add it to the Linux application menu:

```bash
sh scripts/install-linux.sh
```

GitHub Actions builds all three platforms. Pushing a `v*` tag runs the `build` workflow and attaches the builds to a release.

## Tests

```bash
uv run pytest
```
