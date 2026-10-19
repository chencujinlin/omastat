import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from agents_service import Store, TTL, atomic_json
from usage_stats import account_for_forks, aggregate, parse_native


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()
        self.store = Store(self.root/'usage', self.root/'state', home=self.root, cache_home=self.root/'cache')

    def write(self, agent='codex', **kwargs):
        record = {'id': agent, 'updatedAt': datetime.fromtimestamp(self.now, timezone.utc).isoformat(), 'limits': [], 'todayTotalTokens': 12}
        record.update(kwargs)
        atomic_json(self.root/'usage'/f'{agent}.json', record)
        return record

    def snapshot(self, ids=('codex',), now=None):
        return self.store.snapshot(ids, self.now if now is None else now, 300)

    def limit(self, reset=None):
        return [{'percent': .6, 'label': 'Weekly', 'resetsAt': datetime.fromtimestamp(reset or self.now+7200, timezone.utc).isoformat()}]

    def test_dsh_snapshot_exposes_balance_frame(self):
        self.write('deepseek-harness')
        self.store.poll(['deepseek-harness'], self.now)
        row = self.snapshot(['deepseek-harness'])['agents'][0]
        self.assertIn('apiBalance', row)
        self.assertIsInstance(row['apiBalance'], dict)

    def test_performance_metrics_are_passed_through(self):
        self.write('deepseek-harness', performance={'today': {'averageTtftSeconds': 1.25, 'tokensPerSecond': 210.0, 'calls': 3}, 'allTime': {'averageTtftSeconds': 1.5, 'tokensPerSecond': 200.0, 'calls': 30}})
        self.store.poll(['deepseek-harness'], self.now)
        row = self.snapshot(['deepseek-harness'])['agents'][0]
        self.assertAlmostEqual(row['ttftSeconds'], 1.25)
        self.assertAlmostEqual(row['tokensPerSecond'], 210.0)

    def test_fresh_source_cannot_mask_stale_neighbor(self):
        self.write('codex')
        self.write('claude', updatedAt=datetime.fromtimestamp(self.now-1000, timezone.utc).isoformat())
        self.store.poll(['codex','claude'], self.now)
        snap = self.snapshot(['codex','claude'])
        self.assertEqual([a['state'] for a in snap['agents']], ['unknown','stale'])
        self.assertEqual(snap['state'], 'stale')
        self.assertTrue(self.store.due('claude', self.now, 300))
        self.assertFalse(self.store.due('codex', self.now, 300))
        self.assertTrue(self.store.due('codex', self.now+301, 300))

    def test_repeated_reads_never_renew_quota(self):
        self.write(limits=self.limit(self.now+TTL+7200))
        self.store.poll(['codex'], self.now)
        self.store.signatures.clear()
        self.store.poll(['codex'], self.now+TTL-1)
        self.assertEqual(self.store.limits['codex']['at'], self.now)
        self.assertIsNone(self.snapshot(now=self.now+TTL+1)['agents'][0]['bestLimit'])

    def test_expiration_without_file_change(self):
        self.write(limits=self.limit())
        self.store.poll(['codex'], self.now)
        self.assertIsNotNone(self.snapshot()['agents'][0]['bestLimit'])
        self.assertIsNone(self.snapshot(now=self.now+TTL+1)['agents'][0]['bestLimit'])

    def test_claude_fallback_uses_actual_probe_time(self):
        atomic_json(self.root/'cache/omarchy/agent-usage/claude-limits.json', {'fetchedAtMs': (self.now-TTL-1)*1000, 'limits':self.limit()})
        self.write('claude', limits=self.limit(), usageStatusText='Sign-in expired')
        self.store.poll(['claude'],self.now)
        row=self.snapshot(['claude'])['agents'][0]
        self.assertIsNone(row['bestLimit'])
        self.assertEqual(row['quotaHealth'],'error')

    def test_reset_removes_old_ratio(self):
        self.write(limits=self.limit(self.now+30))
        self.store.poll(['codex'], self.now)
        self.assertIsNone(self.snapshot(now=self.now+31)['agents'][0]['bestLimit'])

    def test_missing_and_corrupt_keep_last_valid(self):
        self.write(limits=self.limit())
        self.store.poll(['codex'], self.now)
        path = self.root/'usage/codex.json'
        path.write_text('{secret session body:')
        self.store.poll(['codex'], self.now+1)
        self.assertEqual(self.snapshot()['agents'][0]['state'], 'error')
        self.assertNotIn('secret', json.dumps(self.snapshot()))
        path.unlink()
        self.store.poll(['codex'], self.now+2)
        self.assertIsNotNone(self.snapshot()['agents'][0]['bestLimit'])

    def test_null_record_and_invalid_time(self):
        path = self.root/'usage/codex.json'
        path.parent.mkdir()
        for value in ('null', '[]', '{"updatedAt":"no"}', '{"updatedAt":NaN}'):
            path.write_text(value)
            self.store.poll(['codex'], self.now)
            self.assertEqual(self.snapshot()['agents'][0]['state'], 'error')

    def test_failed_collection_keeps_valid_record(self):
        self.write('pi', todayTotalTokens=123)
        self.store.poll(['pi'], self.now)
        self.write('pi', todayTotalTokens=0, collectionErrors=['private text'])
        self.store.poll(['pi'], self.now+1)
        row = self.snapshot(['pi'])['agents'][0]
        self.assertEqual(row['todayTokens'],123)
        self.assertEqual(row['state'],'error')
        self.assertNotIn('private', json.dumps(row))

    def test_midnight_does_not_relabel_yesterday(self):
        self.write('pi')
        self.store.poll(['pi'], self.now)
        tomorrow = self.now+86400
        row = self.snapshot(['pi'], now=tomorrow)['agents'][0]
        self.assertIsNone(row['todayTokens'])
        self.assertTrue(self.store.due('pi', tomorrow, 100000))

    def test_cooldown_even_manual(self):
        self.store.attempts['pi'] = self.now
        self.assertFalse(self.store.due('pi', self.now+10,300,True))
        self.assertTrue(self.store.due('pi', self.now+31,300,True))
        self.assertFalse(self.store.due('pi', self.now+299,300))

    def test_malformed_nested_fields_are_unknown_and_do_not_crash(self):
        self.write('pi', recentDays=[{'date': []}, None], modelUsage={'m': []})
        self.store.poll(['pi'],self.now)
        row=self.snapshot(['pi'])['agents'][0]
        self.assertIsNone(row['sevenTokens'])
        atomic_json(self.root/'cache/omarchy/agents-extension/local-tools.json', {'pi': {'source': {'records': [{'key':[], 'time':self.now}]}}})
        self.store.scan_stats(['pi'],self.now)
        self.assertEqual(self.snapshot(['pi'])['agents'][0]['tokenState'],'error')

    def test_unknown_not_zero(self):
        self.write('opencode', todayTotalTokens=None)
        self.store.poll(['opencode'],self.now)
        row=self.snapshot(['opencode'])['agents'][0]
        self.assertIsNone(row['todayTokens'])
        self.assertIsNone(row['todayPrompts'])
        self.assertIsNone(row['sevenTokens'])
        self.assertIsNone(row['lastActivityMs'])
        self.assertEqual(row['quotaState'],'unsupported')

    def test_cache_survives_restart_without_new_timestamp(self):
        self.write(limits=self.limit())
        self.store.poll(['codex'],self.now)
        self.store.save()
        restored=Store(self.root/'usage',self.root/'state',home=self.root)
        restored.poll(['codex'], self.now+10)
        self.assertEqual(restored.limits['codex']['at'],self.now)

    def test_unavailable_quota_can_reuse_cache_until_ttl(self):
        self.write(limits=self.limit())
        self.store.poll(['codex'],self.now)
        self.write(updatedAt=datetime.fromtimestamp(self.now+20,timezone.utc).isoformat(), retryAdvised=True)
        self.store.poll(['codex'],self.now+20)
        row=self.snapshot(now=self.now+20)['agents'][0]
        self.assertTrue(row['cachedQuota'])
        self.assertEqual(row['state'],'error')
        self.assertEqual(row['quotaHealth'],'error')

    def test_cache_drops_unrelated_private_payloads(self):
        self.write('pi', sessionBody='private session text', authHelpText='private key')
        self.store.poll(['pi'],self.now)
        self.store.save()
        self.assertNotIn('private', (self.root/'state/agents-cache.json').read_text())

    def test_wrong_provider_is_isolated(self):
        self.write('pi', id='other')
        self.write('codex')
        self.store.poll(['pi','codex'],self.now)
        self.assertEqual([a['state'] for a in self.snapshot(['pi','codex'])['agents']],['error','unknown'])


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'session.jsonl'
        self.now=datetime.now().replace(hour=12,minute=0,second=0,microsecond=0).timestamp()

    def parse(self, rows, agent='codex'):
        self.path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        return parse_native(self.path,agent)

    def codex(self, t, inputs, outputs, cache=0, reason=0):
        return {'type':'event_msg','timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':inputs,'output_tokens':outputs,'cached_input_tokens':cache,'reasoning_output_tokens':reason},'last_token_usage':{'input_tokens':999}}}}

    def test_codex_cumulative_repeats_forks_and_reasoning(self):
        rows=[self.codex(self.now-3,100,20,40,15),self.codex(self.now-2,100,20,40,15),self.codex(self.now-1,140,30,50,20)]
        events=self.parse(rows)
        result=aggregate(events+copy.deepcopy(events),self.now)
        self.assertEqual(result['todayTokens'],170)
        self.assertEqual(result['todayRequests'],2)
        model=result['models']['unknown']
        self.assertEqual(model['inputTokens'],90)
        self.assertEqual(model['cacheReadInputTokens'],50)
        self.assertEqual(model['outputTokens'],30)

    def test_cache_reconciliation_does_not_create_another_call(self):
        events=self.parse([self.codex(self.now-2,100,20,20),self.codex(self.now-1,100,20,40)])
        result=aggregate(events,self.now)
        self.assertEqual(result['todayTokens'],120)
        self.assertEqual(result['todayRequests'],1)

    def test_unknown_cache_breakdown_is_not_zero(self):
        row=self.codex(self.now-1,100,20)
        del row['payload']['info']['total_token_usage']['cached_input_tokens']
        events=self.parse([row])
        result=aggregate(events,self.now)
        self.assertEqual(result['todayTokens'],120)
        self.assertIsNone(result['models']['unknown']['cacheReadInputTokens'])

    def test_codex_fork_without_prefix_uses_last_request_not_inherited_total(self):
        timestamp=datetime.fromtimestamp(self.now-1,timezone.utc).isoformat()
        metadata={'type':'session_meta','payload':{'id':'child','forked_from_id':'parent','timestamp':timestamp}}
        event=self.codex(self.now-1,1000,200,100)
        event['payload']['info']['last_token_usage']={'input_tokens':10,'output_tokens':5,'cached_input_tokens':2}
        result=aggregate(self.parse([metadata,event]),self.now)
        self.assertEqual(result['todayTokens'],15)

    def test_claude_chunks_and_copied_messages_once(self):
        row={'type':'assistant','timestamp':datetime.fromtimestamp(self.now-1,timezone.utc).isoformat(),'message':{'id':'msg-stable','usage':{'input_tokens':10,'output_tokens':20,'cache_read_input_tokens':30,'cache_creation_input_tokens':5}}}
        last=copy.deepcopy(row);last['message']['usage']['output_tokens']=25
        events=self.parse([row,last],'claude')
        result=aggregate(events+events,self.now)
        self.assertEqual(result['todayTokens'],70)
        self.assertEqual(result['todayRequests'],1)

    def test_midnight_and_seven_day_window(self):
        events=self.parse([self.codex(self.now-86400,100,20),self.codex(self.now,120,30)])
        result=aggregate(events,self.now)
        self.assertEqual(result['todayTokens'],30)
        self.assertEqual(result['sevenTokens'],150)
        tomorrow=aggregate(events,self.now+86400)
        self.assertEqual(tomorrow['todayTokens'],0)
        self.assertEqual(tomorrow['lastActivityMs'],self.now*1000)
        week_later=aggregate(events,self.now+7*86400)
        self.assertEqual(week_later['sevenTokens'],0)

    def test_opencode_fork_copies_with_new_ids_are_not_billed_twice(self):
        original={'key':'old','session':'parent','time':self.now,'model':'m','inputTokens':10,'outputTokens':20,'cacheReadInputTokens':5,'cacheCreationInputTokens':0}
        inherited={**original,'key':'new-fork-id','session':'child'}
        new_call={**inherited,'key':'new-call','time':self.now+1}
        events=account_for_forks([original,inherited,new_call],{'child':'parent'})
        self.assertEqual(len(events),2)
        self.assertEqual(aggregate(events,self.now+2)['todayTokens'],70)
        unrelated={**original,'key':'other','session':'unrelated'}
        self.assertEqual(len(account_for_forks([original,unrelated],{})),2)
        siblings=[{**original,'session':'child1'},{**original,'session':'child2'}]
        self.assertEqual(len(account_for_forks(siblings,{'child1':'parent','child2':'parent'})),2)

    def test_unknown_usage_not_counted(self):
        self.assertEqual(self.parse([{'type':'assistant','message':{'id':'x','usage':{'input_tokens':None}}}],'claude'),[])


if __name__=='__main__':
    unittest.main()
