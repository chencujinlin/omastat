"""Load the application and bar with the installed Quickshell/Omarchy modules."""
import os
import json
import time
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='omastat-qml-smoke-') as d:
    base=Path(d)
    (base/'run').mkdir(mode=0o700)
    tools=base/'bin';tools.mkdir()
    command=tools/'omastat'
    command.write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"running":false,"agentState":"unknown"}\'\n')
    command.chmod(0o755)
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'],QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',XDG_CURRENT_DESKTOP='',QT_STYLE_OVERRIDE='Fusion',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(base/'run'),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),OMASTAT_NO_COLLECT='1',OMASTAT_TEST_HOME=str(base/'native'))
    harness=base/'bar-host';harness.mkdir()
    for name in ('Commons','Ui','Services'):
        source=Path('/usr/share/omarchy/shell')/name
        if source.exists(): (harness/name).symlink_to(source,target_is_directory=True)
    (harness/'bar').symlink_to(ROOT/'bar',target_is_directory=True)
    (harness/'shell.qml').write_text('import QtQuick\nimport Quickshell\nimport "bar" as Plugin\nShellRoot { FloatingWindow { visible: true; implicitWidth: 300; implicitHeight: 40; Plugin.BarWidget {} } }\n')
    hidden=base/'hidden-app'
    shutil.copytree(ROOT,hidden,ignore=shutil.ignore_patterns('.git','.aws','.codex','.agents','__pycache__','*.log','stage1-*.png'))
    config=json.loads((hidden/'config.json').read_text());config['startHidden']=True
    (hidden/'config.json').write_text(json.dumps(config))
    for label,path in [('application',ROOT),('hidden-application',hidden),('bar',harness)]:
        process=subprocess.Popen(['quickshell','-p',str(path)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        time.sleep(3)
        children=[]
        children_file=Path(f'/proc/{process.pid}/task/{process.pid}/children')
        if children_file.exists():
            for pid in children_file.read_text().split():
                try: children.append(Path(f'/proc/{pid}/cmdline').read_bytes())
                except OSError: pass
        has_sampler=any(b'vitals_sampler.py' in command for command in children)
        if label=='application' and not has_sampler: raise RuntimeError('visible app did not start sampler')
        if label=='hidden-application' and has_sampler: raise RuntimeError('hidden app still sampling')
        try: output=process.communicate(timeout=0.1)[0]
        except subprocess.TimeoutExpired:
            process.terminate();output=process.communicate(timeout=5)[0]
        expected='Configuration Loaded' in output
        errors=[line for line in output.splitlines() if ('ERROR' in line and 'quickshell.ipc' not in line) or 'TypeError' in line or 'ReferenceError' in line or 'Unable to assign' in line]
        if not expected or errors: raise RuntimeError(output)
        print(label+': QML loaded; no binding/type errors (IPC unavailable in sandbox).')
