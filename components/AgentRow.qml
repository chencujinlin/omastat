pragma ComponentBehavior: Bound
import QtQuick
import "../lib/Format.js" as Fmt
import "../lib/Palette.js" as Palette

Item {
  id: root

  property var theme: null
  property var agent: ({})
  property double nowMs: Date.now()

  readonly property color accent: Palette.agent(agent.id, theme.colors)
  readonly property var limit: agent.bestLimit || null
  readonly property bool isDsh: agent.id === "deepseek-harness"
  readonly property var apiBalance: agent.apiBalance || null
  readonly property bool hasBalance: root.apiBalance !== null
    && root.apiBalance.total !== null && root.apiBalance.total !== undefined
  readonly property string balanceText: root.hasBalance
    ? Fmt.money(root.apiBalance.currency, root.apiBalance.total) : "--"
  readonly property string quotaText: root.limit ? Math.round(root.limit.percent * 100) + "%" : "无"
  readonly property string consumeText: agent.todayTokens === null || agent.todayTokens === undefined
    ? "--" : Fmt.tokens(agent.todayTokens)

  implicitHeight: body.implicitHeight + 20

  Column {
    id: body
    y: 10
    width: parent.width
    spacing: 8

    Item {
      width: parent.width
      height: 30

      AgentMark {
        agentId: root.agent.id || ""
        fallback: Palette.monogram(root.agent.id)
        accent: root.accent
        theme: root.theme
      }

      Text {
        x: 42
        anchors.verticalCenter: parent.verticalCenter
        text: root.agent.name || "Agent"
        color: root.theme.colors.bright
        font.family: "Noto Sans CJK SC"
        font.pixelSize: 15
        font.weight: Font.DemiBold
      }
    }

    Row {
      width: parent.width
      spacing: 12

      MetricCell {
        width: (parent.width - 12) / 2
        theme: root.theme
        label: root.isDsh ? "余额" : "额度"
        value: root.isDsh ? root.balanceText : root.quotaText
        valueColor: root.isDsh
          ? (root.hasBalance && root.apiBalance.state === "ok"
              ? root.accent : Fmt.alpha(root.theme.colors.bright, 0.6))
          : (root.limit ? root.accent : Fmt.alpha(root.theme.colors.bright, 0.6))
        showBar: root.isDsh ? false : root.limit !== null
        barValue: root.limit ? root.limit.percent : 0
        accent: root.accent
      }
      MetricCell {
        width: (parent.width - 12) / 2
        theme: root.theme
        label: "消耗量"
        value: root.consumeText
        valueColor: root.theme.colors.bright
      }
    }

    Row {
      width: parent.width
      spacing: 12

      MetricCell {
        width: (parent.width - 12) / 2
        theme: root.theme
        label: "首字"
        value: Fmt.ttft(root.agent.ttftSeconds)
        valueColor: root.theme.colors.bright
      }
      MetricCell {
        width: (parent.width - 12) / 2
        theme: root.theme
        label: "平均速度"
        value: Fmt.speed(root.agent.tokensPerSecond)
        valueColor: root.theme.colors.bright
      }
    }
  }
}
