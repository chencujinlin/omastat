.pragma library

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
  var names = {
    "codex": "CX",
    "deepseek-harness": "DS",
    "opencode": "OC",
    "claude": "CL",
    "pi": "PI",
    "fireworks": "FW"
  }
  return names[id] || String(id || "?").slice(0, 2).toUpperCase()
}

function displayName(id, record) {
  var names = {
    "codex": "Codex",
    "deepseek-harness": "DeepSeek Harness",
    "opencode": "OpenCode",
    "claude": "Claude Code",
    "pi": "Pi",
    "fireworks": "Fireworks"
  }
  if (names[id]) return names[id]
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
