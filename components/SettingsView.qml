pragma ComponentBehavior: Bound
import QtQuick
import "../lib/Format.js" as Fmt
import "../lib/Palette.js" as Palette
import "../lib/Themes.js" as Themes

// In-window settings page. Values are owned by Config; this page only emits
// changes, so every control immediately reflects the merged configuration.
Item {
  id: root

  property var theme: null
  property var config: null
  property var agents: null
  signal closeRequested()

  readonly property var colors: theme ? theme.colors : ({
    accent: "#7aa2f7", fg: "#a9b1d6", bright: "#c0caf5", muted: "#565f89",
    bg: "#1a1b26", darkBg: "#0e0e14", lightBg: "#24283b"
  })
  readonly property var autoColors: theme && theme.liveColors ? theme.liveColors : root.colors

  readonly property real sideMargin: width > 560 ? 20 : 12
  readonly property real contentWidth: Math.min(720, Math.max(0, width - sideMargin * 2))
  readonly property real contentX: (width - contentWidth) / 2

  Connections {
    target: root.config
    function onSaved() {
      if (root.agents) root.agents.refresh(true)
    }
  }

  function themeColors(id) {
    if (id === "auto") return root.autoColors
    var info = Themes.preset(id)
    return info ? info.colors : root.colors
  }

  function themeLabel(id) {
    if (id === "auto") return "跟随 Omarchy"
    var info = Themes.preset(id)
    return info ? info.label : id
  }

  function themeNote(id) {
    if (id === "auto") {
      return "当前 " + (root.theme && root.theme.themeName ? root.theme.themeName : "Omarchy") + " · 玻璃"
    }
    var info = Themes.preset(id)
    return info ? info.note : ""
  }

  function themeAccent(id) {
    var palette = root.themeColors(id)
    return palette && palette.accent ? palette.accent : root.colors.accent
  }

  function surfaceColor() {
    return root.theme && root.theme.glass === false
      ? root.colors.lightBg : Fmt.alpha(root.colors.lightBg, 0.5)
  }

  function surfaceBorder() {
    return Fmt.alpha(root.colors.fg, 0.16)
  }

  function snapshotFor(id) {
    var list = root.agents ? root.agents.visibleAgents : []
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === id) return list[i]
    }
    return null
  }

  function agentEnabled(id) {
    return root.config ? root.config.agents.indexOf(id) >= 0 : false
  }

  function quotaSummary(id) {
    if (!root.config) return ""
    if (!root.agentEnabled(id)) return "已隐藏"
    var row = root.snapshotFor(id)
    if (!row) return "等待采集"
    if (id === "deepseek-harness") {
      var api = row.apiBalance
      if (api && api.total !== null && api.total !== undefined)
        return "余额 " + Fmt.money(api.currency, api.total)
      return "余额暂不可用"
    }
    var prepaid = row.accountBalance
    if (prepaid && prepaid.remaining !== null && prepaid.remaining !== undefined)
      return "余额 " + Fmt.money(prepaid.currency, prepaid.remaining)
    if (row.bestLimit && row.bestLimit.percent !== null && row.bestLimit.percent !== undefined)
      return "额度 " + Math.round(Number(row.bestLimit.percent) * 100) + "%"
    var info = Palette.agentInfo(id)
    if (info && info.quota === "none") return "无额度接口"
    if (id === "fireworks") return "未配置额度"
    return "暂无额度"
  }

  function quotaColor(id) {
    var row = root.snapshotFor(id)
    if (row && row.state === "error") return root.colors.red
    return Fmt.alpha(root.colors.bright, 0.58)
  }

  // ------------------------------------------------------------- header

  Item {
    id: header
    x: root.contentX
    width: root.contentWidth
    height: 54

    Item {
      id: backButton
      width: 28
      height: 28
      y: 8

      HoverHandler {
        id: backHover
        cursorShape: Qt.PointingHandCursor
      }

      Rectangle {
        anchors.fill: parent
        radius: 6
        color: backHover.hovered ? Fmt.alpha(root.colors.bright, 0.08) : "transparent"
      }

      Text {
        anchors.centerIn: parent
        text: "←"
        color: root.colors.bright
        font.family: "JetBrainsMono Nerd Font"
        font.pixelSize: 16
      }

      TapHandler { onTapped: root.closeRequested() }
    }

    Text {
      x: 38
      y: 0
      text: "设置"
      color: root.colors.bright
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 19
      font.weight: Font.DemiBold
    }

    Text {
      x: 39
      y: 27
      text: "显示与 AGENTS"
      color: Fmt.alpha(root.colors.bright, 0.5)
      font.family: "JetBrainsMono Nerd Font"
      font.pixelSize: 9
      font.letterSpacing: 1.2
    }

    Text {
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      text: root.config && root.config.saveError.length > 0 ? "保存失败" : "自动保存"
      color: root.config && root.config.saveError.length > 0
        ? root.colors.red : Fmt.alpha(root.colors.bright, 0.48)
      font.family: "Noto Sans CJK SC"
      font.pixelSize: 9
    }

    Rectangle {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      height: 1
      color: Fmt.alpha(root.colors.fg, 0.14)
    }
  }

  // ------------------------------------------------------------- content

  Flickable {
    id: flick
    x: root.contentX
    width: root.contentWidth
    anchors.top: header.bottom
    anchors.bottom: parent.bottom
    contentWidth: width
    contentHeight: content.height + 20
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick

    Column {
      id: content
      width: flick.width
      spacing: 0

      // Appearance -------------------------------------------------
      Item {
        width: parent.width
        height: 38

        Row {
          y: 14
          spacing: 8
          Text {
            text: "外观"
            color: Fmt.alpha(root.colors.bright, 0.88)
            font.family: "Noto Sans CJK SC"
            font.pixelSize: 12
            font.weight: Font.DemiBold
          }
          Text {
            y: 1
            text: "APPEARANCE"
            color: Fmt.alpha(root.colors.bright, 0.36)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
            font.letterSpacing: 1.4
          }
        }
      }

      Grid {
        id: themeGrid
        width: parent.width
        columns: 2
        columnSpacing: 10
        rowSpacing: 10

        Repeater {
          model: Themes.order

          delegate: Item {
            id: themeTile
            required property string modelData
            width: (themeGrid.width - themeGrid.columnSpacing) / 2
            height: 82

            readonly property var tileColors: root.themeColors(themeTile.modelData)
            readonly property color tileAccent: root.themeAccent(themeTile.modelData)
            readonly property bool selected: root.theme && root.theme.mode === themeTile.modelData

            Rectangle {
              anchors.fill: parent
              radius: 10
              color: themeTile.selected
                ? Fmt.alpha(themeTile.tileAccent, 0.14)
                : Fmt.alpha(root.colors.bright, 0.035)
              border.width: themeTile.selected ? 1.5 : 1
              border.color: themeTile.selected ? themeTile.tileAccent : root.surfaceBorder()
            }

            Row {
              x: 12
              y: 11
              spacing: 4
              Rectangle { width: 13; height: 13; radius: 3; color: themeTile.tileColors.darkBg || root.colors.darkBg }
              Rectangle { width: 13; height: 13; radius: 3; color: themeTile.tileColors.accent || root.colors.accent }
              Rectangle { width: 13; height: 13; radius: 3; color: themeTile.tileColors.bright || root.colors.bright }
            }

            Text {
              x: 12
              y: 33
              width: parent.width - 34
              text: root.themeLabel(themeTile.modelData)
              color: root.colors.bright
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 12
              font.weight: themeTile.selected ? Font.DemiBold : Font.Normal
              elide: Text.ElideRight
            }
            Text {
              x: 12
              y: 55
              width: parent.width - 22
              text: root.themeNote(themeTile.modelData)
              color: Fmt.alpha(root.colors.bright, 0.52)
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 9
              elide: Text.ElideRight
            }
            Text {
              anchors.right: parent.right
              anchors.rightMargin: 11
              y: 10
              visible: themeTile.selected
              text: "✓"
              color: themeTile.tileAccent
              font.family: "JetBrainsMono Nerd Font"
              font.pixelSize: 12
            }
            TapHandler { onTapped: if (root.config) root.config.setTheme(themeTile.modelData) }
          }
        }
      }

      Item { width: parent.width; height: 18 }

      // Display ----------------------------------------------------
      Item {
        width: parent.width
        height: 38

        Row {
          y: 14
          spacing: 8
          Text {
            text: "显示"
            color: Fmt.alpha(root.colors.bright, 0.88)
            font.family: "Noto Sans CJK SC"
            font.pixelSize: 12
            font.weight: Font.DemiBold
          }
          Text {
            y: 1
            text: "DISPLAY"
            color: Fmt.alpha(root.colors.bright, 0.36)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
            font.letterSpacing: 1.4
          }
        }
      }

      Rectangle {
        width: parent.width
        height: displayColumn.height
        radius: 10
        color: root.surfaceColor()
        border.width: 1
        border.color: root.surfaceBorder()

        Column {
          id: displayColumn
          width: parent.width

          Item {
            width: parent.width
            height: 54

            Text {
              x: 14
              y: 8
              text: "系统资源"
              color: root.colors.bright
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 12
            }
            Text {
              x: 14
              y: 28
              width: parent.width - 80
              text: "CPU、GPU、内存与磁盘"
              color: Fmt.alpha(root.colors.bright, 0.5)
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 9
              elide: Text.ElideRight
            }
            ToggleSwitch {
              anchors.right: parent.right
              anchors.rightMargin: 14
              anchors.verticalCenter: parent.verticalCenter
              theme: root.theme
              checked: root.config ? root.config.showSystem : true
              onToggled: function(value) { if (root.config) root.config.setSection("system", value) }
            }
          }

          Rectangle { width: parent.width; height: 1; color: root.surfaceBorder() }

          Item {
            width: parent.width
            height: 54

            Text {
              x: 14
              y: 8
              text: "Agent 用量"
              color: root.colors.bright
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 12
            }
            Text {
              x: 14
              y: 28
              width: parent.width - 80
              text: "额度、消耗、首字与平均速度"
              color: Fmt.alpha(root.colors.bright, 0.5)
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 9
              elide: Text.ElideRight
            }
            ToggleSwitch {
              anchors.right: parent.right
              anchors.rightMargin: 14
              anchors.verticalCenter: parent.verticalCenter
              theme: root.theme
              checked: root.config ? root.config.showAgents : true
              onToggled: function(value) { if (root.config) root.config.setSection("agents", value) }
            }
          }

          Rectangle { width: parent.width; height: 1; color: root.surfaceBorder() }

          Item {
            width: parent.width
            height: 54

            Text {
              x: 14
              y: 8
              text: "天气条"
              color: root.colors.bright
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 12
            }
            Text {
              x: 14
              y: 28
              width: parent.width - 80
              text: "关闭后停止天气请求"
              color: Fmt.alpha(root.colors.bright, 0.5)
              font.family: "Noto Sans CJK SC"
              font.pixelSize: 9
              elide: Text.ElideRight
            }
            ToggleSwitch {
              anchors.right: parent.right
              anchors.rightMargin: 14
              anchors.verticalCenter: parent.verticalCenter
              theme: root.theme
              checked: root.config ? root.config.showWeather : true
              onToggled: function(value) { if (root.config) root.config.setSection("weather", value) }
            }
          }
        }
      }

      Item { width: parent.width; height: 18 }

      // Agents -----------------------------------------------------
      Item {
        width: parent.width
        height: 38

        Row {
          y: 14
          spacing: 8
          Text {
            text: "Agents"
            color: Fmt.alpha(root.colors.bright, 0.88)
            font.family: "Noto Sans CJK SC"
            font.pixelSize: 12
            font.weight: Font.DemiBold
          }
          Text {
            y: 1
            text: "USAGE & QUOTA"
            color: Fmt.alpha(root.colors.bright, 0.36)
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 9
            font.letterSpacing: 1.4
          }
        }
      }

      Rectangle {
        width: parent.width
        height: agentColumn.height
        radius: 10
        color: root.surfaceColor()
        border.width: 1
        border.color: root.surfaceBorder()

        Column {
          id: agentColumn
          width: parent.width

          Repeater {
            model: Palette.allAgentIds()

            delegate: Item {
              id: agentItem
              required property string modelData
              required property int index
              width: parent.width
              height: 64

              readonly property var info: Palette.agentInfo(agentItem.modelData)
              readonly property var agentRow: root.snapshotFor(agentItem.modelData)
              readonly property bool enabled: root.agentEnabled(agentItem.modelData)

              AgentMark {
                id: agentMark
                x: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 28
                height: 28
                agentId: agentItem.modelData
                fallback: Palette.monogram(agentItem.modelData)
                accent: Palette.agent(agentItem.modelData, root.colors)
                theme: root.theme
              }

              Text {
                x: 52
                y: 9
                width: parent.width - 118
                text: agentItem.info ? agentItem.info.name : agentItem.modelData
                color: root.colors.bright
                font.family: "Noto Sans CJK SC"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                elide: Text.ElideRight
              }
              Text {
                x: 52
                y: 27
                width: parent.width - 118
                text: agentItem.info ? agentItem.info.note : ""
                color: Fmt.alpha(root.colors.bright, 0.46)
                font.family: "Noto Sans CJK SC"
                font.pixelSize: 9
                elide: Text.ElideRight
              }
              Text {
                x: 52
                y: 43
                width: parent.width - 118
                text: root.quotaSummary(agentItem.modelData)
                color: root.quotaColor(agentItem.modelData)
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 9
                elide: Text.ElideRight
              }

              ToggleSwitch {
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                theme: root.theme
                checked: agentItem.enabled
                onToggled: function(value) {
                  if (root.config) root.config.setAgentEnabled(agentItem.modelData, value)
                }
              }

              Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: root.surfaceBorder()
                visible: agentItem.index < Palette.allAgentIds().length - 1
              }
            }
          }
        }
      }

      Text {
        width: parent.width
        y: 8
        height: 30
        text: "关闭 Agent 后不再采集其数据，也不计入今日总消耗；重新开启后会在下次采集时显示。"
        color: Fmt.alpha(root.colors.bright, 0.42)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 9
        wrapMode: Text.Wrap
        lineHeight: 1.15
      }

      Item { width: parent.width; height: 12 }

      Item {
        width: parent.width
        height: 34

        HoverHandler {
          id: resetHover
          cursorShape: Qt.PointingHandCursor
        }

        Rectangle {
          width: 132
          height: 30
          radius: 7
          color: resetHover.hovered ? Fmt.alpha(root.colors.bright, 0.08) : "transparent"
          border.width: 1
          border.color: resetHover.hovered ? Fmt.alpha(root.colors.accent, 0.5) : root.surfaceBorder()
        }
        Text {
          x: 13
          y: 8
          text: "恢复默认显示"
          color: resetHover.hovered ? root.colors.accent : Fmt.alpha(root.colors.bright, 0.72)
          font.family: "Noto Sans CJK SC"
          font.pixelSize: 10
        }
        TapHandler { onTapped: if (root.config) root.config.resetDisplayDefaults() }
      }

      Text {
        width: parent.width
        height: 34
        text: "设置自动保存到 config.local.json（不进入 Git）。"
        color: Fmt.alpha(root.colors.bright, 0.32)
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 9
        wrapMode: Text.Wrap
      }
    }
  }
}
