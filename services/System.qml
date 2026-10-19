import QtQuick
import Quickshell.Io

Item {
  id: root
  visible: false
  property bool active: true
  property bool keepHistory: true
  property int intervalMs: 1000
  property bool ready: false
  property bool alive: false
  property bool failed: false
  property bool rateChange: false
  property string lastError: ""
  property double updatedAtMs: 0
  property double nowMs: Date.now()
  readonly property string health: failed ? "error" : (!active || !ready ? "unknown"
    : (nowMs - updatedAtMs > Math.max(4000, intervalMs * 3) ? "stale" : "normal"))
  readonly property bool cpuAvailable: cpuPct !== null
  readonly property bool gpuAvailable: gpuPct !== null
  readonly property bool memAvailable: memPct !== null
  readonly property bool diskAvailable: diskPct !== null

  property var cpuPct: null
  property var cpuFreqGhz: null
  property var cpuTempC: null
  property var load1: null
  property int cores: 0
  property string cpuModel: ""
  property string gpuModel: ""
  property var gpuPct: null
  property var gpuFreqMhz: null
  property var gpuMaxMhz: null
  property string gpuEngine: ""
  property var gpuTempC: null
  property var gpuVramUsedGb: null
  property var gpuVramTotalGb: null
  property var gpuPowerW: null
  property var memPct: null
  property var memUsedGb: null
  property var memTotalGb: null
  property var swapPct: null
  property var swapUsedGb: null
  property var swapTotalGb: null
  property var diskPct: null
  property var diskUsedGb: null
  property var diskTotalGb: null
  property var diskFreeGb: null
  property var diskReadBps: null
  property var diskWriteBps: null
  property int uptimeSec: 0
  property var cpuHistory: []
  property var gpuHistory: []
  property var memHistory: []
  property var memTop: []
  property var diskHistory: []
  property var historyTimes: []

  Process {
    id: sampler
    command: ["python3", decodeURIComponent(String(Qt.resolvedUrl("../scripts/vitals_sampler.py")).replace(/^file:\/\//, "")),
      "--interval-ms", String(root.intervalMs)]
    stdout: SplitParser { onRead: function(line) { root.handleLine(line) } }
    stderr: SplitParser { onRead: function(line) { root.lastError = "系统采样失败"; root.failed = true } }
    onStarted: root.alive = true
    onExited: {
      root.alive = false
      if (root.active) {
        if (!root.rateChange) { root.failed = true; root.lastError = "系统采样已停止" }
        restart.interval = root.rateChange ? 50 : 5000
        restart.restart()
      }
    }
  }
  Timer { id: restart; onTriggered: { root.rateChange = false; if (root.active) sampler.running = true } }
  Timer { interval: root.keepHistory ? 1000 : 5000; running: true; repeat: true; onTriggered: root.nowMs = Date.now() }
  Component.onCompleted: if (active) sampler.running = true
  onActiveChanged: {
    if (active) sampler.running = true
    else { restart.stop(); sampler.running = false; alive = false }
  }
  onIntervalMsChanged: {
    if (sampler.running) { rateChange = true; sampler.running = false }
  }
  onKeepHistoryChanged: {
    cpuHistory = []; gpuHistory = []; memHistory = []; diskHistory = []; historyTimes = []
  }

  function n(value) { return value === null || value === undefined || !isFinite(Number(value)) ? null : Number(value) }
  function handleLine(line) {
    var d
    try { d = JSON.parse(line) } catch (e) { failed = true; lastError = "系统数据无效"; return }
    if (!d || d.v !== 1) return
    if (d.error) { failed = true; lastError = "系统采样失败，保留上次结果"; return }
    ready = true; failed = false; lastError = ""
    updatedAtMs = n(d.ts) !== null ? Number(d.ts) * 1000 : 0
    var cpu = d.cpu || {}, gpu = d.gpu || {}, mem = d.mem || {}, disk = d.disk || {}
    cpuPct = n(cpu.pct); cpuFreqGhz = n(cpu.freqGhz); cpuTempC = n(cpu.tempC)
    load1 = n(cpu.load1); cores = n(cpu.cores) || 0
    cpuModel = String(d.cpuModel || ""); gpuModel = String(d.gpuModel || "")
    gpuPct = n(gpu.pct); gpuFreqMhz = n(gpu.freqMhz); gpuMaxMhz = n(gpu.maxMhz)
    gpuEngine = String(gpu.engine || ""); gpuTempC = n(gpu.tempC)
    gpuVramUsedGb = n(gpu.vramUsedGb); gpuVramTotalGb = n(gpu.vramTotalGb); gpuPowerW = n(gpu.powerW)
    memPct = n(mem.pct); memUsedGb = n(mem.usedGb); memTotalGb = n(mem.totalGb)
    memTop = mem.top && typeof mem.top.length === "number" ? mem.top : []
    swapPct = n(mem.swapPct); swapUsedGb = n(mem.swapUsedGb); swapTotalGb = n(mem.swapTotalGb)
    diskPct = n(disk.pct); diskUsedGb = n(disk.usedGb); diskTotalGb = n(disk.totalGb)
    diskFreeGb = n(disk.freeGb); diskReadBps = n(disk.readBps); diskWriteBps = n(disk.writeBps)
    uptimeSec = n(d.uptimeSec) || 0
    if (keepHistory) {
      var times = historyTimes.slice(), drop = 0
      times.push(updatedAtMs)
      while (drop < times.length && updatedAtMs - times[drop] >= 60000) drop++
      historyTimes = times.slice(drop)
      cpuHistory = cpuHistory.concat([cpuPct]).slice(drop)
      gpuHistory = gpuHistory.concat([gpuPct]).slice(drop)
      memHistory = memHistory.concat([memPct]).slice(drop)
      diskHistory = diskHistory.concat([diskPct]).slice(drop)
    }
  }
}
