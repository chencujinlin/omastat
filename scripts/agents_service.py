#!/usr/bin/env python3
"""Read existing agent records, refresh stale providers, and publish safe snapshots."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time

from usage_stats import PARSER_VERSION, BUCKETS, NativeStats, account_for_forks, aggregate, number, obj, opencode_origins, stamp
from deepseek_balance import DeepSeekBalance

NAMES = {'codex': 'Codex', 'opencode': 'OpenCode', 'claude': 'Claude Code', 'deepseek-harness': 'DeepSeek Harness', 'pi': 'Pi', 'fireworks': 'Fireworks'}
LOCAL = {'opencode', 'deepseek-harness', 'pi'}
TTL = 6 * 3600
PROCESSES = set()
PROCESS_LOCK = threading.Lock()
STOPPING = threading.Event()


def reject_constant(value):
    raise ValueError('non-finite JSON value')


def read_json(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError('object required')
    return value


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_or_empty(path):
    try:
        return read_json(path)
    except (ValueError, OSError, UnicodeError):
        return {}


def safe_record(record, now):
    # Persist accounting fields only. Drop auth hints, arbitrary payloads and
    # upstream diagnostic text even when the surrounding JSON is valid.
    safe = {key: record[key] for key in ('id', 'updatedAt', 'limitsUpdatedAt', 'hasLocalStats', 'retryAdvised') if key in record}
    safe['usageStatusText'] = bool(record.get('usageStatusText'))
    safe['limits'] = valid_limits(record.get('limits'), now)
    for key in ('todayTotalTokens', 'todayPrompts'):
        safe[key] = number(record.get(key))
    safe['todayTokensByModel'] = {str(k)[:160]: number(v) for k, v in obj(record.get('todayTokensByModel')).items()}
    safe['modelUsage'] = {str(k)[:160]: {field: number(obj(v).get(field)) for field in BUCKETS} for k, v in obj(record.get('modelUsage')).items()}
    performance = obj(record.get('performance'))
    safe['performance'] = {
        scope: {key: number(obj(performance.get(scope)).get(key))
                for key in ('averageTtftSeconds', 'tokensPerSecond', 'calls')}
        for scope in ('today', 'allTime')
    }
    days = record.get('recentDays')
    safe['recentDays'] = [{'date': d['date'][:10], 'messageCount': number(d.get('messageCount')), 'promptCount': number(d.get('promptCount'))} for d in days if isinstance(d, dict) and isinstance(d.get('date'), str)] if isinstance(days, list) else []
    return safe


def valid_limits(raw, now):
    result = []
    for entry in raw if isinstance(raw, list) else []:
        entry = obj(entry)
        percent, reset = number(entry.get('percent')), stamp(entry.get('resetsAt'))
        if entry.get('resetsAt') and reset is None:
            continue
        # Quota percentages in Omarchy's record contract are fractions (0..1).
        if percent is None or percent > 1 or (reset is not None and reset <= now):
            continue
        result.append({'label': str(entry.get('label') or '额度')[:60], 'percent': percent, 'resetsAt': entry.get('resetsAt') if reset is not None else ''})
    return result


def collect(agent, config_home, state_home):
    if STOPPING.is_set():
        return False
    extension = config_home / 'omarchy/plugins/chencu.agents/collectors/update.py'
    updater = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy')) / 'bin/omarchy-agent-usage-update'
    command = [sys.executable, str(extension), agent] if extension.is_file() else [str(updater), agent]
    if agent in ('codex', 'claude'):
        command.insert(-1, '--limits-only')  # Native tool stats below, account quota here.
    state_home.mkdir(parents=True, exist_ok=True)
    with (state_home / (agent + '.lock')).open('w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            with PROCESS_LOCK:
                if STOPPING.is_set():
                    return False
                collector_env = dict(os.environ)
                collector_env.setdefault('OMARCHY_PATH', '/usr/share/omarchy')
                process = subprocess.Popen(command, env=collector_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                PROCESSES.add(process)
        except OSError:
            return False
        try:
            return process.wait(timeout=100) == 0
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return False
        finally:
            with PROCESS_LOCK:
                PROCESSES.discard(process)


class Store:
    def __init__(self, usage_dir, state_dir, config_home=None, home=None, cache_home=None):
        self.usage_dir, self.state_dir = Path(usage_dir), Path(state_dir)
        self.home = Path(home or Path.home())
        self.config_home = Path(config_home or self.home / '.config')
        self.cache_home = Path(cache_home or self.home / '.cache')
        saved = load_or_empty(self.state_dir / 'agents-cache.json')
        self.records = {agent: safe_record(record, time.time()) for agent, record in obj(saved.get('records')).items() if agent in NAMES and isinstance(record, dict) and stamp(record.get('updatedAt')) is not None}
        self.limits = obj(saved.get('limits'))
        self.native_cache = obj(saved.get('native')) if saved.get('nativeParserVersion') == PARSER_VERSION else {}
        self.native = NativeStats(self.home, self.native_cache)
        self.balance = DeepSeekBalance(self.home)
        self.errors, self.signatures, self.attempts, self.stats = {}, {}, {}, {}
        self.stats_errors = {}
        self.stats_at = {}
        self.dirty = False

    def quota_time(self, agent, record):
        explicit = stamp(record.get('limitsUpdatedAt'))
        if explicit is not None:
            return explicit
        if agent == 'claude':
            # Omarchy can republish fallback limits after auth expires without
            # retryAdvised. Its probe cache retains the actual fetch timestamp.
            probe = load_or_empty(self.cache_home / 'omarchy/agent-usage/claude-limits.json')
            fetched = number(probe.get('fetchedAtMs'))
            if fetched is not None:
                return fetched / 1000
        if record.get('usageStatusText') or record.get('retryAdvised'):
            return None
        return stamp(record.get('updatedAt'))

    def poll(self, ids, now):
        for agent in ids:
            path = self.usage_dir / (agent + '.json')
            try:
                stat = path.stat()
                signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
                if self.signatures.get(agent) == signature:
                    continue
                record = read_json(path)
                if record.get('id', agent) != agent or stamp(record.get('updatedAt')) is None:
                    raise ValueError('invalid record')
                if record.get('collectionErrors'):
                    self.errors[agent] = '采集失败，保留上次有效结果'
                    continue
                record = safe_record(record, now)
                self.records[agent] = record
                self.signatures[agent] = signature
                self.errors.pop(agent, None)
                at = self.quota_time(agent, record)
                limits = valid_limits(record.get('limits'), now)
                if limits and at is not None and not record.get('retryAdvised') and 0 <= now-at < TTL:
                    self.limits[agent] = {'at': at, 'limits': limits}
                self.dirty = True
            except FileNotFoundError:
                self.errors[agent] = '记录文件缺失'
            except (OSError, ValueError, UnicodeError, TypeError):
                self.errors[agent] = '记录无法读取'
        # Entries are never merged into raw records. Expire even without a reread.
        for agent in list(self.limits):
            cache = obj(self.limits[agent])
            at = number(cache.get('at'))
            if at is None or not 0 <= now-at < TTL or not valid_limits(cache.get('limits'), now):
                self.limits.pop(agent, None)
                self.dirty = True

    def scan_stats(self, ids, now):
        # Reuse local extension event cache, including its deduplication and DSH
        # fork boundaries. Never perform a second OpenCode/DSH/Pi log scan.
        local = load_or_empty(self.cache_home / 'omarchy/agents-extension/local-tools.json')
        for agent in ids:
            if agent in ('codex', 'claude'):
                try:
                    result, failed = self.native.scan(agent, now)
                except (OSError, ValueError, TypeError):
                    result, failed = None, True
                if failed:
                    self.stats_errors[agent] = '本地统计读取失败，保留上次有效结果'
                elif result is not None:
                    self.stats_errors.pop(agent, None)
                    self.stats[agent] = result
                    self.stats_at[agent] = now
                    self.dirty = True
            elif agent in LOCAL and agent not in self.errors and isinstance(local.get(agent), dict):
                entries = list(local[agent].values())
                if any(not isinstance(e, dict) or not isinstance(e.get('records'), list) for e in entries):
                    self.stats_errors[agent] = '统计缓存格式异常，保留上次结果'
                    continue
                events = [r for e in entries if isinstance(e, dict) for r in (e.get('records') if isinstance(e.get('records'), list) else []) if isinstance(r, dict)]
                if any(not isinstance(r.get('key'), str) or stamp(r.get('time')) is None or any(number(r.get(k)) is None for k in BUCKETS) for r in events):
                    self.stats_errors[agent] = '统计缓存格式异常，保留上次结果'
                    continue
                self.stats_errors.pop(agent, None)
                if agent == 'opencode':
                    parents = opencode_origins(local[agent])
                    if parents is None:
                        self.stats_errors[agent] = '分叉会话元数据暂不可读，保留上次结果'
                        continue
                    events = account_for_forks(events, parents)
                    self.stats_errors.pop(agent, None)
                # The extension's buckets are disjoint; reasoning is already
                # included in outputTokens and is never added to the total.
                self.stats[agent] = aggregate(events, now)
                self.stats_at[agent] = stamp(obj(self.records.get(agent)).get('updatedAt'))

    def due(self, agent, now, interval, force=False):
        at = stamp(obj(self.records.get(agent)).get('updatedAt'))
        midnight = at is not None and datetime.fromtimestamp(at).date() != datetime.fromtimestamp(now).date()
        stale = at is None or not 0 <= now-at < interval or midnight or bool(self.errors.get(agent))
        # Manual refresh is bounded too. Failed providers back off independently.
        cooldown = 30 if force else max(60, interval)
        return (force or stale) and now-self.attempts.get(agent, 0) >= cooldown

    def snapshot(self, ids, now, interval, refreshing=()):
        result = []
        today = datetime.fromtimestamp(now).astimezone().date()
        for agent in ids:
            raw = obj(self.records.get(agent))
            at = stamp(raw.get('updatedAt'))
            state = 'unknown' if at is None else ('normal' if 0 <= now-at <= interval*1.5 else 'stale')
            if self.errors.get(agent):
                state = 'error'
            stats = self.stats.get(agent)
            local_at = self.stats_at.get(agent)
            if stats is None and agent in LOCAL and agent not in self.stats_errors:
                stats = self.record_stats(raw, now)
                local_at = at
            stats = obj(stats)
            cache = obj(self.limits.get(agent))
            cache_at = number(cache.get('at'))
            limits = valid_limits(cache.get('limits'), now) if cache_at is not None and 0 <= now-cache_at < TTL else []
            quota_at = self.quota_time(agent, raw)
            current = valid_limits(raw.get('limits'), now) if quota_at is not None and 0 <= now-quota_at < TTL and not raw.get('retryAdvised') and not raw.get('usageStatusText') else []
            quota_state = 'unsupported' if agent in LOCAL else ('available' if limits else 'unavailable')
            quota_stale = bool(limits) and (not current or cache_at != quota_at or now-cache_at > interval*1.5)
            if quota_stale and state == 'normal':
                state = 'stale'
            date_ok = stats.get('statsDate') == today.isoformat()
            if at is not None and datetime.fromtimestamp(at).date() != today and agent in LOCAL:
                date_ok = False
                if state == 'normal':
                    state = 'stale'
            token_state = 'unknown' if stats.get('todayTokens') is None or not date_ok or local_at is None else ('normal' if 0 <= now-local_at <= interval*1.5 else 'stale')
            if self.stats_errors.get(agent) or (agent in LOCAL and self.errors.get(agent)):
                token_state = 'error'
            quota_health = 'normal' if limits and not quota_stale else ('stale' if limits else 'unknown')
            if agent not in LOCAL and (self.errors.get(agent) or raw.get('retryAdvised') or raw.get('usageStatusText')):
                quota_health = 'error'
            healths = [state, token_state] + ([quota_health] if agent not in LOCAL else [])
            state = next((h for h in ('error', 'stale', 'unknown', 'normal') if h in healths), 'unknown')
            performance = obj(raw.get('performance'))
            today_perf, all_perf = obj(performance.get('today')), obj(performance.get('allTime'))
            ttft = number(today_perf.get('averageTtftSeconds'))
            if ttft is None:
                ttft = number(all_perf.get('averageTtftSeconds'))
            speed = number(today_perf.get('tokensPerSecond'))
            if speed is None:
                speed = number(all_perf.get('tokensPerSecond'))
            if ttft is None:
                ttft = number(stats.get('ttftSeconds'))
            if speed is None:
                speed = number(stats.get('tokensPerSecond'))
            result.append({'tokenState': token_state, 'quotaHealth': quota_health, 'id': agent, 'name': NAMES[agent], 'plan': '本地工具', 'scope': stats.get('scope', 'tool'), 'state': state, 'error': self.errors.get(agent, '') or self.stats_errors.get(agent, ''), 'updatedAtMs': at*1000 if at else 0, 'statsUpdatedAtMs': local_at*1000 if local_at else 0, 'todayTokens': stats.get('todayTokens') if date_ok else None, 'todayPrompts': stats.get('todayRequests') if date_ok else None, 'sevenTokens': stats.get('sevenTokens') if date_ok else None, 'sevenPrompts': stats.get('sevenRequests') if date_ok else None, 'models': stats.get('models', {}), 'todayModels': stats.get('todayModels', {}) if date_ok else {}, 'detailScope': stats.get('detailScope', '累计'), 'days': stats.get('days', []), 'lastActivityMs': stats.get('lastActivityMs'), 'limits': limits, 'bestLimit': max(limits, key=lambda x: x['percent']) if limits else None, 'cachedQuota': quota_stale, 'quotaState': quota_state, 'quotaUpdatedAtMs': cache_at*1000 if cache_at is not None else 0, 'ttftSeconds': ttft, 'tokensPerSecond': speed, 'apiBalance': self.balance.snapshot(now) if agent == 'deepseek-harness' else None})
        priority = ('error', 'stale', 'unknown', 'normal')
        state = next((s for s in priority if any(r['state'] == s for r in result)), 'unknown')
        timestamps = [r['updatedAtMs'] for r in result if r['updatedAtMs']]
        return {'agents': result, 'state': state, 'updatedAtMs': min(timestamps) if timestamps else 0, 'refreshing': bool(refreshing), 'generatedAtMs': now*1000}

    @staticmethod
    def record_stats(raw, now):
        if raw.get('hasLocalStats') is False:
            return {}
        date = datetime.fromtimestamp(now).astimezone().date()
        dates = {(date-timedelta(days=i)).isoformat() for i in range(7)}
        days = [d for d in raw.get('recentDays', []) if isinstance(d, dict) and d.get('date') in dates] if isinstance(raw.get('recentDays'), list) else []
        # Only the known local extension contract calls token totals messageCount.
        # Unknown fields remain unknown; absent dates are not padded with zeroes.
        days = list({d['date']: d for d in days}.values())
        tokens = [number(d.get('messageCount')) for d in days]
        requests = [number(d.get('promptCount')) for d in days]
        return {'todayTokens': number(raw.get('todayTotalTokens')), 'todayRequests': number(raw.get('todayPrompts')), 'sevenTokens': sum(tokens) if len(set(d['date'] for d in days)) == 7 and all(t is not None for t in tokens) else None, 'sevenRequests': sum(requests) if len(days) == 7 and all(t is not None for t in requests) else None, 'models': obj(raw.get('modelUsage')), 'todayModels': obj(raw.get('todayTokensByModel')), 'detailScope': '累计', 'scope': 'tool', 'statsDate': datetime.fromtimestamp(stamp(raw.get('updatedAt')) or 0).astimezone().date().isoformat()}

    def save(self):
        if self.dirty:
            atomic_json(self.state_dir / 'agents-cache.json', {'records': self.records, 'limits': self.limits, 'native': self.native_cache, 'nativeParserVersion': PARSER_VERSION})
            self.dirty = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'config.json')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--no-collect', action='store_true')
    parser.add_argument('--poll-seconds', type=float, default=15)
    args = parser.parse_args()
    home = args.home
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state'))
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    store = Store(state/'omarchy/agents/usage', state/'omarchy/omastat', config_home, home, Path(os.environ.get('XDG_CACHE_HOME', home/'.cache')))
    selector = selectors.DefaultSelector()
    try:
        selector.register(sys.stdin, selectors.EVENT_READ)
    except (OSError, ValueError):
        pass
    def stop(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    workers, active, last_scan = ThreadPoolExecutor(max_workers=2), {}, 0
    try:
        while True:
            now, force = time.time(), False
            settings = load_or_empty(args.config)
            ids = settings.get('agents', list(NAMES))
            ids = list(dict.fromkeys(a for a in ids if isinstance(a, str) and a in NAMES)) if isinstance(ids, list) else list(NAMES)
            interval = number(settings.get('refreshSeconds')) or 300
            interval = max(60, interval)
            store.poll(ids, now)
            if not (args.no_collect or os.environ.get('OMASTAT_NO_COLLECT')):
                store.balance.request(now, force)
            for agent, future in list(active.items()):
                if future.done():
                    try:
                        if not future.result():
                            store.errors[agent] = '采集失败，保留上次有效结果'
                    except Exception:
                        store.errors[agent] = '采集失败，保留上次有效结果'
                    del active[agent]
            if now-last_scan >= min(interval, 60):
                store.scan_stats(ids, now)
                last_scan = now
            snapshot = store.snapshot(ids, now, interval, active)
            try:
                store.save()
            except OSError:
                snapshot['state'] = 'error'
            print(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), flush=True)
            if args.once:
                break
            wait = 0.25 if store.balance.pending else args.poll_seconds
            events = selector.select(timeout=max(0.1, wait))
            for key, _ in events:
                line = key.fileobj.readline()
                if not line:
                    selector.unregister(key.fileobj)
                elif line.strip() == 'refresh':
                    force = True
            if not (args.no_collect or os.environ.get('OMASTAT_NO_COLLECT')):
                for agent in ids:
                    if agent not in active and store.due(agent, time.time(), interval, force):
                        store.attempts[agent] = time.time()
                        active[agent] = workers.submit(collect, agent, config_home, store.state_dir)
            if force:
                last_scan = 0
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        STOPPING.set()
        with PROCESS_LOCK:
            processes = list(PROCESSES)
        for process in processes:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        workers.shutdown(wait=True, cancel_futures=True)


if __name__ == '__main__':
    main()
