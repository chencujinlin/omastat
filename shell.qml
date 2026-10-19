import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "components"
import "services"

ShellRoot {
  id: root

  property bool shown: false
  property double nowMs: Date.now()
  property double barLeaseUntil: 0
  property string barMetric: "none"
  readonly property bool barNeedsSystem: barLeaseUntil > nowMs && (barMetric === "cpu" || barMetric === "memory")
  readonly property bool backgroundStart: Quickshell.env("OMASTAT_BACKGROUND") === "1"
  property bool intro: false
  property bool configApplied: false

  Config { id: cfg }
  Theme { id: themeService }
  System {
    id: systemService
    active: root.shown || root.barNeedsSystem
    intervalMs: root.shown ? 1000 : 5000
    keepHistory: root.shown
  }
  Agents { id: agentsService; config: cfg }
  Weather { id: weatherService; panelVisible: root.shown }

  readonly property var targetScreen: {
    var screens = Quickshell.screens
    if (!screens || screens.length === 0) return null
    if (cfg.output && cfg.output.length > 0) {
      for (var i = 0; i < screens.length; i++) {
        if (screens[i].name === cfg.output) return screens[i]
      }
    }
    return screens[0]
  }

  onConfigAppliedChanged: if (configApplied) shown = !cfg.startHidden && !root.backgroundStart

  Component.onCompleted: {
    introTimer.start()
    configAppliedTimer.start()
  }

  Timer {
    id: configAppliedTimer
    interval: 250
    repeat: false
    onTriggered: {
      root.configApplied = cfg.loaded
      if (cfg.loaded) root.shown = !cfg.startHidden && !root.backgroundStart
      else configAppliedTimer.restart()
    }
  }

  Timer {
    id: introTimer
    interval: 70
    repeat: false
    onTriggered: root.intro = true
  }

  Timer { interval: 5000; running: true; repeat: true; onTriggered: root.nowMs = Date.now() }

  // FloatingWindow is an ordinary top-level window; Hyprland owns placement.
  FloatingWindow {
    id: panel

    title: "Omastat"
    screen: root.targetScreen
    visible: root.shown
    implicitWidth: 380
    implicitHeight: 960
    minimumSize: Qt.size(320, 500)
    color: "transparent"
    surfaceFormat.opaque: false

    // If the compositor closes the window (SUPER+W), keep the IPC state in
    // sync so the next `omarchy-vitals show` can map it again.
    onVisibleChanged: if (!visible && root.shown) root.shown = false
    onClosed: root.shown = false

    GlassCard {
      id: card
      anchors.top: parent.top
      anchors.bottom: parent.bottom
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: 0
      anchors.rightMargin: 0
      radius: 18
      theme: themeService
      screenInfo: panel.screen
      opacity: root.intro ? 1 : 0

      Behavior on opacity {
        NumberAnimation { duration: 340; easing.type: Easing.OutCubic }
      }

      Vitals {
        anchors.fill: parent
        anchors.margins: 12
        theme: themeService
        system: systemService
        agents: agentsService
        weather: weatherService
        config: cfg
        panelVisible: root.shown
      }
    }
  }

  IpcHandler {
    target: "vitals"

    function ping(): string { return root.configApplied ? "ok" : "loading" }
    function open(): void { root.shown = true; root.intro = true }
    function close(): void { root.shown = false }
    function toggle(): void { root.shown = !root.shown; if (root.shown) root.intro = true }

    function refresh(): string {
      if (agentsService) agentsService.refresh(true)
      return "ok"
    }

    function bar(metric: string): string {
      root.barMetric = metric
      root.nowMs = Date.now()
      root.barLeaseUntil = root.nowMs + 45000
      return status()
    }

    function status(): string {
      return JSON.stringify({
        visible: root.shown, running: true, pid: Quickshell.processId,
        agents: agentsService.count, agentState: agentsService.health,
        cpu: systemService.cpuAvailable ? systemService.cpuPct : null,
        memory: systemService.memAvailable ? systemService.memPct : null,
        systemState: systemService.health, updated: systemService.updatedAtMs,
        quotas: agentsService.visibleAgents.map(function(a) {
          return {id: a.id, quota: a.bestLimit ? a.bestLimit.percent : null, state: a.quotaHealth,
            quotaState: a.quotaState, cached: a.cachedQuota}
        })
      })
    }

    function quit(): void {
      Quickshell.execDetached(["kill", "-TERM", String(Quickshell.processId)])
    }
  }
}
