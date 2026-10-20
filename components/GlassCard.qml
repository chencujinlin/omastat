import QtQuick
import Quickshell.Widgets
import "../lib/Format.js" as Fmt

// Frosted glass by default: the wallpaper is loaded at a low resolution and
// smoothly upscaled, then graded under a dark tint. That keeps the look at
// full-screen sizes without repainting a full-screen blur pass. Flat themes
// (orange) skip the wallpaper, grain and translucent grade entirely.
Item {
  id: root

  property var theme: null
  property var screenInfo: null
  property int radius: 18

  default property alias contentData: holder.data

  readonly property var colors: theme ? theme.colors : ({
    accent: "#7aa2f7", blue: "#7aa2f7", magenta: "#bb9af7", cyan: "#7dcfff",
    green: "#9ece6a", yellow: "#e0af68", orange: "#ff9e64", red: "#f7768e",
    fg: "#a9b1d6", bright: "#c0caf5", muted: "#565f89",
    bg: "#1a1b26", darkBg: "#0e0e14", lightBg: "#24283b"
  })
  readonly property bool dark: theme ? theme.isDark : true
  readonly property bool glass: theme ? theme.glass !== false : true

  ClippingRectangle {
    id: clip
    anchors.fill: parent
    radius: root.radius
    color: "transparent"
    border.width: 1
    border.color: root.glass
      ? Fmt.alpha(root.colors.bright, root.dark ? 0.22 : 0.45)
      : Fmt.alpha(root.colors.accent, root.dark ? 0.3 : 0.22)

    Image {
      anchors.fill: parent
      visible: root.glass
      source: root.glass && root.theme ? root.theme.wallpaperSource : ""
      sourceSize: Qt.size(28, 21)
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: false
      smooth: true
      mipmap: true
      opacity: visible && status === Image.Ready ? 0.18 : 0
    }

    Rectangle {
      anchors.fill: parent
      visible: root.glass
      gradient: Gradient {
        GradientStop { position: 0.0; color: Fmt.alpha(root.colors.darkBg, 0.88) }
        GradientStop { position: 0.4; color: Fmt.alpha(root.colors.bg, 0.92) }
        GradientStop { position: 1.0; color: Fmt.alpha(root.colors.darkBg, 0.95) }
      }
    }

    Rectangle {
      anchors.fill: parent
      visible: !root.glass
      gradient: Gradient {
        GradientStop { position: 0.0; color: root.colors.darkBg }
        GradientStop { position: 0.45; color: root.colors.bg }
        GradientStop { position: 1.0; color: root.colors.darkBg }
      }
    }

    Rectangle {
      width: parent.width
      height: 200
      visible: root.glass
      gradient: Gradient {
        GradientStop { position: 0.0; color: Fmt.alpha(root.colors.accent, 0.055) }
        GradientStop { position: 0.5; color: Fmt.alpha(root.colors.accent, 0.014) }
        GradientStop { position: 1.0; color: Fmt.alpha(root.colors.accent, 0.0) }
      }
    }

    Rectangle {
      x: 24
      y: 1
      width: Math.max(0, parent.width - 48)
      height: 1
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0.0; color: Fmt.alpha(root.glass ? root.colors.bright : root.colors.accent, 0.0) }
        GradientStop { position: 0.35; color: Fmt.alpha(root.glass ? root.colors.bright : root.colors.accent, root.glass ? 0.42 : 0.5) }
        GradientStop { position: 0.65; color: Fmt.alpha(root.glass ? root.colors.bright : root.colors.accent, root.glass ? 0.42 : 0.5) }
        GradientStop { position: 1.0; color: Fmt.alpha(root.glass ? root.colors.bright : root.colors.accent, 0.0) }
      }
    }

    Image {
      anchors.fill: parent
      visible: root.glass
      source: "../assets/grain.png"
      fillMode: Image.Tile
      opacity: 0.03
      smooth: false
    }

    Item {
      id: holder
      anchors.fill: parent
    }
  }
}
