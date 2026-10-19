import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "chencu.omastat"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  property var snapshot: ({})
  property double receivedAt: 0
  property double nowMs: Date.now()
  readonly property string metric: String(setting("metric", "none"))
  readonly property string health: {
    if (!snapshot.running || nowMs - receivedAt > 45000) return "unknown"
    if (metric.indexOf("agent:") === 0) {
      var quotas = snapshot.quotas || []
      for (var i = 0; i < quotas.length; i++) if (quotas[i].id === metric.slice(6)) {
        if (quotas[i].quota === null) return "unknown"
        return quotas[i].cached && quotas[i].state === "normal" ? "stale" : quotas[i].state
      }
      return "unknown"
    }
    return metric === "none" ? snapshot.agentState || "unknown" : snapshot.systemState || "unknown"
  }
  readonly property string label: {
    if (metric === "none") return "Omastat"
    var value = metric === "cpu" ? snapshot.cpu : metric === "memory" ? snapshot.memory : null
    var prefix = metric === "cpu" ? "CPU " : metric === "memory" ? "内存 " : "额度已用 "
    if (metric.indexOf("agent:") === 0) {
      var quotas = snapshot.quotas || []
      for (var i = 0; i < quotas.length; i++) if (quotas[i].id === metric.slice(6) && quotas[i].quota !== null) value = quotas[i].quota * 100
    }
    return prefix + (value === null || value === undefined ? "--" : Math.round(value) + "%")
  }
  Process {
    id: probe
    command: ["omastat", "bar", root.metric]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.snapshot = JSON.parse(text); root.receivedAt = Date.now() }
        catch (e) { root.snapshot = ({}) }
      }
    }
    onExited: function(code) { if (code !== 0) root.snapshot = ({}) }
  }
  Timer {
    interval: 15000; running: true; repeat: true; triggeredOnStart: true
    onTriggered: { root.nowMs = Date.now(); if (!probe.running) probe.running = true }
  }
  onMetricChanged: if (!probe.running) probe.running = true
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    foreground: root.health === "error" ? Commons.Color.urgent : root.health === "stale" ? "#d4a84b" : Commons.Color.foreground
    text: (root.health === "normal" ? "○ " : root.health === "error" ? "● " : root.health === "stale" ? "◐ " : "◌ ") + root.label
    labelVisible: !root.vertical
    hasVisualContent: true
    tooltipText: "Omastat · " + ({normal: "正常", stale: "过期", error: "异常", unknown: "未知"})[root.health] + " · 点击显示/隐藏"
    horizontalMargin: 8
    onPressed: function(b) { if (b === Qt.LeftButton) Quickshell.execDetached(["omastat", "toggle"]) }
    Text { visible: root.vertical; anchors.centerIn: parent; text: "◫"; color: root.bar ? root.bar.barForeground : "#a9b1d6"; font.pixelSize: 16 }
  }
}
