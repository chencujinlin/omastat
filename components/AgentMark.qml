import QtQuick
import "../lib/Format.js" as Fmt

// Official agent mark inside the same tinted tile as the rest of the panel.
// Marks are copied from the installed Omarchy agents plugin; the light twins
// are used when the active theme is light.
Rectangle {
  id: root

  property string agentId: ""
  property string fallback: "?"
  property color accent: "#7aa2f7"
  property var theme: null

  readonly property bool lightSurface: root.theme ? !root.theme.isDark : false
  readonly property bool hasLightTwin: ["codex", "deepseek-harness", "opencode", "pi"].indexOf(root.agentId) >= 0
  readonly property string iconSource: {
    if (!root.agentId) return ""
    var suffix = root.lightSurface && root.hasLightTwin ? "-light" : ""
    return Qt.resolvedUrl("../assets/agents/" + root.agentId + suffix + ".svg")
  }

  implicitWidth: 28
  implicitHeight: 28
  radius: 7
  color: Fmt.alpha(root.accent, 0.15)
  border.width: 1
  border.color: Fmt.alpha(root.accent, 0.3)

  Image {
    id: mark
    anchors.centerIn: parent
    width: 18
    height: 18
    source: root.iconSource
    sourceSize: Qt.size(36, 36)
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
    cache: true
    visible: status === Image.Ready
  }

  Text {
    anchors.centerIn: parent
    visible: mark.status !== Image.Ready
    text: root.fallback
    color: root.accent
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: 9
    font.weight: Font.Bold
    font.letterSpacing: 0.3
  }
}
