import QtQuick
import "../lib/Format.js" as Fmt

// Small pill switch used by the settings page. The checked value is owned by
// the caller (it is usually bound to Config); tapping only emits the requested
// new value so the binding is never broken.
Item {
  id: root

  property var theme: null
  property bool checked: false
  signal toggled(bool checked)

  readonly property var colors: theme ? theme.colors : ({
    accent: "#7aa2f7", fg: "#a9b1d6", bright: "#c0caf5", darkBg: "#0e0e14"
  })
  readonly property bool dark: theme ? theme.isDark : true

  implicitWidth: 38
  implicitHeight: 22

  HoverHandler { cursorShape: Qt.PointingHandCursor }

  Rectangle {
    id: track
    anchors.fill: parent
    radius: height / 2
    color: root.checked ? Fmt.alpha(root.colors.accent, 0.82) : Fmt.alpha(root.colors.fg, 0.16)
    border.width: 1
    border.color: root.checked ? Fmt.alpha(root.colors.accent, 0.9) : Fmt.alpha(root.colors.fg, 0.24)

    Behavior on color { ColorAnimation { duration: 120 } }
  }

  Rectangle {
    id: knob
    width: 16
    height: 16
    radius: 8
    y: (parent.height - height) / 2
    x: root.checked ? parent.width - width - 3 : 3
    color: root.checked
      ? (root.dark ? root.colors.bright : "#ffffff")
      : Fmt.alpha(root.colors.bright, root.dark ? 0.82 : 0.7)

    Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: 120 } }
  }

  TapHandler {
    onTapped: root.toggled(!root.checked)
  }
}
