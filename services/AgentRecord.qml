import QtQuick
import Quickshell.Io

// Watches one agent's usage record. The collector is the only writer; this
// component only reads and normalizes.
Item {
  id: root
  visible: false
  width: 0
  height: 0

  property string agentId: ""
  property string usageDir: ""
  property var record: null

  signal recordUpdated(string agentId, var record)

  readonly property string path: usageDir + "/" + agentId + ".json"

  FileView {
    id: file
    path: root.path
    watchChanges: true
    printErrors: false
    onLoaded: root.parse(text())
    onFileChanged: reload()
    onLoadFailed: {
      root.record = null
      root.recordUpdated(root.agentId, null)
    }
  }

  function parse(raw) {
    var data
    try {
      data = JSON.parse(String(raw || ""))
    } catch (e) {
      return
    }
    if (!data || typeof data !== "object") return
    root.record = data
    root.recordUpdated(root.agentId, data)
  }

  function reload() {
    file.reload()
  }
}
