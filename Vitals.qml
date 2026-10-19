pragma ComponentBehavior: Bound
import QtQuick
import "components"
import "lib/Format.js" as Fmt
import "lib/Palette.js" as Palette

Item {
  id: root

  property var theme: null
  property var system: null
  property var agents: null
  property var weather: null
  property var config: null
  property bool panelVisible: true
  property alias flickable: flick

  readonly property var colors: theme.colors
  readonly property real maxContentWidth: 1180
  readonly property real sideMargin: width > 700 ? 24 : 12
  readonly property real contentWidth: Math.min(maxContentWidth, Math.max(0, width - sideMargin * 2))
  readonly property real contentX: (width - contentWidth) / 2
  readonly property bool wide: contentWidth >= 640
  readonly property real todayTotalTokens: {
    var list = root.agents ? root.agents.visibleAgents : []
    var total = 0, any = false
    for (var i = 0; i < list.length; i++) {
      var value = list[i].todayTokens
      if (value !== null && value !== undefined && isFinite(Number(value))) {
        total += Number(value)
        any = true
      }
    }
    return any ? total : -1
  }

  function diskDetails() {
    var parts = [Fmt.diskMeta(root.system.diskUsedGb, root.system.diskTotalGb),
                 "可用 " + Fmt.gb(root.system.diskFreeGb) + " G"]
    if (root.system.diskReadBps !== null || root.system.diskWriteBps !== null)
      parts.push("读 " + Fmt.bytesPerSecond(root.system.diskReadBps) + " · 写 " + Fmt.bytesPerSecond(root.system.diskWriteBps))
    return parts.join("\n")
  }

  function gpuDetails() {
    var parts = [system.gpuEngine ? "引擎 " + system.gpuEngine : "使用率暂无数据"]
    if (system.gpuFreqMhz !== null) parts.push(Fmt.mhz(system.gpuFreqMhz))
    if (system.gpuTempC !== null) parts.push(Fmt.temp(system.gpuTempC))
    if (system.gpuVramUsedGb !== null && system.gpuVramTotalGb !== null) parts.push("显存 " + Fmt.memoryMeta(system.gpuVramUsedGb, system.gpuVramTotalGb))
    if (system.gpuPowerW !== null) parts.push(Number(system.gpuPowerW).toFixed(1) + " W")
    return parts.join(" · ")
  }

  Header {
    id: header
    x: root.contentX
    width: root.contentWidth
    anchors.top: parent.top
    theme: root.theme
    system: root.system
    agents: root.agents
  }

  Footer {
    id: footer
    x: root.contentX
    width: root.contentWidth
    anchors.bottom: parent.bottom
    theme: root.theme
    system: root.system
    agents: root.agents
  }

  WeatherBar {
    id: weatherBar
    x: root.contentX
    width: root.contentWidth
    anchors.bottom: footer.top
    theme: root.theme
    weather: root.weather
  }

  Flickable {
    id: flick
    x: root.contentX
    width: root.contentWidth
    anchors.top: header.bottom
    anchors.bottom: weatherBar.top
    contentWidth: width
    contentHeight: Math.max(height, grid.height + 24)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick

    Grid {
      id: grid
      width: flick.width
      y: root.wide ? Math.max(0, (flick.height - grid.height) / 2) : 0
      columns: root.wide ? 2 : 1
      columnSpacing: 28
      rowSpacing: 24

      Column {
        width: root.wide ? (grid.width - grid.columnSpacing) / 2 : grid.width
        spacing: 0

        Item {
          width: parent.width
          height: 30
          Text {
            x: 0
            y: 9
            text: "SYSTEM"
            color: Fmt.alpha(root.colors.bright, 0.74)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            font.weight: Font.Bold
            font.letterSpacing: 2.0
          }
        }

        SystemRow {
          width: parent.width
          theme: root.theme
          label: "CPU"
          model: root.system.cpuModel
          glyphKind: "cpu"
          accent: Palette.system("cpu", root.colors)
          value: root.system.cpuPct || 0
          valueText: Fmt.percent(root.system.cpuPct)
          available: root.system.cpuAvailable
          meta: [Fmt.ghz(root.system.cpuFreqGhz), Fmt.temp(root.system.cpuTempC)].filter(function(v) { return v.length > 0 }).join(" · ")
            + (root.system.load1 !== null ? " · 负载 " + Number(root.system.load1).toFixed(1) : "")
          history: root.system.cpuHistory
          historyTimes: root.system.historyTimes
        }

        Divider { width: parent.width; color: Fmt.alpha(root.colors.fg, 0.16) }

        SystemRow {
          width: parent.width
          theme: root.theme
          label: "GPU"
          model: root.system.gpuModel
          glyphKind: "gpu"
          accent: Palette.system("gpu", root.colors)
          value: root.system.gpuPct || 0
          valueText: Fmt.percent(root.system.gpuPct)
          available: root.system.gpuAvailable
          meta: root.gpuDetails()
          history: root.system.gpuHistory
          historyTimes: root.system.historyTimes
        }

        Divider { width: parent.width; color: Fmt.alpha(root.colors.fg, 0.16) }

        SystemRow {
          width: parent.width
          theme: root.theme
          label: "内存"
          glyphKind: "mem"
          accent: Palette.system("mem", root.colors)
          value: root.system.memPct || 0
          valueText: Fmt.percent(root.system.memPct)
          available: root.system.memAvailable
          meta: Fmt.memoryMeta(root.system.memUsedGb, root.system.memTotalGb)
            + "\nSwap " + Fmt.memoryMeta(root.system.swapUsedGb, root.system.swapTotalGb)
          history: root.system.memHistory
          historyTimes: root.system.historyTimes
          processes: root.system.memTop
        }

        Divider { width: parent.width; color: Fmt.alpha(root.colors.fg, 0.16) }

        SystemRow {
          width: parent.width
          theme: root.theme
          label: "磁盘"
          glyphKind: "disk"
          accent: Palette.system("disk", root.colors)
          value: root.system.diskPct || 0
          valueText: Fmt.percent(root.system.diskPct)
          available: root.system.diskAvailable
          meta: root.diskDetails()
          history: root.system.diskHistory
          historyTimes: root.system.historyTimes
        }
      }

      Column {
        width: root.wide ? (grid.width - grid.columnSpacing) / 2 : grid.width
        spacing: 0

        Item {
          width: parent.width
          height: 36

          Text {
            x: 0
            y: 10
            text: "AGENTS"
            color: Fmt.alpha(root.colors.bright, 0.86)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
            font.weight: Font.Bold
            font.letterSpacing: 2.0
          }
          Text {
            x: 76
            y: 11
            text: "· " + root.agents.count
            color: Fmt.alpha(root.colors.bright, 0.6)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 11
          }

          Item {
            id: refreshButton
            anchors.right: parent.right
            y: 5
            width: 26
            height: 26
            opacity: refreshHover.hovered ? 1 : 0.8

            HoverHandler { id: refreshHover }
            Text {
              id: refreshIcon
              anchors.centerIn: parent
              text: "↻"
              color: root.agents.refreshing ? root.colors.accent : Fmt.alpha(root.colors.bright, 0.74)
              font.family: "JetBrainsMono Nerd Font"
              font.pixelSize: 15
              RotationAnimation on rotation {
                running: root.agents.refreshing
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
              }
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.agents.refresh(true)
            }
          }
        }

        Item {
          width: parent.width
          height: 28

          Text {
            x: 0
            y: 6
            text: "今日总消耗"
            color: Fmt.alpha(root.colors.bright, 0.48)
            font.family: "Noto Sans CJK SC"
            font.pixelSize: 10
            font.letterSpacing: 0.5
          }
          Text {
            anchors.right: parent.right
            y: 2
            text: root.todayTotalTokens >= 0 ? Fmt.tokens(root.todayTotalTokens) : "--"
            color: root.colors.accent
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 16
            font.weight: Font.DemiBold
          }
        }

        Repeater {
          model: root.agents.visibleAgents

          delegate: Column {
            id: agentDelegate
            required property var modelData
            width: parent.width

            AgentRow {
              width: parent.width
              theme: root.theme
              agent: agentDelegate.modelData
            }
            Divider { width: parent.width; color: Fmt.alpha(root.colors.fg, 0.16) }
          }
        }

        Text {
          visible: root.agents.count === 0
          width: parent.width
          height: visible ? implicitHeight + 16 : 0
          text: "暂无 Agent 数据，等待首次采集"
          color: Fmt.alpha(root.colors.bright, 0.74)
          font.family: "Noto Sans CJK SC"
          font.pixelSize: 11
          wrapMode: Text.Wrap
        }
      }
    }
  }
}
