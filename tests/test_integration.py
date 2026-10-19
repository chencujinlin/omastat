import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from integrate import integrate
from vitals_sampler import CpuMeter, DiskIoMeter, _safe_sample, build_sample, read_disk, read_mem, top_memory_processes


class IntegrationTests(unittest.TestCase):
    def test_top_memory_processes_groups_names_and_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)/'proc'; proc.mkdir()
            for pid, name, pages in (('1','chrome',100),('2','chrome',50),('3','shell',30),('4','tiny',1)):
                d=proc/pid; d.mkdir(); (d/'comm').write_text(name+'\n'); (d/'statm').write_text(f'0 {pages} 0 0 0 0 0\n')
            rows=top_memory_processes(100000, limit=2, proc_root=str(proc), page_size=4096)
            self.assertEqual([r['name'] for r in rows], ['chrome','shell'])
            self.assertEqual(rows[0]['pct'], round(150*4096*100/(100000*1024), 1))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config=self.root/'config'
        self.shell=self.config/'omarchy/shell.json'
        self.shell.parent.mkdir(parents=True)
        self.original={'custom':'untouched','bar':{'position':'top','layout':{'left':[{'id':'omarchy.workspaces'}],'right':[{'id':'chencu.agents'},{'id':'omarchy.audio'}]}}}
        self.shell.write_text(json.dumps(self.original))

    def test_install_idempotent_preserves_bar_and_backs_up(self):
        integrate(ROOT,self.config)
        first=self.shell.read_text()
        integrate(ROOT,self.config)
        self.assertEqual(first,self.shell.read_text())
        data=json.loads(first)
        self.assertEqual(data['custom'],'untouched')
        self.assertEqual(data['bar']['layout']['right'][:2],self.original['bar']['layout']['right'])
        self.assertEqual(data['bar']['layout']['right'].count({'id':'chencu.omastat','metric':'none'}),1)
        self.assertEqual(len(list(self.shell.parent.glob('shell.json.bak.omastat.*'))),1)
        integrate(ROOT,self.config,remove=True)
        self.assertEqual(json.loads(self.shell.read_text()),self.original)

    def test_custom_window_rules_preserved(self):
        rule=self.config/'hypr/vitals.lua';rule.parent.mkdir()
        rule.write_text('-- custom user settings\n')
        integrate(ROOT,self.config)
        self.assertEqual(rule.read_text(),'-- custom user settings\n')
        integrate(ROOT,self.config,remove=True)
        self.assertTrue(rule.is_file())

    def test_migrates_exact_old_rule_and_restores_it(self):
        rule=self.config/'hypr/vitals.lua';rule.parent.mkdir()
        previous='-- old owned rule\no.window({title="old"}, {float=true})\n'
        rule.write_text(previous)
        with patch('integrate.OLD_RULE_HASH',hashlib.sha256(previous.encode()).hexdigest()):
            integrate(ROOT,self.config)
        self.assertEqual(rule.read_text(),(ROOT/'hypr/vitals.lua').read_text())
        integrate(ROOT,self.config,remove=True)
        self.assertEqual(rule.read_text(),previous)

    def test_existing_widget_is_not_removed(self):
        data=self.original
        data['bar']['layout']['right'].append({'id':'chencu.omastat','metric':'cpu'})
        self.shell.write_text(json.dumps(data))
        integrate(ROOT,self.config)
        integrate(ROOT,self.config,remove=True)
        self.assertIn({'id':'chencu.omastat','metric':'cpu'},json.loads(self.shell.read_text())['bar']['layout']['right'])

    def test_install_script_in_isolated_home(self):
        hypr=self.config/'hypr';hypr.mkdir()
        (hypr/'bindings.lua').write_text('-- existing\n')
        (hypr/'hyprland.lua').write_text('-- existing\n')
        env=dict(os.environ,OMASTAT_HOME=str(self.root),XDG_CONFIG_HOME=str(self.config),XDG_DATA_HOME=str(self.root/'data'),XDG_STATE_HOME=str(self.root/'state'),WAYLAND_DISPLAY='')
        subprocess.run(['bash',str(ROOT/'install.sh')],env=env,check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['bash',str(ROOT/'install.sh')],env=env,check=True,stdout=subprocess.DEVNULL)
        self.assertTrue((self.root/'.local/bin/omastat').is_symlink())
        self.assertEqual((hypr/'bindings.lua').read_text().count('omastat toggle'),1)
        self.assertNotIn('float = true',(hypr/'vitals.lua').read_text())
        self.assertIn('-- existing',(hypr/'bindings.lua').read_text())


class TelemetryTests(unittest.TestCase):
    def test_unreadable_memory_and_disk_unknown(self):
        with patch('builtins.open',side_effect=OSError):
            self.assertIsNone(read_mem()['pct'])
        with patch('vitals_sampler.os.statvfs',side_effect=OSError):
            self.assertIsNone(read_disk()['pct'])

    def test_missing_cpu_unknown(self):
        with patch.object(CpuMeter,'_read_stat',return_value=None):
            self.assertIsNone(CpuMeter().step())

    def test_disk_rates_use_deltas_and_elapsed_time(self):
        with patch('vitals_sampler.read_text',return_value='0 0 100 0 0 0 200'):
            meter=DiskIoMeter()
            self.assertIsNone(meter.step()['readBps'])
        meter.previous=(100*512,200*512,10)
        with patch('vitals_sampler.read_text',return_value='0 0 120 0 0 0 240'),patch('vitals_sampler.time.monotonic',return_value=12):
            self.assertEqual(meter.step(),{'readBps':5120,'writeBps':10240})


    def test_one_gpu_failure_does_not_hide_cpu_or_memory(self):
        from unittest.mock import Mock
        cpu, gpu = Mock(), Mock()
        cpu.step.return_value = 12.5
        gpu.step.side_effect = OSError
        sample = build_sample(cpu, gpu)
        self.assertEqual(sample['cpu']['pct'], 12.5)
        self.assertIsNone(sample['gpu']['pct'])
        self.assertIsNotNone(sample['mem']['totalGb'])

    def test_sampler_failure_never_emits_fake_zero(self):
        with patch('vitals_sampler.build_sample',side_effect=OSError):
            value=_safe_sample(None,None)
            self.assertIsNone(value['cpu']['pct'])
            self.assertIsNone(value['mem']['pct'])
            self.assertIsNone(value['disk']['pct'])
            self.assertIn('error',value)


if __name__=='__main__': unittest.main()
