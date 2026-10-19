pragma ComponentBehavior: Bound
import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property string kind: "cpu"
  property color color: "#7aa2f7"

  implicitWidth: 14
  implicitHeight: 14

  // CPU: a chip with pins on four sides.
  Item {
    anchors.fill: parent
    visible: root.kind === "cpu"

    Rectangle {
      x: 2; y: 2; width: 10; height: 10; radius: 2
      color: "transparent"
      border.width: 1
      border.color: root.color
    }
    Rectangle {
      x: 5; y: 5; width: 4; height: 4; radius: 1
      color: Fmt.alpha(root.color, 0.55)
    }
    Repeater {
      model: 3
      Rectangle {
        required property int index
        x: 3.2 + index * 3.2; y: 0; width: 1.2; height: 2
        color: root.color
      }
    }
    Repeater {
      model: 3
      Rectangle {
        required property int index
        x: 3.2 + index * 3.2; y: 12; width: 1.2; height: 2
        color: root.color
      }
    }
    Repeater {
      model: 2
      Rectangle {
        required property int index
        x: 0; y: 4 + index * 4; width: 2; height: 1.2
        color: root.color
      }
    }
    Repeater {
      model: 2
      Rectangle {
        required property int index
        x: 12; y: 4 + index * 4; width: 2; height: 1.2
        color: root.color
      }
    }
  }

  // GPU: a card with a fan and a bracket.
  Item {
    anchors.fill: parent
    visible: root.kind === "gpu"

    Rectangle {
      x: 1; y: 2; width: 12; height: 9; radius: 2
      color: "transparent"
      border.width: 1
      border.color: root.color
    }
    Rectangle {
      x: 5; y: 5; width: 4; height: 4; radius: 2
      color: "transparent"
      border.width: 1
      border.color: Fmt.alpha(root.color, 0.8)
    }
    Rectangle { x: 5.4; y: 5.4; width: 1; height: 1; radius: 0.5; color: root.color }
    Rectangle { x: 7.7; y: 5.4; width: 1; height: 1; radius: 0.5; color: root.color }
    Rectangle { x: 5.4; y: 7.7; width: 1; height: 1; radius: 0.5; color: root.color }
    Rectangle { x: 7.7; y: 7.7; width: 1; height: 1; radius: 0.5; color: root.color }
    Rectangle { x: 4; y: 11; width: 1.5; height: 2; color: root.color }
    Rectangle { x: 8.5; y: 11; width: 1.5; height: 2; color: root.color }
  }

  // Memory: a module with three slots.
  Item {
    anchors.fill: parent
    visible: root.kind === "mem"

    Rectangle {
      x: 1; y: 2.5; width: 12; height: 9; radius: 2
      color: "transparent"
      border.width: 1
      border.color: root.color
    }
    Repeater {
      model: 3
      Rectangle {
        required property int index
        x: 3.5; y: 4.7 + index * 2.2; width: 7; height: 1.1; radius: 0.55
        color: Fmt.alpha(root.color, index === 0 ? 0.9 : 0.5)
      }
    }
    Rectangle { x: 4; y: 11.5; width: 2; height: 2; color: root.color }
    Rectangle { x: 8; y: 11.5; width: 2; height: 2; color: root.color }
  }

  // Disk: three platters in a stack.
  Item {
    anchors.fill: parent
    visible: root.kind === "disk"

    Repeater {
      model: 3
      Rectangle {
        required property int index
        x: 1.5; y: 1.5 + index * 4; width: 11; height: 3; radius: 1.2
        color: index === 0 ? Fmt.alpha(root.color, 0.22) : "transparent"
        border.width: 1
        border.color: root.color
      }
    }
    Rectangle { x: 10; y: 6.1; width: 1.2; height: 1.2; radius: 0.6; color: root.color }
  }
}
