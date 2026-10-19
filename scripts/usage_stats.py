"""Token accounting adapters. Persist only counters and event identities, never bodies."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path

PARSER_VERSION = 4
BUCKETS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens')


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def stamp(value):
    try:
        if isinstance(value, (float, int)):
            if isinstance(value, bool) or not math.isfinite(value):
                return None
            return value / 1000 if value > 100_000_000_000 else value
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def obj(value):
    return value if isinstance(value, dict) else {}


def token_event(key, session, when, model, inputs, outputs, read=0, write=0):
    values = [number(v) for v in (inputs, outputs, read, write)]
    when = stamp(when)
    if when is None or any(v is None for v in values):
        return None
    return dict(key=str(key), session=session if isinstance(session, str) else 'unknown', time=when, model=model[:160] if isinstance(model, str) else 'unknown', **dict(zip(BUCKETS, values)))


def parse_native(path, agent):
    """Native-only statistics: account aggregates may overlap Pi/OpenCode.

    Codex cumulative snapshots produce deltas; repeated snapshots and copied
    fork prefixes share an identity. Reasoning is already part of output.
    Claude streaming chunks share message/request IDs; take the latest usage.
    """
    events, previous, session, model = {}, {}, str(path), 'unknown'
    valid_rows, invalid_rows = 0, 0
    forked, created = False, None
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = obj(json.loads(line))
            except ValueError:
                invalid_rows += 1
                continue  # A live JSONL writer may leave its final line incomplete.
            valid_rows += 1
            payload = obj(row.get('payload'))
            if agent == 'codex':
                if row.get('type') == 'session_meta':
                    session = str(payload.get('id') or session)
                    forked = bool(payload.get('forked_from_id') or payload.get('parent_session_id'))
                    created = stamp(payload.get('timestamp') or row.get('timestamp'))
                if row.get('type') == 'turn_context':
                    model = payload.get('model') or payload.get('model_slug') or model
                if payload.get('type') != 'token_count':
                    continue
                info = obj(payload.get('info'))
                total = obj(info.get('total_token_usage'))
                last = obj(info.get('last_token_usage'))
                fields = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens')
                if total and all(number(total.get(k, 0)) is not None for k in fields):
                    current = {k: total.get(k, 0) for k in fields}
                    if previous == current:
                        continue
                    usage = {k: max(0, current[k] - previous.get(k, 0)) for k in fields}
                    event_time = stamp(row.get('timestamp'))
                    if not previous and forked and created is not None and event_time is not None and event_time >= created:
                        if not last or number(last.get('input_tokens')) is None or number(last.get('output_tokens')) is None:
                            raise ValueError('fork baseline unavailable')
                        usage = last
                    previous = current
                else:
                    usage = last
                if not usage:
                    continue
                inputs, outputs, read, write = (number(usage.get(k, 0)) for k in fields)
                if any(v is None for v in (inputs, outputs, read, write)):
                    continue
                if inputs + outputs <= 0:
                    continue  # Cache/detail reconciliation is not another request.
                key = 'cx:' + str((row.get('timestamp'), tuple(sorted(total.items())) if total else tuple(sorted(last.items())), model))
                event = token_event(key, session, row.get('timestamp'), model, max(0, inputs-read-write), outputs, read, write)
                if event:
                    event['totalTokens'] = inputs + outputs
                    if 'cached_input_tokens' not in (total or last):
                        event['inputTokens'] = None
                        event['cacheReadInputTokens'] = None
                    if 'cache_write_input_tokens' not in (total or last):
                        event['cacheCreationInputTokens'] = None
                    if read + write > inputs:
                        event['inputTokens'] = event['cacheReadInputTokens'] = event['cacheCreationInputTokens'] = None
            else:
                message = obj(row.get('message'))
                usage = obj(message.get('usage') or row.get('usage'))
                if (row.get('type') != 'assistant' and message.get('role') != 'assistant') or not usage:
                    continue
                mid = message.get('id') or row.get('messageId') or row.get('requestId') or row.get('uuid')
                if not mid:
                    continue  # No stable identity: cannot guarantee deduplication.
                key = 'cl:' + str(mid)
                event = token_event(key, row.get('sessionId') or session, row.get('timestamp') or message.get('timestamp'), message.get('model', 'unknown'), usage.get('input_tokens'), usage.get('output_tokens'), usage.get('cache_read_input_tokens', 0), usage.get('cache_creation_input_tokens', 0))
            if event and (event.get('totalTokens') or sum(event[k] or 0 for k in BUCKETS)) > 0:
                # Hash keys: they are bookkeeping identities, not display text.
                event['key'] = hashlib.sha256(event['key'].encode()).hexdigest()
                events[event['key']] = event
    if invalid_rows and not valid_rows:
        raise ValueError("invalid accounting log")
    return list(events.values())


def parse_codex_timing(path):
    """Read Codex's per-turn wall-clock timings and cumulative turn tokens.

    New Codex transcripts emit task_complete with time_to_first_token_ms and
    duration_ms, and token_usage_record with the final turn_token_usage. Those
    are the native measurements behind the missing TTFT/speed columns.
    """
    completed, outputs = {}, {}
    try:
        with path.open(encoding='utf-8') as handle:
            for line in handle:
                try:
                    row = obj(json.loads(line))
                except ValueError:
                    continue
                payload = obj(row.get('payload'))
                kind = row.get('type')
                if kind == 'event_msg':
                    event = payload.get('type')
                    if event == 'task_complete':
                        turn = payload.get('turn_id') or payload.get('root_turn_id')
                        completed_at = stamp(payload.get('completed_at')) or stamp(row.get('timestamp'))
                        started_at = stamp(payload.get('started_at')) or completed_at
                        duration = number(payload.get('duration_ms'))
                        ttft = number(payload.get('time_to_first_token_ms'))
                        if isinstance(turn, str) and completed_at is not None and duration is not None and ttft is not None and duration > 0:
                            completed[turn] = {'turn': turn, 'startedAt': started_at,
                                               'completedAt': completed_at,
                                               'durationMs': duration, 'ttftMs': ttft}
                elif kind == 'token_usage_record':
                    turn = payload.get('turn_id') or payload.get('root_turn_id')
                    usage = obj(payload.get('turn_token_usage'))
                    output = number(usage.get('output_tokens'))
                    if isinstance(turn, str) and output is not None:
                        outputs[turn] = output
    except (OSError, UnicodeError):
        return []
    rows = []
    for turn, row in completed.items():
        output = outputs.get(turn)
        if output is None:
            continue
        generation_ms = row['durationMs'] - row['ttftMs']
        rows.append({**row, 'outputTokens': output,
                     'tokensPerSecond': output / (generation_ms / 1000.0) if generation_ms > 0 and output > 0 else None})
    return rows


def aggregate_codex_timing(rows, now):
    """Average today's Codex TTFT and generation speed across turns."""
    today = datetime.fromtimestamp(now).astimezone().date()
    selected, seen = [], set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get('turn') in seen:
            continue
        started_at = stamp(row.get('startedAt')) or stamp(row.get('completedAt'))
        if started_at is None or datetime.fromtimestamp(started_at).astimezone().date() != today:
            continue
        seen.add(row.get('turn'))
        selected.append(row)
    if not selected:
        return {}
    # Match Tokei's display rules: TTFT is a median of requests within 120 s;
    # speed is total output tokens / total generation time, with implausible
    # samples (too few tokens, too short/long timing, >3000 tok/s) excluded.
    ttfts = []
    usable = []
    for row in selected:
        output = number(row.get('outputTokens'))
        duration = number(row.get('durationMs'))
        ttft = number(row.get('ttftMs'))
        if ttft is not None and 0 <= ttft <= 120000:
            ttfts.append(ttft)
        if output is None or duration is None or ttft is None or output < 20:
            continue
        generation = (duration - ttft) / 1000.0
        if generation <= 0.2 or generation > 1800:
            continue
        speed = output / generation
        if speed <= 3000:
            usable.append((output, generation))
    result = {'performanceTurns': len(selected), 'ttftSamples': len(ttfts)}
    if ttfts:
        result['ttftSeconds'] = round(statistics.median(ttfts) / 1000.0, 2)
    if usable:
        result['tokensPerSecond'] = round(sum(o for o, _ in usable) / sum(g for _, g in usable), 1)
    return result


