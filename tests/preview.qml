import QtQuick
import Quickshell
import "../" as App
import "../services" as Services
import "../components" as Components

ShellRoot {
  FloatingWindow {
    implicitWidth: Number(Quickshell.env("OMASTAT_PREVIEW_WIDTH") || 360)
    implicitHeight: 920
    visible: true
    color: "transparent"
    Services.Theme { id: themeService }
    Services.System { id: systemService }
    Services.Agents { id: agentsService }
    App.Config { id: cfg }
    Components.GlassCard {
      id: card
      anchors.fill: parent
      theme: themeService
      App.Vitals {
        id: view
        anchors.fill: parent
        anchors.margins: 16
        theme: themeService
        system: systemService
        agents: agentsService
        config: cfg
      }
    }
    Timer {
      interval: 3500; running: true
      onTriggered: {
        view.flickable.contentY = Number(Quickshell.env("OMASTAT_PREVIEW_SCROLL") || 0)
        capture.start()
      }
    }
    Timer {
      id: capture; interval: 500
      onTriggered: card.grabToImage(function(result) {
        result.saveToFile(Quickshell.env("OMASTAT_PREVIEW_PATH"))
        Quickshell.execDetached(["kill", "-TERM", String(Quickshell.processId)])
      })
    }
  }
}
