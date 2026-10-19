import QtQuick
import Quickshell
import Quickshell.Io
import "../lib/Format.js" as Fmt

// Reads the live Omarchy theme. Everything is best-effort: a missing theme
// falls back to Tokyo Night and the panel keeps working.
Item {
  id: root
  visible: false
  width: 0
  height: 0

  readonly property string home: Quickshell.env("HOME") || ""
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || home + "/.local/state"
  readonly property string themeRoot: stateHome + "/omarchy/current"
  readonly property string colorsPath: themeRoot + "/theme/colors.toml"
  readonly property string namePath: themeRoot + "/theme.name"
  readonly property string backgroundPath: themeRoot + "/background"

  property bool isDark: true
  property string themeName: ""
  property int wallpaperVersion: 0
  property string wallpaperPath: backgroundPath
  property string backgroundTarget: ""

  readonly property string mono: "JetBrainsMono Nerd Font"
  readonly property string sans: "Noto Sans"

  readonly property string wallpaperSource:
    wallpaperPath.length > 0 && backgroundTarget.length > 0
      ? Fmt.fileUrl(backgroundTarget) + "?v=" + wallpaperVersion
      : ""

  property var colors: ({
    accent: "#7aa2f7",
    blue: "#7aa2f7",
    magenta: "#bb9af7",
    cyan: "#7dcfff",
    green: "#9ece6a",
    yellow: "#e0af68",
    orange: "#ff9e64",
    red: "#f7768e",
    fg: "#a9b1d6",
    bright: "#c0caf5",
    muted: "#565f89",
    bg: "#1a1b26",
    darkBg: "#0e0e14",
    lightBg: "#24283b"
  })

  FileView {
    id: colorsFile
    path: root.colorsPath
    watchChanges: true
    printErrors: false
    onLoaded: root.parseColors(text())
    onFileChanged: reload()
  }

  FileView {
    id: nameFile
    path: root.namePath
    watchChanges: true
    printErrors: false
    onLoaded: root.applyName(text())
    onFileChanged: reload()
  }

  Process {
    id: backgroundProbe
    running: false
    command: ["readlink", "-f", root.backgroundPath]
    stdout: SplitParser {
      onRead: function(line) { root.applyBackground(String(line || "").trim()) }
    }
  }

  Timer {
    interval: 8000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      colorsFile.reload()
      nameFile.reload()
      if (!backgroundProbe.running) backgroundProbe.running = true
    }
  }

  function applyName(raw) {
    var name = String(raw || "").trim()
    if (name === root.themeName) return
    root.themeName = name
    root.wallpaperVersion++
  }

  function applyBackground(target) {
    if (!target || target === root.backgroundTarget) return
    root.backgroundTarget = target
    root.wallpaperPath = target
    root.wallpaperVersion++
  }

  function parseColors(raw) {
    var text = String(raw || "")
    if (text.length === 0) return

    var p = {
      accent: "#7aa2f7", blue: "#7aa2f7", magenta: "#bb9af7", cyan: "#7dcfff",
      bright_cyan: "#0db9d7", green: "#9ece6a", yellow: "#e0af68",
      bright_orange: "#ff9e64", orange: "#ff9e64", red: "#f7768e",
      foreground: "#a9b1d6", bright_foreground: "#c0caf5", dark_foreground: "#565f89",
      background: "#1a1b26", dark_background: "#0e0e14", lighter_background: "#24283b"
    }
    var mode = ""
    var re = /^\s*([A-Za-z0-9_]+)\s*=\s*"?(#[0-9a-fA-F]{6})"?\s*$/gm
    var match
    while ((match = re.exec(text)) !== null) {
      var key = match[1]
      if (key in p) p[key] = match[2]
    }
    var modeMatch = text.match(/^\s*mode\s*=\s*"?(dark|light)"?/m)
    if (modeMatch) mode = modeMatch[1]

    var accent = p.accent || p.blue
    var fg = p.foreground || "#a9b1d6"
    var bright = p.bright_foreground || "#c0caf5"
    var muted = p.dark_foreground || "#565f89"
    var bg = p.background || "#1a1b26"
    var bgc = Qt.color(bg)
    var luminance = 0.2126 * bgc.r + 0.7152 * bgc.g + 0.0722 * bgc.b

    root.isDark = mode === "light" ? false : (mode === "dark" ? true : luminance < 0.5)
    root.colors = {
      accent: accent,
      blue: p.blue || accent,
      magenta: p.magenta || "#bb9af7",
      cyan: p.cyan || p.bright_cyan || "#7dcfff",
      green: p.green || "#9ece6a",
      yellow: p.yellow || "#e0af68",
      orange: p.orange || p.bright_orange || "#ff9e64",
      red: p.red || "#f7768e",
      fg: fg,
      bright: root.isDark ? bright : fg,
      muted: muted,
      bg: bg,
      darkBg: p.dark_background || "#0e0e14",
      lightBg: p.lighter_background || "#24283b"
    }
  }
}
