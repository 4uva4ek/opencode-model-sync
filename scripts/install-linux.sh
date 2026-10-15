#!/usr/bin/env sh
# Installs the PyInstaller build for the current user and adds it to the application menu.
#   uv run python scripts/build.py && sh scripts/install-linux.sh
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
build="$root/dist/OpenCode Model Sync"
target="${XDG_DATA_HOME:-$HOME/.local/share}/opencode-model-sync"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"

[ -x "$build/OpenCode Model Sync" ] || { echo "Build first: uv run python scripts/build.py" >&2; exit 1; }

rm -rf "$target"
mkdir -p "$target" "$apps" "$icons"
cp -r "$build/." "$target/"
cp "$root/assets/icon.png" "$icons/opencode-model-sync.png"

cat > "$apps/opencode-model-sync.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OpenCode Model Sync
Comment=Add models from local and self-hosted servers to opencode
Exec="$target/OpenCode Model Sync"
Icon=opencode-model-sync
Terminal=false
Categories=Development;Utility;
StartupWMClass=opencode-model-sync
EOF

update-desktop-database "$apps" 2>/dev/null || true
echo "Installed to $target"
