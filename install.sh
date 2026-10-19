#!/usr/bin/env bash
# Install omastat into the current user's configuration. Safe to rerun.
set -euo pipefail

PROJECT=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
USER_HOME=${OMASTAT_HOME:-$HOME}
CONFIG_HOME=${XDG_CONFIG_HOME:-$USER_HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$USER_HOME/.local/share}
HYPR_DIR="$CONFIG_HOME/hypr"
SHORTCUT="SUPER + CTRL + M"

say() { printf '%s\n' "Omastat: $*"; }
backup() {
  [[ -f $1 ]] || return 0
  cp -a "$1" "$1.bak.$(date +%Y%m%d-%H%M%S-%N)"
}

link_file() {
  local source=$1 target=$2
  if [[ -L $target && $(readlink -f "$target") == "$source" ]]; then return; fi
  if [[ -d $target && ! -L $target ]]; then say "拒绝覆盖目录：$target"; return 1; fi
  if [[ -e $target || -L $target ]]; then backup "$target"; fi
  ln -sfn "$source" "$target"
}

chmod +x "$PROJECT/bin/omarchy-vitals" "$PROJECT/bin/omastat" "$PROJECT/scripts/vitals_sampler.py"

mkdir -p "$CONFIG_HOME/quickshell" "$USER_HOME/.local/bin" \
  "$DATA_HOME/applications" "$DATA_HOME/icons/hicolor/scalable/apps"

if [[ -e $CONFIG_HOME/quickshell/omarchy-vitals && ! -L $CONFIG_HOME/quickshell/omarchy-vitals ]]; then
  say "拒绝覆盖已存在的真实目录：$CONFIG_HOME/quickshell/omarchy-vitals"
  say "请先把它移走，再重新运行安装脚本"
  exit 1
fi
link_file "$PROJECT" "$CONFIG_HOME/quickshell/omarchy-vitals"
link_file "$PROJECT/bin/omarchy-vitals" "$USER_HOME/.local/bin/omarchy-vitals"
link_file "$PROJECT/bin/omastat" "$USER_HOME/.local/bin/omastat"
install -m 644 "$PROJECT/assets/vitals.svg" "$DATA_HOME/icons/hicolor/scalable/apps/omarchy-vitals.svg"
install -m 644 "$PROJECT/omarchy-vitals.desktop" "$DATA_HOME/applications/omarchy-vitals.desktop"

mkdir -p "$HYPR_DIR" "$CONFIG_HOME/omarchy/plugins"
PLUGIN="$CONFIG_HOME/omarchy/plugins/chencu.omastat"
if [[ -e $PLUGIN && ! -L $PLUGIN ]]; then
  say "保留现有插件目录：$PLUGIN（请人工合并 bar/ 内容）"
else
  link_file "$PROJECT/bar" "$PLUGIN"
fi
python3 "$PROJECT/scripts/integrate.py" --project "$PROJECT" --config-home "$CONFIG_HOME"

if [[ -f $HYPR_DIR/hyprland.lua ]] && ! grep -qF 'require("hypr.vitals")' "$HYPR_DIR/hyprland.lua"; then
  backup "$HYPR_DIR/hyprland.lua"
  printf '\n-- omarchy-vitals\nrequire("hypr.vitals")\n' >>"$HYPR_DIR/hyprland.lua"
  say "已在 hyprland.lua 中加载 hypr.vitals"
fi

if [[ -f $HYPR_DIR/bindings.lua ]] && ! grep -qF 'omastat toggle' "$HYPR_DIR/bindings.lua"; then
  if grep -qF '"SUPER + CTRL + M"' "$HYPR_DIR/bindings.lua"; then
    say "保留已占用的 SUPER + CTRL + M；请使用 Omastat 顶部栏入口"
  else
  backup "$HYPR_DIR/bindings.lua"
  printf '\n-- omarchy-vitals\no.bind("%s", "Omastat", os.getenv("HOME") .. "/.local/bin/omastat toggle")\n' "$SHORTCUT" >>"$HYPR_DIR/bindings.lua"
  say "已绑定快捷键 $SHORTCUT"
  fi
fi

if [[ -f $HYPR_DIR/autostart.lua ]] && grep -qF 'omarchy-vitals' "$HYPR_DIR/autostart.lua"; then
  backup "$HYPR_DIR/autostart.lua"
  sed -i '/omarchy-vitals/d' "$HYPR_DIR/autostart.lua"
  say "已移除旧的登录自启动（按需从菜单或快捷键打开）"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi

if [[ -n ${WAYLAND_DISPLAY:-} ]] && command -v hyprctl >/dev/null 2>&1; then
  hyprctl reload
  hyprctl configerrors
fi

say "Omastat 安装完成；顶部栏配置已添加独立入口"
say "运行：omastat toggle（或 $SHORTCUT）"
say "调试：omastat run"
