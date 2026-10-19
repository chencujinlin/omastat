#!/usr/bin/env bash
# Remove omastat from the current user's configuration. The project
# directory itself is left untouched.
set -uo pipefail

PROJECT=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
USER_HOME=${OMASTAT_HOME:-$HOME}
CONFIG_HOME=${XDG_CONFIG_HOME:-$USER_HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$USER_HOME/.local/share}
HYPR_DIR="$CONFIG_HOME/hypr"

say() { printf '%s\n' "Omastat: $*"; }

if command -v omarchy-vitals >/dev/null 2>&1; then
  omarchy-vitals quit >/dev/null 2>&1 || true
fi

if [[ -L $CONFIG_HOME/quickshell/omarchy-vitals ]]; then
  rm -f "$CONFIG_HOME/quickshell/omarchy-vitals"
  say "已移除 Quickshell 配置软链"
fi
if [[ -L $USER_HOME/.local/bin/omarchy-vitals ]]; then
  rm -f "$USER_HOME/.local/bin/omarchy-vitals"
fi
rm -f "$DATA_HOME/applications/omarchy-vitals.desktop"
rm -f "$DATA_HOME/icons/hicolor/scalable/apps/omarchy-vitals.svg"
python3 "$PROJECT/scripts/integrate.py" --project "$PROJECT" --config-home "$CONFIG_HOME" --remove
if [[ -L $CONFIG_HOME/omarchy/plugins/chencu.omastat ]]; then
  rm -f "$CONFIG_HOME/omarchy/plugins/chencu.omastat"
fi
if [[ -L $USER_HOME/.local/bin/omastat ]]; then
  rm -f "$USER_HOME/.local/bin/omastat"
fi
rm -f "${XDG_STATE_HOME:-$USER_HOME/.local/state}/omarchy/vitals-limits.json"

python3 - "$HYPR_DIR" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
for name in ("hyprland.lua", "bindings.lua", "autostart.lua"):
    path = root / name
    if not path.is_file():
        continue
    lines = path.read_text().splitlines(keepends=True)
    kept = []
    for line in lines:
        if "-- omarchy-vitals" in line:
            continue
        if 'require("hypr.vitals")' in line:
            continue
        if "omarchy-vitals toggle" in line or "omastat toggle" in line:
            continue
        if "launch_on_start" in line and "omarchy-vitals" in line:
            continue
        kept.append(line)
    if kept != lines:
        path.with_name(path.name + ".bak.uninstall." + str(__import__("time").time_ns())).write_text("".join(lines))
        path.write_text("".join(kept))
        print(f"omarchy-vitals: 已清理 {path}")
PY

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi
if [[ -n ${WAYLAND_DISPLAY:-} ]] && command -v hyprctl >/dev/null 2>&1; then
  hyprctl reload
  hyprctl configerrors
fi

say "已卸载（项目文件未删除）"
