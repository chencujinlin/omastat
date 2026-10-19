.pragma library

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value))
}

function percent(value) {
  if (value === null || value === undefined || isNaN(value)) return "--"
  return Math.round(clamp(Number(value), 0, 100)) + "%"
}

function temp(value) {
  if (value === null || value === undefined || isNaN(value) || value < 0) return ""
  return Math.round(Number(value)) + "°C"
}

function ghz(value) {
  if (value === null || value === undefined || isNaN(value) || value <= 0) return ""
  return Number(value).toFixed(1) + " GHz"
}

function mhz(value) {
  if (value === null || value === undefined || isNaN(value) || value <= 0) return ""
  return Math.round(Number(value)) + " MHz"
}

function gb(value) {
  if (value === null || value === undefined || isNaN(value)) return "暂无数据"
  var n = Number(value)
  if (n >= 100) return Math.round(n).toString()
  if (n >= 10) return n.toFixed(1)
  return n.toFixed(2)
}

function memoryMeta(used, total) {
  return gb(used) + " / " + gb(total) + " G"
}

function diskMeta(used, total) {
  return gb(used) + " / " + gb(total) + " G"
}

function tokens(value) {
  if (value === null || value === undefined) return "暂无数据"
  var n = Number(value || 0)
  if (!isFinite(n) || n < 0) return "暂无数据"
  if (n >= 100000000) {
    var yi = n / 100000000
    return yi.toFixed(yi >= 10 ? 1 : 2).replace(/\.?0+$/, "") + "亿"
  }
  if (n >= 10000000) return Math.round(n / 1000000) + "M"
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M"
  if (n >= 1000) return Math.round(n / 1000) + "K"
  return Math.round(n).toString()
}

function calls(value) {
  if (value === null || value === undefined) return "暂无数据"
  var n = Number(value)
  if (!isFinite(n) || n < 0) return "暂无数据"
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M"
  if (n >= 10000) return Math.round(n / 1000) + "K"
  return Math.round(n).toString()
}

function reset(iso, nowMs) {
  if (!iso) return ""
  var at = Date.parse(iso)
  if (isNaN(at)) return ""
  var delta = at - (nowMs || Date.now())
  if (delta <= 0) return "已重置"
  var minutes = Math.floor(delta / 60000)
  if (minutes < 1) return "不足1分"
  if (minutes < 60) return minutes + "分"
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return hours + "小时" + (minutes % 60) + "分"
  var days = Math.floor(hours / 24)
  return days + "天" + (hours % 24) + "小时"
}

function limitShort(label) {
  var text = String(label || "").toLowerCase()
  if (text.indexOf("week") >= 0) return "周"
  if (text.indexOf("5") >= 0 && text.indexOf("hour") >= 0) return "5时"
  if (text.indexOf("day") >= 0) return "日"
  if (text.indexOf("month") >= 0) return "月"
  if (text.indexOf("session") >= 0) return "5时"
  return "期"
}

function age(ms, nowMs) {
  if (!ms || ms <= 0) return "从未"
  var delta = Math.max(0, (nowMs || Date.now()) - ms)
  var minutes = Math.floor(delta / 60000)
  if (minutes < 1) return "刚刚"
  if (minutes < 60) return minutes + "分钟前"
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return hours + "小时前"
  return Math.floor(hours / 24) + "天前"
}

function uptime(seconds) {
  var s = Math.max(0, Number(seconds || 0))
  var days = Math.floor(s / 86400)
  var hours = Math.floor((s % 86400) / 3600)
  var minutes = Math.floor((s % 3600) / 60)
  if (days > 0) return days + "天" + hours + "小时"
  if (hours > 0) return hours + "小时" + minutes + "分"
  return Math.max(1, minutes) + "分"
}

function clock(nowMs) {
  var d = new Date(nowMs || Date.now())
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0")
}

function dateLabel(nowMs) {
  var d = new Date(nowMs || Date.now())
  var days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
  return days[d.getDay()] + " · " + d.getDate() + "日"
}

function fullDate(nowMs) {
  var d = new Date(nowMs || Date.now())
  var days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
  return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + days[d.getDay()]
}

function ttft(value) {
  if (value === null || value === undefined || isNaN(Number(value)) || Number(value) <= 0) return "--"
  var n = Number(value)
  return (n < 10 ? n.toFixed(2) : n.toFixed(1)) + "s"
}

function money(currency, value) {
  if (value === null || value === undefined || isNaN(Number(value))) return "--"
  var code = String(currency || "").toUpperCase()
  var prefix = code === "CNY" ? "¥" : code === "USD" ? "$" : (code ? code + " " : "")
  return prefix + Number(value).toFixed(2)
}

function speed(value) {
  if (value === null || value === undefined || isNaN(Number(value)) || Number(value) <= 0) return "--"
  var n = Number(value)
  if (n >= 1000) return (n / 1000).toFixed(1) + "k tok/s"
  return Math.round(n) + " tok/s"
}

function alpha(color, opacity) {
  if (!color) return Qt.rgba(1, 1, 1, opacity)
  var c = typeof color === "string" ? Qt.color(color) : color
  return Qt.rgba(c.r, c.g, c.b, opacity)
}

function fileUrl(path) {
  if (!path) return ""
  var parts = String(path).split("/")
  for (var i = 0; i < parts.length; i++) parts[i] = encodeURIComponent(parts[i])
  return "file://" + parts.join("/")
}

function stateLabel(state) {
  return ({normal: "正常", stale: "已过期", error: "异常", unknown: "未知"})[state] || "未知"
}

function stateColor(state, colors) {
  return state === "normal" ? colors.green : state === "stale" ? colors.yellow
    : state === "error" ? colors.red : colors.fg
}

function bytesPerSecond(value) {
  if (value === null || value === undefined) return "暂无数据"
  if (value >= 1048576) return (value / 1048576).toFixed(1) + " MiB/s"
  return (value / 1024).toFixed(1) + " KiB/s"
}
