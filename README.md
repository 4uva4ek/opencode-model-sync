# OpenCode Model Sync

[Русская версия](README.ru.md)

A small desktop app for Linux, macOS (Apple Silicon) and Windows. It asks your model servers which models they serve and adds them to the [opencode](https://opencode.ai) config. It works with the regular opencode release: opencode picks up config changes on its own.

## Features

- Lists the providers in `~/.config/opencode/opencode.json` that have their own API address, and checks whether each server responds.
- Works with Ollama, LM Studio, vLLM, llama.cpp and any OpenAI-compatible server, local or on your network.
- For Ollama and LM Studio it reads the real context size and tool-calling support. Embedding models are skipped.
- **Sync** adds new models. **Remove from config** removes the models you select, for example ones that are gone from the server.
- The tool-calling label of a model in the config is a switch. Turn it off for a model that says it supports tools but handles them poorly.
- Finds local servers on their default ports that are not in the config yet and offers to add them.
- The config only changes when you press a button. A backup `opencode.json.bak-model-sync-*` is written next to it before the first change.
- Lives in the tray. Light or dark theme follows the system. Russian and English interface.

Models go into the config section where the provider is defined, the legacy `provider` map or the newer `providers` map. If one ID ended up in both, opencode would ignore the legacy entry together with its server address.

`.jsonc` files with comments are read but never rewritten, so the comments are not lost.

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
