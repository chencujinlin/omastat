import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var theme: null
  property var system: null
  property var agents: null

  implicitHeight: 32

  readonly property color dotColor: root.system && root.system.health === "error" ? root.theme.colors.red
    : root.system && root.system.health === "stale" ? root.theme.colors.yellow
    : root.theme.colors.green

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: 1
    color: Fmt.alpha(root.theme.colors.fg, 0.1)
  }

  Rectangle {
    id: dot
    x: 0
    y: 15
    width: 5
    height: 5
    radius: 2.5
    color: root.dotColor
  }

  Text {
    x: 9
    y: 8
    text: "系统" + Fmt.stateLabel(root.system ? root.system.health : "unknown")
      + " · " + (root.agents ? root.agents.count : 0) + " 个 Agent"
      + " · 数据 " + (root.agents ? root.agents.ageLabel : "未知")
    color: Fmt.alpha(root.theme.colors.bright, 0.74)
    font.family: "Noto Sans CJK SC"
    font.pixelSize: 10
    elide: Text.ElideRight
    width: parent.width - x
  }
}