def aggregate(events, now):
    today = datetime.fromtimestamp(now).astimezone().date()
    dates = [(today-timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    days = {d: {'date': d, 'tokens': 0, 'requests': 0} for d in dates}
    models, today_models, seen = {}, {}, set()
    activity = None
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('key'), str):
            continue
        if event.get('key') in seen:
            continue
        seen.add(event.get('key'))
        when = stamp(event.get('time'))
        if when is None or when > now + 60:
            continue
        values = [number(event.get(k)) for k in BUCKETS]
        total = number(event.get('totalTokens'))
        if total is None:
            if any(v is None for v in values):
                continue
            total = sum(values)
        day = datetime.fromtimestamp(when).astimezone().date().isoformat()
        activity = max(activity or when, when)
        model = event.get('model') if isinstance(event.get('model'), str) else 'unknown'
        model = model[:160]
        bucket = models.setdefault(model, dict.fromkeys(BUCKETS, 0))
        for k, v in zip(BUCKETS, values):
            bucket[k] = bucket[k] + v if bucket[k] is not None and v is not None else None
        if day in days:
            days[day]['tokens'] += total
            days[day]['requests'] += 1
        if day == today.isoformat():
            today_models[model] = today_models.get(model, 0) + total
    return {'todayTokens': days[dates[-1]]['tokens'], 'todayRequests': days[dates[-1]]['requests'], 'sevenTokens': sum(d['tokens'] for d in days.values()), 'sevenRequests': sum(d['requests'] for d in days.values()), 'days': list(days.values()), 'models': models, 'todayModels': today_models, 'lastActivityMs': activity * 1000 if activity is not None else None, 'scope': 'tool', 'detailScope': '累计', 'statsDate': today.isoformat()}


class NativeStats:
    """Incremental metadata cache; unchanged transcripts are never reparsed."""
    def __init__(self, home, cache):
        self.home, self.cache = Path(home), cache

    def scan(self, agent, now):
        import os
        if agent == 'codex':
            root = Path(os.environ.get('CODEX_HOME', self.home / '.codex')) if self.home == Path.home() else self.home / '.codex'
            paths = list((root / 'sessions').rglob('*.jsonl')) + list((root / 'archived_sessions').rglob('*.jsonl'))
        else:
            root = Path(os.environ.get('CLAUDE_CONFIG_DIR', self.home / '.claude')) if self.home == Path.home() else self.home / '.claude'
            paths = list((root / 'projects').rglob('*.jsonl'))
        old, fresh, errors = obj(self.cache.get(agent)), {}, []
        for path in paths:
            key = str(path)
            entry = obj(old.get(key))
            try:
                stat = path.stat()
                signature = [stat.st_ino, stat.st_size, stat.st_mtime_ns]
                if entry.get('signature') != signature:
                    entry = {'signature': signature, 'events': parse_native(path, agent)}
                    if agent == 'codex':
                        entry['timing'] = parse_codex_timing(path)
                elif agent == 'codex' and 'timing' not in entry:
                    entry['timing'] = parse_codex_timing(path)
                fresh[key] = entry
            except (OSError, ValueError, TypeError):
                errors.append('本地统计读取失败')
                if entry:
                    fresh[key] = entry
        self.cache[agent] = fresh
        result = aggregate([r for e in fresh.values() for r in e.get('events', [])], now) if paths else None
        if agent == 'codex' and result is not None:
            timing = [row for entry in fresh.values() for row in entry.get('timing', []) if isinstance(row, dict)]
            performance = aggregate_codex_timing(timing, now)
            if performance:
                result.update(performance)
        return result, bool(errors)


def opencode_origins(entries):
    """Read only fork relationships; reuse the existing parsed token events.

    OpenCode may give copied messages new IDs. An identical accounting event
    in a known ancestor/child session is an inherited prefix, not a new call.
    """
    import sqlite3
    from contextlib import closing
    parents = {}
    for key in entries:
        if not key.startswith('opencode-db:'):
            continue
        path = Path(key[len('opencode-db:'):])
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
                connection.execute('PRAGMA query_only=ON')
                columns = {r[1] for r in connection.execute('PRAGMA table_info(session)')}
                if {'id', 'parent_id'} <= columns:
                    parents.update({str(a): str(b) for a, b in connection.execute('SELECT id, parent_id FROM session WHERE parent_id IS NOT NULL')})
        except (OSError, sqlite3.Error):
            return None
    return parents


def account_for_forks(events, parents):
    def ancestors(session):
        result = set()
        while session in parents and session not in result:
            result.add(session)
            session = parents[session]
        result.add(session)
        return result
    seen, result = {}, []
    for event in events:
        session = str(event.get('session'))
        signature = (event.get('time'), str(event.get('model')), *(event.get(k) for k in BUCKETS))
        prior = seen.setdefault(signature, [])
        # Exact accounting copies in an explicit ancestor/child pair only.
        # Independent requests and parallel sibling sessions remain distinct.
        if any(old != session and (old in ancestors(session) or session in ancestors(old)) for old in prior):
            continue
        prior.append(session)
        result.append(event)
    return result
