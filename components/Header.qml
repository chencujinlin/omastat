import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var theme: null
  property var system: null
  property var agents: null
  implicitHeight: 64

  readonly property var colors: theme ? theme.colors : ({
    accent: "#7aa2f7", green: "#9ece6a", yellow: "#e0af68", red: "#f7768e",
    fg: "#a9b1d6", bright: "#c0caf5", muted: "#565f89"
  })
  property date clockDate: new Date()
  Timer { interval: 30000; running: root.visible; repeat: true; onTriggered: root.clockDate = new Date() }

  Item {
    id: mark
    x: 0
    y: 5
    width: 16
    height: 16

    Rectangle { x: 0; y: 10; width: 3; height: 6; radius: 1.5; color: Fmt.alpha(root.colors.accent, 0.55) }
    Rectangle { x: 4.3; y: 3; width: 3; height: 13; radius: 1.5; color: root.colors.accent }
    Rectangle { x: 8.6; y: 7; width: 3; height: 9; radius: 1.5; color: Fmt.alpha(root.colors.accent, 0.8) }
    Rectangle { x: 12.9; y: 1; width: 3; height: 15; radius: 1.5; color: Fmt.alpha(root.colors.bright, 0.9) }
  }

  Text {
    id: word
    x: 24
    y: -3
    text: "Omastat"
    color: root.colors.bright
    font.family: "Z003"
    font.pixelSize: 27
    font.letterSpacing: 0.4
  }

  Rectangle {
    id: liveDot
    x: word.x + word.width + 8
    y: 13
    width: 5
    height: 5
    radius: 2.5
    color: root.agents && root.agents.count > 0 ? root.colors.green : root.colors.yellow
  }

  Text {
    anchors.right: parent.right
    y: 0
    text: Fmt.clock(root.clockDate)
    color: root.colors.bright
    font.family: "JetBrainsMono Nerd Font"
    font.pixelSize: 19
    font.weight: Font.DemiBold
  }

  Text {
    anchors.right: parent.right
    y: 27
    text: Fmt.fullDate(root.clockDate)
    color: Fmt.alpha(root.colors.bright, 0.76)
    font.family: "Noto Sans CJK SC"
    font.pixelSize: 10
    font.letterSpacing: 0.5
  }

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Fmt.alpha(root.colors.fg, 0.1)
  }
}
