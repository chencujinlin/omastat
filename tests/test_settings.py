"""Settings merge: checked-in defaults plus the gitignored local overlay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from agents_service import AGENT_ORDER, read_settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config.json'

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def test_local_overlay_overrides_agents_and_interval(self):
        self.write('config.json', {'agents': ['pi'], 'refreshSeconds': 300})
        self.write('config.local.json', {'agents': ['codex', 'claude'], 'refreshSeconds': 60})
        ids, interval = read_settings(self.config)
        self.assertEqual(ids, ['codex', 'claude'])
        self.assertEqual(interval, 60)

    def test_empty_agent_list_is_respected(self):
        self.write('config.json', {'agents': list(AGENT_ORDER)})
        self.write('config.local.json', {'agents': []})
        ids, _ = read_settings(self.config)
        self.assertEqual(ids, [])

    def test_unknown_only_list_falls_back_to_defaults(self):
        self.write('config.json', {'agents': ['not-an-agent']})
        self.assertEqual(read_settings(self.config)[0], list(AGENT_ORDER))

    def test_canonical_order_and_duplicates(self):
        self.write('config.json', {'agents': ['fireworks', 'codex', 'fireworks', 'deepseek-harness']})
        self.assertEqual(read_settings(self.config)[0], ['deepseek-harness', 'codex', 'fireworks'])

    def test_invalid_overlay_keeps_base(self):
        self.write('config.json', {'agents': ['pi'], 'refreshSeconds': 300})
        (self.root / 'config.local.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(read_settings(self.config), (['pi'], 300))

    def test_refresh_interval_floor(self):
        self.write('config.json', {'agents': ['pi'], 'refreshSeconds': 1})
        self.assertEqual(read_settings(self.config)[1], 60)

    def test_invalid_local_types_do_not_mask_base(self):
        self.write('config.json', {'agents': ['pi'], 'refreshSeconds': 90})
        self.write('config.local.json', {'agents': 'not-a-list', 'refreshSeconds': 'soon'})
        self.assertEqual(read_settings(self.config), (['pi'], 90))

    def test_missing_files_use_all_defaults(self):
        self.assertEqual(read_settings(self.config), (list(AGENT_ORDER), 300))


if __name__ == '__main__':
    unittest.main()
