import QtQuick
import Quickshell
import Quickshell.Io

// Small, optional user configuration. Everything has a usable default, so a
// missing or malformed config.json never keeps the panel from starting.
Item {
  id: root
  visible: false
  width: 0
  height: 0

  property bool loaded: false
  property bool startHidden: false
  property int refreshSeconds: 300
  property string output: ""
  property var agents: ["codex", "deepseek-harness", "opencode", "claude", "pi", "fireworks"]

  readonly property string configPath: decodeURIComponent(
    String(Qt.resolvedUrl("config.json")).replace(/^file:\/\//, ""))

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    printErrors: false
    onLoaded: root.apply(text())
    onFileChanged: reload()
    onLoadFailed: root.loaded = true
  }

  function apply(raw) {
    var data
    try {
      data = JSON.parse(String(raw || ""))
    } catch (e) {
      root.loaded = true
      return
    }
    if (!data || typeof data !== "object") {
      root.loaded = true
      return
    }

    if (typeof data.startHidden === "boolean") root.startHidden = data.startHidden
    if (typeof data.refreshSeconds === "number")
      root.refreshSeconds = Math.max(60, data.refreshSeconds)
    if (typeof data.output === "string") root.output = data.output
    if (data.agents && typeof data.agents.length === "number") {
      var clean = []
      for (var i = 0; i < data.agents.length; i++) {
        if (typeof data.agents[i] === "string" && data.agents[i].length > 0)
          clean.push(data.agents[i])
      }
      if (clean.length > 0) root.agents = clean
    }
    root.loaded = true
  }
}
