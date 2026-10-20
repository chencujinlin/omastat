.pragma library

// Canonical agent list. Order here is the display order everywhere: Config
// defaults, the settings page and the snapshot emitted by the Python reader.
var agents = [
  { id: "deepseek-harness", name: "DeepSeek Harness", short: "DSH", quota: "balance",
    note: "余额来自 DSH 登录账号；消耗与性能来自本机会话" },
  { id: "codex", name: "Codex", short: "CX", quota: "limits",
    note: "额度来自 Codex 登录态；首字与速度来自本地会话" },
  { id: "opencode", name: "OpenCode", short: "OC", quota: "none",
    note: "本地用量；没有额度接口" },
  { id: "claude", name: "Claude Code", short: "CL", quota: "limits",
    note: "额度来自 Claude 登录态；本地用量来自会话记录" },
  { id: "pi", name: "Pi", short: "PI", quota: "none",
    note: "本地用量；没有额度接口" },
  { id: "fireworks", name: "Fireworks", short: "FW", quota: "prepaid",
    note: "预付费余额；需要在 Omarchy Agents 中配置" }
]

function allAgentIds() {
  var result = []
  for (var i = 0; i < agents.length; i++) result.push(agents[i].id)
  return result
}

function agentInfo(id) {
  for (var i = 0; i < agents.length; i++) {
    if (agents[i].id === id) return agents[i]
  }
  return null
}

function system(kind, colors) {
  if (kind === "cpu") return colors.blue || colors.accent
  if (kind === "gpu") return colors.magenta || colors.accent
  if (kind === "mem") return colors.cyan || colors.accent
  if (kind === "disk") return colors.green || colors.accent
  return colors.accent
}

function agent(id, colors) {
  if (id === "codex") return colors.yellow || "#e0af68"
  if (id === "deepseek-harness") return colors.blue || "#7aa2f7"
  if (id === "opencode") return colors.magenta || "#bb9af7"
  if (id === "claude") return colors.red || "#f7768e"
  if (id === "pi") return colors.green || "#9ece6a"
  if (id === "fireworks") return colors.orange || "#ff9e64"
  return colors.accent
}

function monogram(id) {
  var info = agentInfo(id)
  return info ? info.short : String(id || "?").slice(0, 2).toUpperCase()
}

function displayName(id, record) {
  var info = agentInfo(id)
  if (info) return info.name
  var name = record && record.name ? String(record.name) : String(id || "Agent")
  return name.split(/\s+/)[0]
}

function planBadge(record) {
  var tier = String((record && record.tierLabel) || "").trim()
  if (!tier) return "本地"
  var lower = tier.toLowerCase()
  if (lower.indexOf("max") >= 0) return "最高"
  if (lower.indexOf("pro") >= 0) return "专业"
  if (lower.indexOf("free") >= 0) return "免费"
  if (lower.indexOf("plus") >= 0) return "Plus"
  if (tier.indexOf("本地") >= 0 || lower.indexOf("local") >= 0) return "本地"
  return tier.split(/[\s-]+/)[0].slice(0, 4)
}

// Quota fill is "used" (0..1). Low usage keeps the agent accent; near-limit
// windows turn warm so the strip can be read at a glance.
function quotaColor(percent, colors, accent) {
  if (percent >= 0.9) return colors.red || "#f7768e"
  if (percent >= 0.75) return colors.yellow || "#e0af68"
  return accent
}
