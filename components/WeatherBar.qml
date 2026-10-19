import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var theme: null
  property var weather: null

  readonly property var info: weather && weather.weatherData ? weather.weatherData : ({})
  readonly property bool ready: info.state === "ok"
  readonly property string temperatureText: info.temperature !== null && info.temperature !== undefined
    ? info.temperature + "°" : "--"
  readonly property string locationText: [info.location || "", info.condition || ""]
    .filter(function(part) { return part.length > 0 }).join(" · ")
  readonly property string feelsText: {
    var parts = []
    if (info.feelsLike !== null && info.feelsLike !== undefined) parts.push("体感 " + info.feelsLike + "°")
    if (info.humidity !== null && info.humidity !== undefined) parts.push("湿度 " + info.humidity + "%")
    return parts.join(" · ")
  }
  readonly property string highLowText: info.high !== null && info.high !== undefined
    && info.low !== null && info.low !== undefined
    ? "最高 " + info.high + "° / 最低 " + info.low + "°" : ""
  readonly property string windText: {
    if (info.windKmph === null || info.windKmph === undefined) return ""
    var direction = info.windDirZh || info.windDir || ""
    return direction + (direction ? " " : "") + info.windKmph + " km/h"
  }

  visible: ready
  implicitHeight: 62
  height: visible ? implicitHeight : 0

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: 1
    color: Fmt.alpha(root.theme.colors.fg, 0.16)
  }

  Row {
    id: leftRow
    anchors.left: parent.left
    anchors.right: rightColumn.left
    anchors.rightMargin: 12
    anchors.verticalCenter: parent.verticalCenter
    spacing: 10

    Text {
      height: 36
      verticalAlignment: Text.AlignVCenter
      text: root.info.icon || "☁"
      color: root.theme.colors.cyan
      font.family: "JetBrainsMono Nerd Font"
      font.pixelSize: 28
    }
    Text {
      height: 36
      verticalAlignment: Text.AlignVCenter
      text: root.temperatureText
      color: root.theme.colors.bright
      font.family: "JetBrainsMono Nerd Font"
      font.pixelSize: 27
      font.weight: Font.DemiBold
    }
    Column {
      anchors.verticalCenter: parent.verticalCenter
      width: Math.max(0, leftRow.width - 28 - 10 - 58 - 20)
      spacing: 1
      Text {
        width: parent.width
        text: root.locationText
        color: Fmt.alpha(root.theme.colors.bright, 0.92)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 12
        elide: Text.ElideRight
      }
      Text {
        width: parent.width
        text: root.feelsText
        color: Fmt.alpha(root.theme.colors.bright, 0.58)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 9
        elide: Text.ElideRight
      }
    }
  }

  Column {
    id: rightColumn
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    width: implicitWidth
    spacing: 1

    Text {
      anchors.right: parent.right
      text: root.highLowText
      color: Fmt.alpha(root.theme.colors.bright, 0.82)
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 11
    }
    Text {
      anchors.right: parent.right
      text: root.windText
      color: Fmt.alpha(root.theme.colors.bright, 0.55)
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 9
    }
  }
}
