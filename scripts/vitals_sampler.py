#!/usr/bin/env python3
"""1 Hz system telemetry sampler for Quickshell/QML.

Emits one JSON object per line on stdout (flushed). Pure Python stdlib:
no psutil, no PIL, no network. A single cached lspci lookup supplies the GPU
model name; CPU model comes from /proc/cpuinfo.

Usage:
    vitals_sampler.py [--interval-ms 1000] [--count 0]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time

SCHEMA_VERSION = 1
ENGINES = ("render", "video", "compute")
DRM_PREFIX = "/dev/dri/"

GIB = 1024.0 * 1024.0 * 1024.0
KB_PER_GIB = 1024.0 * 1024.0


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def read_int(path: str) -> int | None:
    text = read_text(path)
    if text is None:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def clean_model(text: str) -> str:
    text = re.sub(r"\((?:R|TM)\)", "", str(text), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


_CPU_MODEL: str | None = None
_GPU_MODEL: str | None = None


def read_cpu_model() -> str | None:
    """Read the stable CPU model string; cached for the life of the sampler."""
    global _CPU_MODEL
    if _CPU_MODEL is None:
        _CPU_MODEL = ""
        text = read_text("/proc/cpuinfo") or ""
        for line in text.splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() in ("model name", "Hardware", "Processor"):
                _CPU_MODEL = clean_model(value)
                break
    return _CPU_MODEL or None


def _gpu_driver_label(driver: str) -> str:
    return {
        "i915": "Intel Graphics", "xe": "Intel Graphics",
        "nvidia": "NVIDIA GPU", "nouveau": "NVIDIA GPU",
        "amdgpu": "AMD Radeon", "radeon": "AMD Radeon",
    }.get(driver.lower(), "")


def read_gpu_model() -> str | None:
    """Read the first display adapter's model from lspci; cache the result.

    lspci is optional. If it is unavailable we fall back to the DRM driver
    name, which is still more useful than hiding the GPU row's identity.
    """
    global _GPU_MODEL
    if _GPU_MODEL is None:
        _GPU_MODEL = ""
        try:
            output = subprocess.run(
                ["lspci", "-mm", "-nn"], capture_output=True, text=True,
                timeout=2, check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            output = ""
        for line in output.splitlines():
            try:
                fields = shlex.split(line)
            except ValueError:
                continue
            if len(fields) < 4:
                continue
            kind = fields[1].lower()
            if not any(word in kind for word in ("vga", "3d", "display")):
                continue
            vendor = re.sub(r"\s*\[[0-9a-fA-F]{4}\]$", "", fields[2]).strip()
            vendor = vendor.replace(" Corporation", "").replace(" Inc.", "").strip()
            device = re.sub(r"\s*\[[0-9a-fA-F]{4}\]$", "", fields[3]).strip()
            bracket = re.search(r"\[([^\[\]]+)\]\s*$", device)
            if bracket:
                device = bracket.group(1).strip()
            if vendor and device:
                _GPU_MODEL = (vendor + " " + device).strip()
                break
        if not _GPU_MODEL:
            for path in glob.glob("/sys/class/drm/card[0-9]*/device/uevent"):
                for line in (read_text(path) or "").splitlines():
                    if line.startswith("DRIVER="):
                        _GPU_MODEL = _gpu_driver_label(line.partition("=")[2])
                        break
                if _GPU_MODEL:
                    break
    return _GPU_MODEL or None


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

class CpuMeter:
    """Computes CPU utilisation from consecutive /proc/stat snapshots."""

    def __init__(self) -> None:
        self._prev: tuple[int, int] | None = None

    @staticmethod
    def _read_stat() -> tuple[int, int] | None:
        try:
            with open("/proc/stat", "rb") as fh:
                line = fh.readline()
        except OSError:
            return None
        fields = line.split()
        if len(fields) < 5 or fields[0] != b"cpu":
            return None
        try:
            values = [int(token) for token in fields[1:]]
        except ValueError:
            return None
        if len(values) < 4:
            return None
        # guest/guest_nice are already accounted for in user/nice.
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values[:8])
        return total, idle

    def step(self) -> float | None:
        current = self._read_stat()
        if current is None:
            return None
        pct = None
        if self._prev is not None:
            total_delta = current[0] - self._prev[0]
            idle_delta = current[1] - self._prev[1]
            if total_delta > 0:
                pct = (total_delta - idle_delta) * 100.0 / total_delta
        self._prev = current
        return clamp_pct(pct) if pct is not None else None


def cpu_freq_ghz() -> float | None:
    """Average current CPU frequency in GHz (cpufreq first, cpuinfo fallback)."""
    freqs: list[int] = []
    try:
        with os.scandir("/sys/devices/system/cpu/cpufreq") as entries:
            for entry in entries:
                if not entry.name.startswith("policy"):
                    continue
                value = read_int(os.path.join(entry.path, "scaling_cur_freq"))
                if value is not None:
                    freqs.append(value)
    except OSError:
        pass
    if freqs:
        return round(sum(freqs) / len(freqs) / 1_000_000.0, 2)

    text = read_text("/proc/cpuinfo")
    if text:
        mhz: list[float] = []
        for line in text.splitlines():
            if line.startswith("cpu MHz"):
                _, _, rhs = line.partition(":")
                try:
                    mhz.append(float(rhs))
                except ValueError:
                    continue
        if mhz:
            return round(sum(mhz) / len(mhz) / 1000.0, 2)
    return None


def _max_temp_input(files) -> int | None:
    best: int | None = None
    for entry in files:
        name = entry.name
        if not (name.startswith("temp") and name.endswith("_input")):
            continue
        value = read_int(entry.path)
        if value is None:
            continue
        if best is None or value > best:
            best = value
    return best


def cpu_temp_c() -> float | None:
    """Hottest coretemp sensor in C; thermal zones as fallback."""
    try:
        with os.scandir("/sys/class/hwmon") as hwmons:
            for hwmon in hwmons:
                name = read_text(os.path.join(hwmon.path, "name"))
                if name is None or name.strip() != "coretemp":
                    continue
                try:
                    with os.scandir(hwmon.path) as files:
                        raw = _max_temp_input(files)
                except OSError:
                    raw = None
                if raw is not None:
                    return round(raw / 1000.0, 1)
    except OSError:
        pass

    raw = None
    try:
        with os.scandir("/sys/class/thermal") as zones:
            for zone in zones:
                if not zone.name.startswith("thermal_zone"):
                    continue
                value = read_int(os.path.join(zone.path, "temp"))
                if value is None:
                    continue
                if raw is None or value > raw:
                    raw = value
    except OSError:
        pass
    return round(raw / 1000.0, 1) if raw is not None else None


def read_load1() -> float | None:
    text = read_text("/proc/loadavg")
    if text:
        try:
            return round(float(text.split()[0]), 2)
        except (ValueError, IndexError):
            pass
    return None


# ---------------------------------------------------------------------------
# GPU (i915 DRM fdinfo engine counters)
# ---------------------------------------------------------------------------

GpuClient = tuple[str, str] | None
GpuCounters = tuple[GpuClient, dict[str, int]]
GpuState = dict[tuple[str, str], GpuCounters]


def _read_fdinfo_counters(path: str) -> GpuCounters:
    client_id: str | None = None
    pdev: str | None = None
    counters: dict[str, int] = {}
    try:
        with open(path, "r", encoding="ascii", errors="replace") as fh:
            for line in fh:
                if line.startswith("drm-client-id:"):
                    value = line.partition(":")[2].strip()
                    if value:
                        client_id = value
                    continue
                if line.startswith("drm-pdev:"):
                    value = line.partition(":")[2].strip()
                    if value:
                        pdev = value
                    continue
                if not line.startswith("drm-engine-"):
                    continue
                key, sep, rest = line.partition(":")
                if not sep:
                    continue
                engine = key[len("drm-engine-"):]
                if engine not in ENGINES:
                    continue
                bits = rest.split()
                if not bits:
                    continue
                try:
                    value = int(bits[0])
                except ValueError:
                    continue
                if value >= 0:
                    counters[engine] = value
    except OSError:
        return None, {}
    identity = (pdev or "", client_id) if client_id is not None else None
    return identity, counters


class GpuMeter:
    """Measures GPU busy time from per-(pid, fd) DRM engine ns counters.

    i915 reports the same per-client engine counters through every fd of a
    DRM client (Hyprland commonly has 4+ fds for one client), and a forked
    process can share the same client too.  Summing raw per-fd deltas would
    therefore report >100% on an idle GPU.  We still scan/track every
    (pid, fd) key, but collapse deltas per (DRM device, client-id) before
    summing across engines.
    """

    def __init__(self) -> None:
        self._prev: GpuState = {}
        self._prev_ns: int | None = None

    @staticmethod
    def _scan() -> GpuState:
        state: GpuState = {}
        try:
            with os.scandir("/proc") as procs:
                for proc in procs:
                    pid = proc.name
                    if not pid.isdigit():
                        continue
                    try:
                        with os.scandir(f"/proc/{pid}/fd") as fds:
                            for fd in fds:
                                if not fd.name.isdigit():
                                    continue
                                try:
                                    target = os.readlink(fd.path)
                                except OSError:
                                    continue
                                if not target.startswith(DRM_PREFIX):
                                    continue
                                counters = _read_fdinfo_counters(
                                    f"/proc/{pid}/fdinfo/{fd.name}"
                                )
                                if counters[1]:
                                    state[(pid, fd.name)] = counters
                    except OSError:
                        continue
        except OSError:
            pass
        return state

    def step(self) -> tuple[float | None, str | None]:
        started_ns = time.monotonic_ns()
        try:
            state = self._scan()
        except Exception:
            state = {}

        pct: float | None = None
        engine: str | None = None

        if state:
            if self._prev_ns is not None:
                elapsed_ns = started_ns - self._prev_ns
            else:
                elapsed_ns = 0

            busy = {name: 0 for name in ENGINES}
            # DRM client -> engine -> delta. Taking the max within a client
            # avoids counting the same shared counters once per duplicate fd.
            client_deltas: dict[tuple[str, str], dict[str, int]] = {}
            for key, (identity, counters) in state.items():
                old = self._prev.get(key)
                if old is None:
                    # New key: establishes a baseline, never counted.
                    continue
                old_identity, old_counters = old
                if (
                    identity is not None
                    and old_identity is not None
                    and identity != old_identity
                ):
                    # fd recycled by a different client: new baseline.
                    continue
                if identity is not None:
                    group = identity
                else:
                    group = (f"pid:{key[0]}", f"fd:{key[1]}")
                for name, value in counters.items():
                    old_value = old_counters.get(name)
                    if old_value is None:
                        # New engine counter for an existing key: baseline too.
                        continue
                    delta = value - old_value
                    if delta <= 0:
                        continue
                    bucket = client_deltas.setdefault(group, {})
                    if delta > bucket.get(name, 0):
                        bucket[name] = delta
            for bucket in client_deltas.values():
                for name, delta in bucket.items():
                    busy[name] += delta

            engine = max(ENGINES, key=lambda name: busy[name])
            if elapsed_ns > 0:
                pct = clamp_pct(busy[engine] * 100.0 / elapsed_ns)
            else:
                pct = 0.0
        # else: no readable engine counters at all -> pct/engine stay null.

        self._prev = state
        self._prev_ns = started_ns
        return pct, engine


def gpu_freq_mhz() -> tuple[int | None, int | None]:
    cards: list[str] = []
    try:
        with os.scandir("/sys/class/drm") as entries:
            for entry in entries:
                name = entry.name
                if name.startswith("card") and name[4:].isdigit():
                    cards.append(name)
    except OSError:
        return None, None

    for card in sorted(cards):
        base = os.path.join("/sys/class/drm", card)
        current = read_int(os.path.join(base, "gt_cur_freq_mhz"))
        if current is not None:
            maximum = read_int(os.path.join(base, "gt_max_freq_mhz"))
            return current, maximum
    return None, None


# ---------------------------------------------------------------------------
# memory / disk / uptime
# ---------------------------------------------------------------------------

def top_memory_processes(total_kb: int, limit: int = 3, proc_root: str = "/proc",
                         page_size: int | None = None) -> list[dict]:
    """Aggregate resident memory by process name, highest first.

    RSS is an estimate (shared pages are counted in every process), but it is
    cheap, available without root, and matches what users expect from a "top
    memory processes" list. Grouping by comm keeps multi-process apps such as
    Chromium as one meaningful row.
    """
    if total_kb <= 0:
        return []
    try:
        page_size = page_size or os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError):
        page_size = 4096
    groups: dict[str, int] = {}
    try:
        with os.scandir(proc_root) as processes:
            for process in processes:
                if not process.name.isdigit():
                    continue
                try:
                    with open(os.path.join(process.path, "comm"), "r",
                              encoding="utf-8", errors="replace") as handle:
                        name = handle.read().strip()
                    with open(os.path.join(process.path, "statm"), "r",
                              encoding="ascii", errors="replace") as handle:
                        fields = handle.read().split()
                    rss_pages = int(fields[1])
                except (OSError, ValueError, IndexError):
                    continue
                if not name or rss_pages <= 0:
                    continue
                groups[name] = groups.get(name, 0) + rss_pages
    except OSError:
        return []
    total_bytes = total_kb * 1024.0
    rows = sorted(groups.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    return [
        {"name": name[:48],
         "pct": round(min(100.0, pages * page_size * 100.0 / total_bytes), 1),
         "rssGb": round(pages * page_size / GIB, 2)}
        for name, pages in rows
    ]


def read_mem() -> dict[str, float]:
    data: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="ascii", errors="replace") as fh:
            for line in fh:
                key, sep, rest = line.partition(":")
                if not sep:
                    continue
                bits = rest.split()
                if not bits:
                    continue
                try:
                    data[key] = int(bits[0])
                except ValueError:
                    continue
    except OSError:
        pass

    total_kb = data.get("MemTotal", 0)
    available_kb = data.get("MemAvailable")
    if available_kb is None:
        available_kb = (
            data.get("MemFree", 0)
            + data.get("Buffers", 0)
            + data.get("Cached", 0)
        )
    if total_kb <= 0:
        fallback = dict.fromkeys(("pct", "usedGb", "totalGb", "swapPct", "swapUsedGb", "swapTotalGb"))
        fallback["top"] = []
        return fallback
    used_kb = max(0, total_kb - available_kb)

    swap_total_kb = data.get("SwapTotal", 0)
    swap_free_kb = data.get("SwapFree", 0)
    swap_used_kb = max(0, swap_total_kb - swap_free_kb)

    mem_pct = used_kb * 100.0 / total_kb if total_kb > 0 else 0.0
    swap_pct = swap_used_kb * 100.0 / swap_total_kb if swap_total_kb > 0 else 0.0

    return {
        "pct": round(clamp_pct(mem_pct), 1),
        "usedGb": round(used_kb / KB_PER_GIB, 2),
        "totalGb": round(total_kb / KB_PER_GIB, 2),
        "swapPct": round(clamp_pct(swap_pct), 1),
        "swapUsedGb": round(swap_used_kb / KB_PER_GIB, 2),
        "swapTotalGb": round(swap_total_kb / KB_PER_GIB, 2),
        "top": top_memory_processes(total_kb),
    }


def read_disk() -> dict[str, float]:
    try:
        stat = os.statvfs("/")
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
    except OSError:
        return dict.fromkeys(("pct", "usedGb", "totalGb", "freeGb"))

    used = max(0, total - free)
    pct = used * 100.0 / total if total > 0 else 0.0
    return {
        "pct": round(clamp_pct(pct), 1),
        "usedGb": round(used / GIB, 2),
        "totalGb": round(total / GIB, 2),
        "freeGb": round(stat.f_bavail * stat.f_frsize / GIB, 2),
    }


class DiskIoMeter:
    """Root filesystem block device only; never sum partitions and parents."""
    def __init__(self):
        self.previous = None
        self.device = None
        try:
            for line in (read_text("/proc/self/mountinfo") or "").splitlines():
                fields = line.split()
                if len(fields) > 5 and fields[4] == "/":
                    self.device = fields[2]
                    break
        except (ValueError, IndexError):
            pass

    def step(self):
        text = read_text("/sys/dev/block/" + str(self.device) + "/stat")
        now = time.monotonic()
        try:
            fields = text.split() if text else []
            current = (int(fields[2]) * 512, int(fields[6]) * 512, now)
        except (ValueError, IndexError):
            return {"readBps": None, "writeBps": None}
        previous, self.previous = self.previous, current
        if previous is None or now <= previous[2] or current[0] < previous[0] or current[1] < previous[1]:
            return {"readBps": None, "writeBps": None}
        return {"readBps": round((current[0]-previous[0])/(now-previous[2])), "writeBps": round((current[1]-previous[1])/(now-previous[2]))}


def gpu_optional():
    """Read only kernel-exposed sensors; absence is unknown, never zero."""
    import glob
    devices = sorted(set(os.path.realpath(p) for p in glob.glob("/sys/class/drm/card[0-9]*/device")))
    if len(devices) != 1:
        return dict.fromkeys(("tempC", "vramUsedGb", "vramTotalGb", "powerW"))
    device = devices[0]
    def first_int(pattern):
        for path in sorted(glob.glob(pattern)):
            value = read_int(path)
            if value is not None:
                return value
        return None
    vram = first_int(device + "/mem_info_vram_used")
    total = first_int(device + "/mem_info_vram_total")
    temp = first_int(device + "/hwmon/hwmon*/temp1_input")
    power = first_int(device + "/hwmon/hwmon*/power1_average")
    return {"tempC": temp/1000 if temp is not None else None, "vramUsedGb": vram/GIB if vram is not None else None, "vramTotalGb": total/GIB if total is not None else None, "powerW": power/1000000 if power is not None else None}


def read_uptime() -> int:
    text = read_text("/proc/uptime")
    if text:
        try:
            return int(float(text.split()[0]))
        except (ValueError, IndexError):
            pass
    return 0


# ---------------------------------------------------------------------------
# sample assembly
# ---------------------------------------------------------------------------

def build_sample(cpu: CpuMeter, gpu: GpuMeter, disk_io=None) -> dict:
    def probe(function, fallback=None):
        try:
            return function()
        except Exception:
            # A bad device must not hide healthy CPU/memory/disk readings.
            return fallback
    cpu_pct = probe(cpu.step)
    gpu_pct, gpu_engine = probe(gpu.step, (None, None))
    temp_c = probe(cpu_temp_c)
    freq_ghz = probe(cpu_freq_ghz)
    load1 = probe(read_load1)
    mem = probe(read_mem, dict.fromkeys(("pct", "usedGb", "totalGb", "swapPct", "swapUsedGb", "swapTotalGb")))
    if not isinstance(mem.get("top"), list):
        mem["top"] = []
    disk = probe(read_disk, dict.fromkeys(("pct", "usedGb", "totalGb", "freeGb")))
    if disk_io is not None:
        disk.update(probe(disk_io.step, {"readBps": None, "writeBps": None}))
    uptime = probe(read_uptime, 0)
    cur_mhz, max_mhz = probe(gpu_freq_mhz, (None, None))

    return {
        "v": SCHEMA_VERSION,
        "ts": round(time.time(), 3),
        "uptimeSec": uptime,
        "cpuModel": probe(read_cpu_model, None),
        "gpuModel": probe(read_gpu_model, None),
        "cpu": {
            "pct": round(cpu_pct, 1) if cpu_pct is not None else None,
            "freqGhz": freq_ghz,
            "tempC": temp_c,
            "load1": load1,
            "cores": os.cpu_count() or 0,
        },
        "gpu": {
            "pct": None if gpu_pct is None else round(gpu_pct, 1),
            "freqMhz": cur_mhz,
            "maxMhz": max_mhz,
            "engine": gpu_engine,
            **probe(gpu_optional, {}),
        },
        "mem": mem,
        "disk": disk,
    }


def _safe_sample(cpu: CpuMeter, gpu: GpuMeter, disk_io=None) -> dict:
    try:
        return build_sample(cpu, gpu, disk_io)
    except Exception:
        # A single tick must never kill the sampler.
        return {
            "v": SCHEMA_VERSION,
            "ts": round(time.time(), 3),
            "uptimeSec": 0,
            "cpu": {
                "pct": None,
                "freqGhz": None,
                "tempC": None,
                "load1": None,
                "cores": os.cpu_count() or 0,
            },
            "gpu": {
                "pct": None,
                "freqMhz": None,
                "maxMhz": None,
                "engine": None,
            },
            "error": "system sample failed",
            "mem": dict(dict.fromkeys(("pct", "usedGb", "totalGb", "swapPct", "swapUsedGb", "swapTotalGb")), top=[]),
            "disk": dict.fromkeys(("pct", "usedGb", "totalGb", "freeGb", "readBps", "writeBps")),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _interval_ms(value: str) -> int:
    try:
        ms = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer number of milliseconds")
    if ms < 200:
        raise argparse.ArgumentTypeError("must be >= 200 ms")
    return ms


def _count(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if count < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit 1 Hz system vitals as JSON lines on stdout."
    )
    parser.add_argument(
        "--interval-ms",
        type=_interval_ms,
        default=1000,
        help="sampling period in milliseconds (default: 1000, minimum: 200)",
    )
    parser.add_argument(
        "--count",
        type=_count,
        default=0,
        help="number of samples to emit, 0 = unlimited (default: 0)",
    )
    args = parser.parse_args(argv)

    period = args.interval_ms / 1000.0
    stop = threading.Event()

    def _handle_signal(_signum, _frame) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cpu = CpuMeter()
    gpu = GpuMeter()
    disk_io = DiskIoMeter()

    # Prime both differential meters, then wait one interval before the first
    # line so the first emitted sample already has real deltas.
    cpu.step()
    gpu.step()
    disk_io.step()
    if stop.wait(period):
        return 0

    emitted = 0
    next_due = time.monotonic()
    while not stop.is_set():
        sample = _safe_sample(cpu, gpu, disk_io)
        line = json.dumps(sample, separators=(",", ":"), ensure_ascii=False)
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            # Reader went away (e.g. Quickshell restart). Point stdout at
            # /dev/null so the interpreter's final flush also stays quiet.
            try:
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, sys.stdout.fileno())
                os.close(devnull)
            except OSError:
                pass
            return 0

        emitted += 1
        if args.count != 0 and emitted >= args.count:
            break

        next_due += period
        now = time.monotonic()
        if next_due <= now:
            next_due = now + period
        if stop.wait(next_due - now):
            break

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
