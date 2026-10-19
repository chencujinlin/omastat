#!/usr/bin/env python3
"""Controlled offscreen comparison. Does not measure compositor/GPU rendering."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time


def counters(pid):
    text=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'cpu':(int(text[11])+int(text[12]))/os.sysconf('SC_CLK_TCK'), 'rssKiB':int(text[21])*os.sysconf('SC_PAGE_SIZE')//1024}


def measure(root, kind, seconds, fixture, label, output):
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',XDG_CURRENT_DESKTOP='',QT_STYLE_OVERRIDE='Fusion',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(fixture/'run'),XDG_CONFIG_HOME=str(fixture/'config'),XDG_STATE_HOME=str(fixture/'state'),XDG_CACHE_HOME=str(fixture/'cache'),OMASTAT_NO_COLLECT='1',OMASTAT_TEST_HOME=str(fixture/'home'))
    if kind=='ui-hidden':
        settings=json.loads((root/'config.json').read_text())
        settings['startHidden']=True
        (root/'config.json').write_text(json.dumps(settings))
    if kind=='sampler': command=['python3',str(root/'scripts/vitals_sampler.py')]
    elif kind=='reader': command=['python3',str(root/'scripts/agents_service.py'),'--no-collect','--home',str(fixture/'home'),'--config',str(root/'config.json')]
    else: command=['quickshell','-p',str(root),'-n']
    log_path=output.parent/f'{label}-{kind}.log'
    with log_path.open('w') as log:
        process=subprocess.Popen(command,env=env,stdout=log if kind.startswith('ui') else subprocess.DEVNULL,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
        try:
            time.sleep(3)
            if process.poll() is not None:
                return {'version':label,'process':kind,'error':'startup failed','log':str(log_path)}
            first=counters(process.pid)
            start=time.monotonic()
            samples=[]
            for _ in range(seconds):
                time.sleep(1)
                samples.append(counters(process.pid))
            elapsed=time.monotonic()-start
            result={'version':label,'process':kind,'seconds':round(elapsed,2),'cpuPercentOneCore':round(100*(samples[-1]['cpu']-first['cpu'])/elapsed,3),'rssKiB':max(s['rssKiB'] for s in samples),'backend':'offscreen/software'}
            if kind.startswith('ui') and 'Configuration Loaded' not in log_path.read_text(): result['error']='QML did not load'
            return result
        finally:
            os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--seconds',type=int,default=15)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='omastat-performance-') as temporary:
        fixture=Path(temporary)
        (fixture/'run').mkdir(mode=0o700)
        usage=fixture/'state/omarchy/agents/usage';usage.mkdir(parents=True)
        # A fixed, explicitly synthetic workload isolates UI overhead. No auth,
        # network, or real transcripts are read during this benchmark.
        for agent in ('codex','claude','pi','opencode','deepseek-harness','fireworks'):
            (usage/f'{agent}.json').write_text(json.dumps({'id':agent,'updatedAt':datetime.now(timezone.utc).isoformat(),'todayTotalTokens':12345,'todayPrompts':12,'limits':[],'hasLocalStats':True,'recentDays':[],'modelUsage':{}}))
        for label,original in [('before',args.before),('after',args.after)]:
            root=fixture/(label+'-source')
            shutil.copytree(original,root,ignore=shutil.ignore_patterns('.git','.aws','.codex','.agents','__pycache__','*.log','stage1-*.png'))
            initial=json.loads((root/'config.json').read_text())
            initial['startHidden']=False
            (root/'config.json').write_text(json.dumps(initial))
            for kind in ['ui','ui-hidden','sampler']+(['reader'] if (root/'scripts/agents_service.py').exists() else []):
                row=measure(root,kind,args.seconds,fixture,label,args.output)
                rows.append(row)
                args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps(row),flush=True)


if __name__=='__main__': main()
