.pragma library

// Theme registry shared by Theme.qml, Config.qml and the settings page.
// "auto" intentionally has no entry: it follows the live Omarchy palette and
// keeps the frosted glass surface. Every named preset is a fixed flat palette.
var order = ["auto", "tokyo-night", "orange", "light"]

var presets = {
  "tokyo-night": {
    id: "tokyo-night",
    label: "Tokyo Night",
    note: "Omarchy 深蓝 · 纯色",
    dark: true,
    glass: false,
    radius: 10,
    colors: {
      accent: "#7aa2f7",
      blue: "#7aa2f7",
      magenta: "#bb9af7",
      cyan: "#7dcfff",
      green: "#9ece6a",
      yellow: "#e0af68",
      orange: "#ff9e64",
      red: "#f7768e",
      fg: "#a9b1d6",
      bright: "#c0caf5",
      muted: "#565f89",
      bg: "#1a1b26",
      darkBg: "#13141c",
      lightBg: "#24283b"
    }
  },
  "orange": {
    id: "orange",
    label: "橙色",
    note: "暖橙 · 纯色 · 无玻璃",
    dark: true,
    glass: false,
    radius: 10,
    colors: {
      accent: "#e68e0d",
      blue: "#e0a458",
      magenta: "#c97a5a",
      cyan: "#b8a58a",
      green: "#a3a86b",
      yellow: "#e3b341",
      orange: "#f0a04b",
      red: "#d9614c",
      fg: "#c9b9a8",
      bright: "#f4e7d6",
      muted: "#8b7561",
      bg: "#17120e",
      darkBg: "#0f0c09",
      lightBg: "#241b14"
    }
  },
  "light": {
    id: "light",
    label: "浅色",
    note: "Claude 风格 · 米黄 · 纯色",
    dark: false,
    glass: false,
    radius: 10,
    colors: {
      accent: "#b55436",
      blue: "#4c6b88",
      magenta: "#96566b",
      cyan: "#4f746e",
      green: "#6f7f4e",
      yellow: "#9a7b32",
      orange: "#c15f3c",
      red: "#b33a2b",
      fg: "#3d3d3a",
      bright: "#1f1e1d",
      muted: "#6b675e",
      bg: "#f0eee6",
      darkBg: "#e7e3d8",
      lightBg: "#e2ddd0"
    }
  }
}

function valid(id) {
  return order.indexOf(id) >= 0
}

function preset(id) {
  if (id === "auto" || !valid(id)) return null
  return presets[id]
}
