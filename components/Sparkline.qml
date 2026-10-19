import QtQuick
import "../lib/Format.js" as Fmt

Item {
  id: root

  property var values: []
  property var times: []
  onTimesChanged: canvas.requestPaint()
  property color stroke: "#7aa2f7"
  property real fillOpacity: 0.12
  property real lineWidth: 1.4
  property real maxValue: 0

  onVisibleChanged: if (visible) canvas.requestPaint()
  onValuesChanged: canvas.requestPaint()
  onWidthChanged: canvas.requestPaint()
  onHeightChanged: canvas.requestPaint()
  onStrokeChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    antialiasing: true

    onPaint: {
      var ctx = getContext("2d")
      ctx.clearRect(0, 0, width, height)
      var data = root.values
      if (!data || data.length === 0 || !root.visible) return

      var max = root.maxValue > 0 ? root.maxValue : 1
      if (root.maxValue <= 0) {
        for (var i = 0; i < data.length; i++) {
          var value = Number(data[i])
          if (isFinite(value) && value > max) max = value
        }
      }
      if (max <= 0) max = 1

      var w = width
      var h = height
      var pad = root.lineWidth
      var usable = Math.max(1, h - pad * 2)
      var step = w / 59
      var start = Math.max(0, w - step * (data.length - 1))
      var timed = root.times && root.times.length === data.length
      var endTime = timed ? root.times[root.times.length - 1] : 0

      var connected = false
      ctx.beginPath()
      for (var j = 0; j < data.length; j++) {
        if (data[j] === null || data[j] === undefined) { connected = false; continue }
        var v = Math.max(0, Math.min(max, Number(data[j] || 0)))
        var x = timed ? w * (1 - (endTime - root.times[j]) / 60000) : start + step * j
        if (timed && j > 0 && root.times[j] - root.times[j - 1] > 2000) connected = false
        var y = pad + usable - (v / max) * usable
        if (!connected) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
        connected = true
      }

      if (root.fillOpacity > 0 && data.indexOf(null) < 0) {
        ctx.save()
        ctx.lineTo(w, h)
        ctx.lineTo(0, h)
        ctx.closePath()
        ctx.fillStyle = Fmt.alpha(root.stroke, root.fillOpacity)
        ctx.fill()
        ctx.restore()
      }

      connected = false
      ctx.beginPath()
      for (var k = 0; k < data.length; k++) {
        if (data[k] === null || data[k] === undefined) { connected = false; continue }
        var value2 = Math.max(0, Math.min(max, Number(data[k] || 0)))
        var x2 = timed ? w * (1 - (endTime - root.times[k]) / 60000) : start + step * k
        if (timed && k > 0 && root.times[k] - root.times[k - 1] > 2000) connected = false
        var y2 = pad + usable - (value2 / max) * usable
        if (!connected) ctx.moveTo(x2, y2)
        else ctx.lineTo(x2, y2)
        connected = true
      }
      ctx.strokeStyle = root.stroke
      ctx.lineWidth = root.lineWidth
      ctx.lineJoin = "round"
      ctx.lineCap = "round"
      ctx.stroke()
    }
  }
}
