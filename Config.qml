import QtQuick
import Quickshell
import Quickshell.Io
import "lib/Palette.js" as Palette
import "lib/Themes.js" as Themes

// Two layers: config.json ships usable defaults, config.local.json carries
// only the settings changed from the UI (it is gitignored). Everything has a
// usable default, so missing or malformed files never keep the panel from
// starting.
Item {
  id: root
  visible: false
  width: 0
  height: 0

  property bool baseLoaded: false
  property bool localLoaded: false
  readonly property bool loaded: baseLoaded && localLoaded

  property var base: ({})
  property var local: ({})
  property string saveError: ""
  signal saved()

  property bool startHidden: false
  property int refreshSeconds: 300
  property string output: ""
  property string theme: "auto"
  property bool showSystem: true
  property bool showAgents: true
  property bool showWeather: true
  property var agents: Palette.allAgentIds()

  readonly property string configPath: decodeURIComponent(
    String(Qt.resolvedUrl("config.json")).replace(/^file:\/\//, ""))
  readonly property string localPath: decodeURIComponent(
    String(Qt.resolvedUrl("config.local.json")).replace(/^file:\/\//, ""))

  FileView {
    id: baseFile
    path: root.configPath
    watchChanges: true
    printErrors: false
    onLoaded: root.applyBase(text())
    onFileChanged: reload()
    onLoadFailed: { root.base = ({}); root.baseLoaded = true; root.recompute() }
  }

  FileView {
    id: localFile
    path: root.localPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.applyLocal(text())
    onFileChanged: reload()
    onLoadFailed: { root.local = ({}); root.localLoaded = true; root.recompute() }
    onSaved: { root.saveError = ""; root.saved() }
    onSaveFailed: root.saveError = "设置保存失败，请检查项目目录写入权限"
  }

  function toObject(raw) {
    var data
    try {
      data = JSON.parse(String(raw || ""))
    } catch (e) {
      return ({})
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) return ({})
    return data
  }

  function applyBase(raw) {
    root.base = root.toObject(raw)
    root.baseLoaded = true
    root.recompute()
  }

  function applyLocal(raw) {
    root.local = root.toObject(raw)
    root.localLoaded = true
    root.recompute()
  }

  function booleanValue(key, fallback) {
    var localValue = root.local ? root.local[key] : undefined
    if (typeof localValue === "boolean") return localValue
    var baseValue = root.base ? root.base[key] : undefined
    if (typeof baseValue === "boolean") return baseValue
    return fallback
  }

  function numberValue(key, fallback) {
    var localValue = root.local ? root.local[key] : undefined
    if (typeof localValue === "number" && isFinite(localValue)) return localValue
    var baseValue = root.base ? root.base[key] : undefined
    if (typeof baseValue === "number" && isFinite(baseValue)) return baseValue
    return fallback
  }

  function stringValue(key, fallback) {
    var localValue = root.local ? root.local[key] : undefined
    if (typeof localValue === "string") return localValue
    var baseValue = root.base ? root.base[key] : undefined
    if (typeof baseValue === "string") return baseValue
    return fallback
  }

  function themeValue() {
    var localValue = root.local ? root.local.theme : undefined
    if (Themes.valid(localValue)) return localValue
    var baseValue = root.base ? root.base.theme : undefined
    if (Themes.valid(baseValue)) return baseValue
    return "auto"
  }

  // Unknown ids are dropped. An explicit empty list means "hide all"; a list
  // containing only unknown ids falls back to the canonical defaults.
  function normalizeAgents(raw) {
    var order = Palette.allAgentIds()
    if (!Array.isArray(raw)) return order
    var selected = ({})
    var valid = 0
    for (var i = 0; i < raw.length; i++) {
      var id = raw[i]
      if (typeof id !== "string" || order.indexOf(id) < 0) continue
      selected[id] = true
      valid++
    }
    if (raw.length > 0 && valid === 0) return order
    var result = []
    for (var j = 0; j < order.length; j++) {
      if (selected[order[j]]) result.push(order[j])
    }
    return result
  }

  function agentsValue() {
    var localValue = root.local ? root.local.agents : undefined
    if (Array.isArray(localValue)) return root.normalizeAgents(localValue)
    var baseValue = root.base ? root.base.agents : undefined
    if (Array.isArray(baseValue)) return root.normalizeAgents(baseValue)
    return Palette.allAgentIds()
  }

  function orderedAgents(ids) {
    var order = Palette.allAgentIds()
    var result = []
    for (var i = 0; i < order.length; i++) {
      if (ids.indexOf(order[i]) >= 0) result.push(order[i])
    }
    return result
  }

  function recompute() {
    if (!root.baseLoaded || !root.localLoaded) return
    root.startHidden = root.booleanValue("startHidden", false)
    root.refreshSeconds = Math.max(60, root.numberValue("refreshSeconds", 300))
    root.output = root.stringValue("output", "")
    root.theme = root.themeValue()
    root.showSystem = root.booleanValue("showSystem", true)
    root.showAgents = root.booleanValue("showAgents", true)
    root.showWeather = root.booleanValue("showWeather", true)
    root.agents = root.agentsValue()
  }

  function save() {
    if (!root.loaded) return
    // Keep manual overrides (e.g. output or refreshSeconds) that the settings
    // page does not own; only replace the fields shown in the UI.
    var payload = {}
    if (root.local) {
      for (var key in root.local) payload[key] = root.local[key]
    }
    payload.theme = root.theme
    payload.showSystem = root.showSystem
    payload.showAgents = root.showAgents
    payload.showWeather = root.showWeather
    payload.agents = root.agents.slice()
    localFile.setText(JSON.stringify(payload, null, 2) + "\n")
  }

  function setTheme(value) {
    root.theme = Themes.valid(value) ? value : "auto"
    root.save()
  }

  function setSection(name, enabled) {
    enabled = enabled === true
    if (name === "system") root.showSystem = enabled
    else if (name === "agents") root.showAgents = enabled
    else if (name === "weather") root.showWeather = enabled
    else return
    root.save()
  }

  function setAgentEnabled(id, enabled) {
    if (Palette.allAgentIds().indexOf(id) < 0) return
    var ids = root.agents.slice()
    var index = ids.indexOf(id)
    if (enabled === true && index < 0) ids.push(id)
    else if (enabled !== true && index >= 0) ids.splice(index, 1)
    root.agents = root.orderedAgents(ids)
    root.save()
  }

  function resetDisplayDefaults() {
    root.theme = "auto"
    root.showSystem = true
    root.showAgents = true
    root.showWeather = true
    root.agents = Palette.allAgentIds()
    root.save()
  }
}
