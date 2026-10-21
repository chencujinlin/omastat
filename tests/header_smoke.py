"""Check the header's wide/compact reflow without starting the desktop app."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
import QtQuick
import Quickshell
import "components" as Components
import "services" as Services

ShellRoot {
  Services.Theme { id: theme }
  Components.Header { id: header; width: 380; theme: theme }

  Timer {
    interval: 350
    running: true
    onTriggered: {
      console.log("HEADER wide compact=" + header.compact + " height=" + header.height)
      header.width = 300
      finish.start()
    }
  }

  Timer {
    id: finish
    interval: 650
    onTriggered: {
      console.log("HEADER compact compact=" + header.compact + " height=" + header.height)
      Quickshell.execDetached(["kill", "-TERM", String(Quickshell.processId)])
    }
  }
}
'''

with tempfile.TemporaryDirectory(prefix="omastat-header-smoke-") as temporary:
    base = Path(temporary)
    source = base / "app"
    shutil.copytree(
        ROOT, source,
        ignore=shutil.ignore_patterns(
            ".git", ".aws", ".codex", ".agents", "__pycache__", "*.log",
            "config.local.json", "stage1-*.png"))
    (source / "header_harness.qml").write_text(HARNESS, encoding="utf-8")
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
    process = subprocess.Popen(
        ["quickshell", "-p", str(source / "header_harness.qml")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output = process.communicate(timeout=8)[0]
    except subprocess.TimeoutExpired:
        process.terminate()
        output = process.communicate(timeout=5)[0]

    wide = [line for line in output.splitlines() if "HEADER wide" in line]
    compact = [line for line in output.splitlines() if "HEADER compact" in line]
    if not wide or not compact:
        raise SystemExit("header harness produced no state\n" + output)
    wide_line, compact_line = wide[-1], compact[-1]
    if "compact=false height=64" not in wide_line:
        raise SystemExit("wide header state unexpected\n" + output)
    if "compact=true height=74" not in compact_line:
        raise SystemExit("compact header state unexpected\n" + output)
    if "TypeError" in output or "ReferenceError" in output or "Unable to assign" in output:
        raise SystemExit(output)
    print("header:", wide_line.split("HEADER ")[-1], "->", compact_line.split("HEADER ")[-1])
