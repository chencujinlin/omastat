import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deepseek_balance import DeepSeekBalance, fetch_balance, fetch_dsh_balance, read_api_key, read_dsh_credentials

FAKE_KEY = 'sk-test-1234567890'


class BalanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        dsh = self.root / '.dsh'
        dsh.mkdir()
        (dsh / '.credentials.yaml').write_text(
            'version: 1\n'
            'records:\n'
            '  client-connection/browser-session:\n'
            '    kind: grant\n'
            '    payload:\n'
            '      version: 1\n'
            '      secret: unrelated\n'
            '      refs:\n'
            f'        DEEPSEEK_API_KEY: {FAKE_KEY}\n'
        )

    def test_reads_key_from_dsh_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(read_api_key(self.root), FAKE_KEY)

    def test_env_key_takes_precedence(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'sk-env-1234567890'}, clear=True):
            self.assertEqual(read_api_key(self.root), 'sk-env-1234567890')

    def test_missing_key_is_unconfigured(self):
        with tempfile.TemporaryDirectory() as empty, patch.dict(os.environ, {}, clear=True):
            balance = DeepSeekBalance(empty)
            snap = balance.snapshot()
            self.assertEqual(snap['state'], 'unconfigured')
            self.assertFalse(snap['configured'])
            self.assertIsNone(snap['total'])

    def test_balance_is_fetched_and_key_is_not_exposed(self):
        data = {'available': True, 'currency': 'CNY', 'total': 5.11,
                'granted': 1.03, 'toppedUp': 4.08, 'fetchedAtMs': int(time.time() * 1000)}
        with patch.dict(os.environ, {}, clear=True):
            balance = DeepSeekBalance(self.root, fetcher=lambda key: data)
            snap = balance.refresh_sync()
        self.assertEqual(snap['state'], 'ok')
        self.assertEqual(snap['total'], 5.11)
        self.assertEqual(snap['currency'], 'CNY')
        self.assertNotIn('sk-', json.dumps(snap))

    def test_fetch_error_does_not_expose_key(self):
        def fail(_key):
            raise RuntimeError('network down')

        with patch.dict(os.environ, {}, clear=True):
            balance = DeepSeekBalance(self.root, fetcher=fail)
            snap = balance.refresh_sync()
        self.assertEqual(snap['state'], 'error')
        self.assertIsNone(snap['total'])
        self.assertNotIn('sk-', json.dumps(snap))

    def test_reads_dsh_account_grant_and_prefers_it(self):
        (self.root / '.dsh').mkdir(exist_ok=True)
        (self.root / '.dsh/.credentials.yaml').write_text(
            'version: 1\n'
            'records:\n'
            '  deepseek-account-platform/default:\n'
            '    kind: grant\n'
            '    payload:\n'
            '      version: 1\n'
            '      token: dsh-test-token-123456\n'
            '      issuer: https://platform.deepseek.com\n'
            'refs:\n'
            f'  DEEPSEEK_API_KEY: {FAKE_KEY}\n'
        )
        with patch.dict(os.environ, {}, clear=True):
            token, issuer = read_dsh_credentials(self.root)
            self.assertEqual(token, 'dsh-test-token-123456')
            self.assertEqual(issuer, 'https://platform.deepseek.com')
            data = {'source': 'dsh', 'currency': 'CNY', 'total': 4.03,
                    'normal': 4.03, 'bonus': 0.0, 'available': True,
                    'fetchedAtMs': int(time.time() * 1000)}
            balance = DeepSeekBalance(self.root, fetcher=lambda _: data)
            snap = balance.refresh_sync()
        self.assertEqual(snap['state'], 'ok')
        self.assertEqual(snap['source'], 'dsh')
        self.assertAlmostEqual(snap['total'], 4.03)
        self.assertNotIn('dsh-test-token', json.dumps(snap))

    def test_dsh_platform_summary_parser(self):
        payload = {'code': 0, 'msg': 'ok', 'data': {'biz_code': 0, 'biz_msg': 'ok', 'biz_data': {
            'normal_wallets': [{'currency': 'CNY', 'balance': '4.0349700400000000'}],
            'bonus_wallets': [{'currency': 'CNY', 'balance': '0'}],
        }}}

        class Response:
            status = 200
            def read(self):
                return json.dumps(payload).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_exc):
                return False

        token = 'dsh-test-token-123456'
        with patch('deepseek_balance.urllib.request.urlopen', return_value=Response()) as opened:
            result = fetch_dsh_balance(token)
            request = opened.call_args.args[0]
            self.assertEqual(request.headers.get('X-dsh-auth-token'), token)
        self.assertEqual(result['source'], 'dsh')
        self.assertEqual(result['currency'], 'CNY')
        self.assertAlmostEqual(result['total'], 4.03497004)
        self.assertNotIn(token, json.dumps(result))

    def test_official_response_parser_prefers_cny(self):
        payload = {
            'is_available': True,
            'balance_infos': [
                {'currency': 'USD', 'total_balance': '1.00', 'granted_balance': '0.00', 'topped_up_balance': '1.00'},
                {'currency': 'CNY', 'total_balance': '5.11', 'granted_balance': '1.03', 'topped_up_balance': '4.08'},
            ],
        }

        class Response:
            status = 200

            def read(self):
                return json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        with patch('deepseek_balance.urllib.request.urlopen', return_value=Response()) as opened:
            result = fetch_balance(FAKE_KEY)
            request = opened.call_args.args[0]
            self.assertIn(FAKE_KEY, request.headers.get('Authorization'))
            self.assertNotIn(FAKE_KEY, json.dumps({key: value for key, value in result.items() if key != 'key'}))
        self.assertTrue(result['available'])
        self.assertEqual(result['currency'], 'CNY')
        self.assertAlmostEqual(result['total'], 5.11)
        self.assertAlmostEqual(result['granted'], 1.03)
        self.assertAlmostEqual(result['toppedUp'], 4.08)


if __name__ == '__main__':
    unittest.main()
