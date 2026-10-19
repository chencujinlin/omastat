import QtQuick
import Quickshell
import Quickshell.Io

// Uses the same location state and wttr.in source as Omarchy's status-bar
// weather panel. One-shot reads keep the app's QML process simple; the JSON
// payload is tiny and contains no credentials.
Item {
  id: root
  visible: false

  property bool panelVisible: true
  property var weatherData: ({ state: "loading" })
  readonly property bool fetchEnabled: Quickshell.env("OMASTAT_NO_COLLECT") !== "1"
  readonly property bool ready: weatherData && weatherData.state === "ok"

  function request() {
    if (fetchEnabled && !probe.running) probe.running = true
  }

  Process {
    id: probe
    command: ["python3", decodeURIComponent(String(Qt.resolvedUrl("../scripts/weather_service.py")).replace(/^file:\/\//, "")),
      "--home", Quickshell.env("OMASTAT_TEST_HOME") || Quickshell.env("HOME")]
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          let value = JSON.parse(String(text).trim())
          root.weatherData = value && typeof value === "object" ? value : ({ state: "error" })
        } catch (e) {
          root.weatherData = ({ state: "error" })
        }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: if (String(text).trim().length > 0) root.weatherData = ({ state: "error" })
    }
    onExited: function(code) {
      if (code !== 0 && (!root.weatherData || root.weatherData.state === "loading")) root.weatherData = ({ state: "error" })
    }
  }

  Timer {
    interval: 900000
    running: root.panelVisible && root.fetchEnabled
    repeat: true
    triggeredOnStart: true
    onTriggered: root.request()
  }

  Timer {
    interval: 120000
    running: root.panelVisible && root.fetchEnabled && root.weatherData.state === "error"
    repeat: true
    onTriggered: root.request()
  }

  Component.onCompleted: if (root.panelVisible) root.request()
}
