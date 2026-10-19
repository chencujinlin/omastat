pragma ComponentBehavior: Bound
import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var theme: null
  property string label: ""
  property string glyphKind: "cpu"
  property color accent: "#7aa2f7"
  property real value: 0
  property string valueText: "暂无数据"
  property string meta: ""
  property var history: []
  property var historyTimes: []
  property bool available: true
  property var processes: []
  property string model: ""
  property bool processesExpanded: false

  implicitHeight: body.implicitHeight + 20

  Column {
    id: body
    y: 10
    width: parent.width
    spacing: 7

    Item {
      width: parent.width
      height: root.model.length > 0 ? 39 : 30

      Glyph {
        y: 4
        kind: root.glyphKind
        color: root.accent
        opacity: root.available ? 1 : 0.5
        scale: 1.15
        transformOrigin: Item.TopLeft
      }
      Text {
        x: 23
        y: 2
        text: root.label
        color: Fmt.alpha(root.theme.colors.bright, 0.9)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 13
        font.weight: Font.DemiBold
      }
      Text {
        x: 23
        y: 19
        width: parent.width - 92
        visible: text.length > 0
        text: root.model
        color: Fmt.alpha(root.theme.colors.bright, 0.62)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 10
        elide: Text.ElideRight
      }
      Text {
        anchors.right: parent.right
        y: -4
        text: root.valueText
        color: root.available ? root.accent : Fmt.alpha(root.theme.colors.fg, 0.8)
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: root.available ? 24 : 13
        font.weight: Font.DemiBold
      }
    }

    Meter {
      width: parent.width
      height: 4
      value: root.available ? root.value / 100 : 0
      color: root.accent
      trackColor: Fmt.alpha(root.theme.colors.fg, 0.2)
    }

    Text {
      width: parent.width
      visible: text.length > 0
      text: root.meta
      color: Fmt.alpha(root.theme.colors.bright, 0.75)
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 11
      wrapMode: Text.Wrap
      lineHeight: 1.15
    }

    Sparkline {
      visible: root.available && root.history.length > 1
      width: parent.width
      height: 22
      values: root.history
      times: root.historyTimes
      stroke: root.accent
      maxValue: 100
      fillOpacity: 0.12
      lineWidth: 1.2
      opacity: 0.55
    }

    Column {
      width: parent.width
      visible: root.processes.length > 0
      spacing: 3

      Item {
        id: processToggle
        width: parent.width
        height: 23

        HoverHandler {
          id: processHover
          cursorShape: Qt.PointingHandCursor
        }

        Rectangle {
          anchors.fill: parent
          radius: 6
          color: processHover.hovered ? Fmt.alpha(root.theme.colors.bright, 0.06) : "transparent"
        }

        Text {
          anchors.left: parent.left
          anchors.leftMargin: 1
          anchors.verticalCenter: parent.verticalCenter
          text: (root.processesExpanded ? "▾  " : "▸  ") + "高占用进程"
          color: Fmt.alpha(root.theme.colors.bright, 0.8)
          font.family: "Noto Sans CJK SC"
          font.pixelSize: 10
          font.letterSpacing: 0.6
        }
        Text {
          anchors.right: parent.right
          anchors.rightMargin: 3
          anchors.verticalCenter: parent.verticalCenter
          text: root.processesExpanded ? "收起" : "点击展开"
          color: Fmt.alpha(root.theme.colors.bright, 0.58)
          font.family: "Noto Sans CJK SC"
          font.pixelSize: 9
        }

        TapHandler {
          onTapped: root.processesExpanded = !root.processesExpanded
        }
      }

      Column {
        width: parent.width
        visible: root.processesExpanded
        spacing: 2

        Repeater {
          model: root.processes

          delegate: Item {
            id: processRow
            required property var modelData
            width: parent.width
            height: 19

            Text {
              id: procName
              anchors.left: parent.left
              anchors.leftMargin: 1
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - procPct.width - 10
              text: processRow.modelData.name || ""
              color: Fmt.alpha(root.theme.colors.bright, 0.84)
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 12
              elide: Text.ElideRight
            }
            Text {
              id: procPct
              anchors.right: parent.right
              anchors.rightMargin: 1
              anchors.verticalCenter: parent.verticalCenter
              text: Number(processRow.modelData.pct || 0).toFixed(1) + "%"
              color: root.accent
              font.family: "JetBrainsMono Nerd Font"
              font.pixelSize: 12
            }
          }
        }
      }
    }
  }
}
