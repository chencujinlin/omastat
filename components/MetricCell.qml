import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var theme: null
  property string label: ""
  property string value: "--"
  property color valueColor: "#c0caf5"
  property bool showBar: false
  property real barValue: 0
  property color accent: "#7aa2f7"

  implicitHeight: 48

  Column {
    width: parent.width
    spacing: 2

    Text {
      text: root.label
      color: Fmt.alpha(root.theme.colors.bright, 0.64)
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 10
      font.letterSpacing: 0.7
    }
    Text {
      width: parent.width
      text: root.value
      color: root.valueColor
      font.family: "JetBrainsMono Nerd Font"
      font.pixelSize: 18
      font.weight: Font.DemiBold
      elide: Text.ElideRight
    }
    Meter {
      visible: root.showBar
      width: parent.width
      height: 2
      value: root.barValue
      color: root.accent
      trackColor: Fmt.alpha(root.theme.colors.fg, 0.12)
    }
  }
}
