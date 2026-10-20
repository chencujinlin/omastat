"""Render actual components with copied usage records and the current theme.

Qt offscreen rendering checks layout only; no compositor or IPC validation.
Note: Quickshell 0.3.2's ClippingRectangle does not appear in offscreen
grabToImage captures, so the images can be blank; use a real desktop capture
for visual review. The harness still fails fast on QML load/runtime errors.
"""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='omastat-preview-') as temporary:
    base=Path(temporary)
    source=base/'source'
    shutil.copytree(ROOT,source,ignore=shutil.ignore_patterns('.git','.aws','.codex','.agents','__pycache__','*.png','performance.json','config.local.json'))
    harness=(ROOT/'tests/preview.qml').read_text().replace('import "../"','import "."').replace('import "../services"','import "services"').replace('import "../components"','import "components"')
    (source/'preview.qml').write_text(harness)
    (base/'run').mkdir(mode=0o700)
    usage=Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'omarchy/agents/usage'
    if usage.is_dir(): shutil.copytree(usage,base/'state/omarchy/agents/usage')
    theme=Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'omarchy/current/theme/colors.toml'
    if theme.is_file():
        target=base/'state/omarchy/current/theme';target.mkdir(parents=True)
        shutil.copyfile(theme,target/'colors.toml')
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',XDG_CURRENT_DESKTOP='',QT_STYLE_OVERRIDE='Fusion',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(base/'run'),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),OMASTAT_NO_COLLECT='1',OMASTAT_TEST_HOME=str(base/'native'))
    cases = [
        ('compact', 380, '1', 0, None, False),
        ('hidpi', 320, '2', 0, None, False),
        ('agents', 380, '1', 360, None, False),
        ('orange', 380, '1', 0, {'theme': 'orange'}, False),
        ('settings-orange', 380, '1', 0, {'theme': 'orange', 'showWeather': False}, True),
        ('tokyo-night', 380, '1', 0, {'theme': 'tokyo-night'}, False),
        ('light', 380, '1', 0, {'theme': 'light'}, False),
        ('settings-light', 380, '1', 0, {'theme': 'light', 'showWeather': False}, True),
    ]
    for name, width, scale, scroll, overlay, settings in cases:
        local = source/'config.local.json'
        if overlay is None:
            local.unlink(missing_ok=True)
        else:
            local.write_text(json.dumps(overlay))
        destination=ROOT/'docs'/f'stage1-{name}.png'
        case=dict(env,QT_SCALE_FACTOR=scale,OMASTAT_PREVIEW_PATH=str(destination),OMASTAT_PREVIEW_WIDTH=str(width),OMASTAT_PREVIEW_SCROLL=str(scroll),OMASTAT_PREVIEW_SETTINGS='1' if settings else '0')
        result=subprocess.run(['quickshell','-p',str(source/'preview.qml')],env=case,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=12)
        (Path('/tmp')/f'omastat-stage1-{name}.log').write_text(result.stdout)
        errors=[line for line in result.stdout.splitlines() if ('ERROR' in line and 'quickshell.ipc' not in line) or 'TypeError' in line or 'ReferenceError' in line or 'Unable to assign' in line]
        if 'Configuration Loaded' not in result.stdout or errors: raise RuntimeError(result.stdout)
        if not destination.exists(): raise RuntimeError(result.stdout)
        print(destination)
