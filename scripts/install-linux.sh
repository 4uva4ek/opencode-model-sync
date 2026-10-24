#!/usr/bin/env sh
# Installs the PyInstaller build for the current user and adds it to the application menu.
#   uv run python scripts/build.py && sh scripts/install-linux.sh
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
build="$root/dist/OpenCode Companion"
target="${XDG_DATA_HOME:-$HOME/.local/share}/opencode-companion"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"

[ -x "$build/OpenCode Companion" ] || { echo "Build first: uv run python scripts/build.py" >&2; exit 1; }

rm -rf "$target"
mkdir -p "$target" "$apps" "$icons"
cp -r "$build/." "$target/"
cp "$root/assets/icon.png" "$icons/opencode-companion.png"

cat > "$apps/opencode-companion.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OpenCode Companion
Comment=Manage OpenCode models, agents, MCP servers and settings
Exec="$target/OpenCode Companion"
Icon=opencode-companion
Terminal=false
Categories=Development;Utility;
StartupWMClass=opencode-companion
EOF

update-desktop-database "$apps" 2>/dev/null || true
echo "Installed to $target"
