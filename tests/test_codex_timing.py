import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from usage_stats import NativeStats, aggregate_codex_timing, parse_codex_timing


class CodexTimingTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()
        self.today = datetime.fromtimestamp(self.now).astimezone().date().isoformat()
        self.old = self.now - 86400 * 2
        self.log = self.root / 'rollout.jsonl'
        rows = [
            {'timestamp': datetime.fromtimestamp(self.now - 1800).astimezone().isoformat(),
             'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 't1',
                                              'completed_at': int(self.now - 120),
                                              'duration_ms': 60000, 'time_to_first_token_ms': 2000}},
            {'timestamp': datetime.fromtimestamp(self.now - 120).astimezone().isoformat(),
             'type': 'token_usage_record', 'payload': {'turn_id': 't1',
                                                       'turn_token_usage': {'output_tokens': 5800}}},
            {'timestamp': datetime.fromtimestamp(self.now - 60).astimezone().isoformat(),
             'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 't2',
                                              'completed_at': int(self.now - 30),
                                              'duration_ms': 32000, 'time_to_first_token_ms': 2000}},
            {'timestamp': datetime.fromtimestamp(self.now - 30).astimezone().isoformat(),
             'type': 'token_usage_record', 'payload': {'turn_id': 't2',
                                                       'turn_token_usage': {'output_tokens': 3000}}},
            {'timestamp': datetime.fromtimestamp(self.old).astimezone().isoformat(),
             'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 'old',
                                              'completed_at': int(self.old),
                                              'duration_ms': 10000, 'time_to_first_token_ms': 1000}},
            {'timestamp': datetime.fromtimestamp(self.old).astimezone().isoformat(),
             'type': 'token_usage_record', 'payload': {'turn_id': 'old',
                                                       'turn_token_usage': {'output_tokens': 900}}},
        ]
        self.log.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')

    def test_parser_keeps_only_complete_turns(self):
        rows = parse_codex_timing(self.log)
        self.assertEqual(len(rows), 3)
        self.assertEqual([row['turn'] for row in rows], ['t1', 't2', 'old'])

    def test_today_aggregate_averages_ttft_and_weights_speed(self):
        performance = aggregate_codex_timing(parse_codex_timing(self.log), self.now)
        self.assertEqual(performance['ttftSeconds'], 2.0)
        self.assertEqual(performance['tokensPerSecond'], 100.0)
        self.assertEqual(performance['performanceTurns'], 2)

    def test_native_scan_exposes_codex_performance(self):
        sessions = self.root / '.codex/sessions/2026/10/19'
        sessions.mkdir(parents=True)
        target = sessions / 'rollout.jsonl'
        target.write_text(self.log.read_text())
        result, failed = NativeStats(self.root, {}).scan('codex', self.now)
        self.assertFalse(failed)
        self.assertEqual(result['ttftSeconds'], 2.0)
        self.assertEqual(result['tokensPerSecond'], 100.0)

    def test_incomplete_timing_is_ignored(self):
        self.log.write_text(json.dumps({'type': 'event_msg', 'payload': {'type': 'task_complete',
                                                                        'turn_id': 'bad',
                                                                        'duration_ms': 1000}}) + '\n')
        self.assertEqual(parse_codex_timing(self.log), [])


if __name__ == '__main__':
    main()
