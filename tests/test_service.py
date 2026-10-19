"""Exercise the actual long-running reader without desktop/network access."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from agents_service import atomic_json


class ServiceTests(unittest.TestCase):
    def test_live_reader_recovers_and_continues_without_another_plugin(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            config=base/'config.json';config.write_text('{"agents":["pi"],"refreshSeconds":60}')
            usage=base/'state/omarchy/agents/usage/pi.json'
            record={'id':'pi','updatedAt':datetime.now(timezone.utc).isoformat(),'todayTotalTokens':77,'todayPrompts':2,'limits':[]}
            atomic_json(usage,record)
            env=dict(os.environ,XDG_STATE_HOME=str(base/'state'),XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache'))
            process=subprocess.Popen([sys.executable,str(ROOT/'scripts/agents_service.py'),'--no-collect','--home',str(base),'--config',str(config),'--poll-seconds','0.1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
            def until(predicate):
                for _ in range(20):
                    if not selector.select(timeout=1): self.fail('reader stopped publishing')
                    row=json.loads(process.stdout.readline())['agents'][0]
                    if predicate(row): return row
                self.fail('reader did not observe update')
            try:
                until(lambda r:r['todayTokens']==77)
                usage.write_text('null')
                row=until(lambda r:r['state']=='error')
                self.assertEqual(row['todayTokens'],77)
                record['todayTotalTokens']=88
                atomic_json(usage,record)
                until(lambda r:r['todayTokens']==88 and r['state']=='normal')
                self.assertIsNone(row['lastActivityMs'])
            finally:
                process.terminate();process.wait(timeout=5)
                self.assertEqual(process.stderr.read(),'')
                process.stdout.close();process.stderr.close();selector.close()


if __name__=='__main__': unittest.main()
