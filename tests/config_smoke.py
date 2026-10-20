"""Exercise Config's local-overlay save/load with the real QML FileView.

The panel is not started and no desktop service is touched; this runs an
offscreen Quickshell copy and only writes inside a temporary directory.
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
import Quickshell.Io

ShellRoot {
  id: root
  property bool applied: false

  Config { id: cfg }

  Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: {
      if (root.applied || !cfg.loaded) return
      root.applied = true
      if (Quickshell.env("OMASTAT_CONFIG_CHECK") === "1") {
        console.log("STATE theme=" + cfg.theme + " agents=" + cfg.agents.join(",")
          + " weather=" + cfg.showWeather + " system=" + cfg.showSystem)
        finish.start()
        return
      }
      cfg.setTheme(Quickshell.env("OMASTAT_CONFIG_THEME") || "orange")
      cfg.setSection("weather", false)
      cfg.setAgentEnabled("claude", false)
      finish.start()
    }
  }

  Timer {
    id: finish
    interval: 500
    onTriggered: Quickshell.execDetached(["kill", "-TERM", String(Quickshell.processId)])
  }
}
'''


def run_harness(source, env, check=False, theme=""):
    case = dict(env)
    if check:
        case["OMASTAT_CONFIG_CHECK"] = "1"
    if theme:
        case["OMASTAT_CONFIG_THEME"] = theme
    process = subprocess.Popen(
        ["quickshell", "-p", str(source / "config_harness.qml")],
        env=case, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output = process.communicate(timeout=8)[0]
    except subprocess.TimeoutExpired:
        process.terminate()
        output = process.communicate(timeout=5)[0]
    return process.returncode, output


with tempfile.TemporaryDirectory(prefix="omastat-config-smoke-") as temporary:
    base = Path(temporary)
    source = base / "app"
    shutil.copytree(
        ROOT, source,
        ignore=shutil.ignore_patterns(
            ".git", ".aws", ".codex", ".agents", "__pycache__", "*.log",
            "config.local.json", "stage1-*.png"))
    (source / "config_harness.qml").write_text(HARNESS, encoding="utf-8")
    (source / "config.local.json").write_text('{"refreshSeconds": 120}', encoding="utf-8")
    (base / "run").mkdir(mode=0o700)
    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_PLATFORMTHEME="generic",
        XDG_CURRENT_DESKTOP="",
        QT_STYLE_OVERRIDE="Fusion",
        QT_QUICK_BACKEND="software",
        XDG_RUNTIME_DIR=str(base / "run"),
        XDG_CONFIG_HOME=str(base / "config"),
        XDG_STATE_HOME=str(base / "state"),
        XDG_CACHE_HOME=str(base / "cache"),
        OMASTAT_NO_COLLECT="1",
        OMASTAT_TEST_HOME=str(base / "native"),
    )

    code, output = run_harness(source, env)
    overlay_path = source / "config.local.json"
    if not overlay_path.is_file():
        raise SystemExit("config.local.json was not written\n" + output)
    saved = json.loads(overlay_path.read_text(encoding="utf-8"))
    expected_agents = [a for a in json.loads((source / "config.json").read_text(encoding="utf-8"))["agents"] if a != "claude"]
    expected = {
        "refreshSeconds": 120,
        "theme": "orange",
        "showSystem": True,
        "showAgents": True,
        "showWeather": False,
        "agents": expected_agents,
    }
    if saved != expected:
        raise SystemExit(f"unexpected overlay: {saved!r}\n{output}")
    if "保存失败" in output or "TypeError" in output or "ReferenceError" in output:
        raise SystemExit(output)

    code, output = run_harness(source, env, check=True)
    wanted = "STATE theme=orange agents=" + ",".join(expected_agents) + " weather=false system=true"
    if wanted not in output:
        raise SystemExit("reloaded state did not match\n" + output)

    print("config: local overlay saved and reloaded", saved)

    for theme in ("light", "tokyo-night"):
        code, output = run_harness(source, env, theme=theme)
        saved = json.loads(overlay_path.read_text(encoding="utf-8"))
        expected["theme"] = theme
        if saved != expected:
            raise SystemExit(f"unexpected overlay for {theme}: {saved!r}\n{output}")
        code, output = run_harness(source, env, check=True)
        wanted = "STATE theme=" + theme + " agents=" + ",".join(expected_agents) + " weather=false system=true"
        if wanted not in output:
            raise SystemExit(f"reloaded {theme} state did not match\n" + output)
        print("config: theme persisted", theme)
