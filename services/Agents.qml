import QtQuick
import Quickshell
import Quickshell.Io
import "../lib/Format.js" as Fmt

// Accounting and refresh policy live in the tested Python reader. QML renders
// snapshots and never scans transcripts or renews quota timestamps.
Item {
  id: root
  visible: false
  property var config: null
  property var snapshot: ({ agents: [], state: "unknown", updatedAtMs: 0 })
  property double nowMs: Date.now()
  property bool workerFailed: false
  readonly property var visibleAgents: snapshot.agents || []
  readonly property int count: visibleAgents.length
  readonly property bool refreshing: snapshot.refreshing === true
  readonly property string health: workerFailed ? "error"
    : (snapshot.generatedAtMs && nowMs - snapshot.generatedAtMs > 45000 ? "stale" : snapshot.state || "unknown")
  readonly property bool stale: health !== "normal"
  readonly property string ageLabel: Fmt.age(snapshot.updatedAtMs, nowMs)
  readonly property string lastError: workerFailed ? "采集服务暂不可用" : ""

  Process {
    id: worker
    command: ["python3", decodeURIComponent(String(Qt.resolvedUrl("../scripts/agents_service.py")).replace(/^file:\/\//, "")),
      "--home", Quickshell.env("OMASTAT_TEST_HOME") || Quickshell.env("HOME"),
      "--config", decodeURIComponent(String(Qt.resolvedUrl("../config.json")).replace(/^file:\/\//, ""))]
    stdinEnabled: true
    stdout: SplitParser {
      onRead: function(line) {
        try {
          let value = JSON.parse(line)
          if (value && value.agents && typeof value.agents.length === "number") {
            root.snapshot = value
            root.workerFailed = false
          }
        } catch (e) { root.workerFailed = true }
      }
    }
    stderr: SplitParser { onRead: function(line) { root.workerFailed = true } }
    onExited: { root.workerFailed = true; restart.restart() }
  }
  Timer { id: restart; interval: 5000; onTriggered: worker.running = true }
  Timer { interval: 15000; running: true; repeat: true; onTriggered: root.nowMs = Date.now() }
  Component.onCompleted: worker.running = true
  function refresh(force) { if (worker.running) worker.write("refresh\n"); else worker.running = true }
}
