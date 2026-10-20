"""Verify the built-in theme presets through the real Theme QML service.

Runs offscreen copies of the project; no desktop service, network, or user
configuration is touched.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
import QtQuick
import Quickshell
import "services" as Services

ShellRoot {
  Services.Theme { id: theme; mode: Quickshell.env("OMASTAT_THEME_MODE") }

  Timer {
    interval: 250
    running: true
    onTriggered: {
      console.log("THEME " + JSON.stringify({
        mode: theme.mode,
        glass: theme.glass,
        dark: theme.isDark,
        radius: theme.radius,
        accent: theme.colors.accent,
        bg: theme.colors.bg,
        bright: theme.colors.bright,
        label: theme.displayName
      }))
      Quickshell.execDetached(["kill", "-TERM", String(Quickshell.processId)])
    }
  }
}
'''

EXPECTED = {
    "auto": {"glass": True, "dark": True, "radius": 18, "label": "跟随 Omarchy"},
    "tokyo-night": {
        "glass": False, "dark": True, "radius": 10,
        "accent": "#7aa2f7", "bg": "#1a1b26", "bright": "#c0caf5",
        "label": "Tokyo Night"},
    "orange": {
        "glass": False, "dark": True, "radius": 10,
        "accent": "#e68e0d", "bg": "#17120e", "bright": "#f4e7d6",
        "label": "橙色"},
    "light": {
        "glass": False, "dark": False, "radius": 10,
        "accent": "#b55436", "bg": "#f0eee6", "bright": "#1f1e1d",
        "label": "浅色"},
}


def run_theme(source, base, mode):
    runtime = base / "run" / mode.replace("-", "_")
    runtime.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_PLATFORMTHEME="generic",
        XDG_CURRENT_DESKTOP="",
        QT_STYLE_OVERRIDE="Fusion",
        QT_QUICK_BACKEND="software",
        XDG_RUNTIME_DIR=str(runtime),
        XDG_CONFIG_HOME=str(base / "config"),
        XDG_STATE_HOME=str(base / "state"),
        XDG_CACHE_HOME=str(base / "cache"),
        OMASTAT_NO_COLLECT="1",
        OMASTAT_THEME_MODE=mode,
    )
    process = subprocess.Popen(
        ["quickshell", "-p", str(source / "theme_harness.qml")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output = process.communicate(timeout=8)[0]
    except subprocess.TimeoutExpired:
        process.terminate()
        output = process.communicate(timeout=5)[0]
    for line in output.splitlines():
        if line.startswith("DEBUG qml: THEME "):
            return json.loads(line[len("DEBUG qml: THEME "):])
        if "THEME {" in line:
            return json.loads(line[line.index("THEME {") + len("THEME "):])
    raise RuntimeError(f"no theme output for {mode}\n{output}")


with tempfile.TemporaryDirectory(prefix="omastat-theme-smoke-") as temporary:
    base = Path(temporary)
    source = base / "app"
    shutil.copytree(
        ROOT, source,
        ignore=shutil.ignore_patterns(
            ".git", ".aws", ".codex", ".agents", "__pycache__", "*.log",
            "config.local.json", "stage1-*.png"))
    (source / "theme_harness.qml").write_text(HARNESS, encoding="utf-8")

    for mode in ("auto", "tokyo-night", "orange", "light"):
        actual = run_theme(source, base, mode)
        expected = EXPECTED[mode]
        for key, value in expected.items():
            if actual.get(key) != value:
                raise SystemExit(
                    f"{mode}: {key}={actual.get(key)!r}, expected {value!r}\n{actual}")
        if actual.get("mode") != mode:
            raise SystemExit(f"{mode}: service kept mode {actual.get('mode')!r}")
        print(f"theme: {mode} ok {actual}")
