import QtQuick

Item {
  id: root

  property real value: 0
  property color color: "#7aa2f7"
  property color trackColor: "#1AFFFFFF"
  property int thickness: 3

  implicitHeight: thickness

  Rectangle {
    anchors.fill: parent
    radius: height / 2
    color: root.trackColor
  }

  Rectangle {
    height: parent.height
    radius: height / 2
    width: root.value > 0
      ? Math.max(2, parent.width * Math.max(0, Math.min(1, root.value)))
      : 0
    color: root.color
  }
}
